"""Multi-Desk Coordinator & Asynchronous Task Scheduler for SOLANA PREDATOR.

Coordinates the six specialized desks:
1. DESK_MARKET (MarketSupervisor: SCAN, TokenRadar, CompositeMarketDataProvider)
2. DESK_WHALE (WhaleSupervisor: WHALE, WhaleIntelligenceEngine)
3. DESK_INVESTIGATION (InvestigationSupervisor: VET, AUDIT, TokenRadar)
4. DESK_QUANT (QuantSupervisor: QUANT, DecisionOutcomeEvaluator, StrategyOptimizer)
5. DESK_RISK (RiskSupervisor: RISK, SKEPTIC, SIZE, IndependentRiskGuard)
6. DESK_COMMAND (CHIEF: CHIEF, AUDIT, AgentOrchestrator)
"""

import time
import uuid
import asyncio
import logging
import re
from typing import Dict, List, Any, Optional, Callable, Awaitable

from backend.config import settings
from backend.database.repository import Repository
from backend.models import (
    NormalizedMarketEvent,
    EventQuality,
    MarketSource,
    AgentName,
    AgentDecision,
    AgentResult,
    ChiefConsensusRecord,
    DeskId,
    ExecutionState,
    AgentTaskExecution,
    StructuredAgentReport,
    DeskStatusRecord,
    WatchlistItem,
    TerminalWsEnvelope,
)

logger = logging.getLogger("predator.desks.coordinator")


def _sanitize_error(msg: str) -> str:
    """Redact any potential bearer tokens or API keys from error messages."""
    if not msg:
        return ""
    sanitized = re.sub(r"(sk-[a-zA-Z0-9_-]{10,})", "[REDACTED_KEY]", str(msg))
    sanitized = re.sub(r"(Bearer\s+[a-zA-Z0-9._-]+)", "Bearer [REDACTED]", sanitized)
    return sanitized[:300]


class MultiDeskCoordinator:
    """Manages the six operational desks, bounded async task scheduling, and structured reporting."""

    def __init__(
        self,
        repository: Repository,
        agent_orchestrator: Any,
        token_radar: Any,
        whale_engine: Any,
        learning_evaluator: Optional[Any] = None,
        risk_guard: Optional[Any] = None,
        market_provider: Optional[Any] = None,
        max_queue_size: int = 100,
        max_concurrency: int = 4,
        task_timeout_sec: float = 10.0,
        max_retries: int = 2,
        dedup_window_sec: float = 2.0,
    ):
        self.repository = repository
        self.orchestrator = agent_orchestrator
        self.token_radar = token_radar
        self.whale_engine = whale_engine
        self.learning_evaluator = learning_evaluator
        self.risk_guard = risk_guard
        self.market_provider = market_provider

        self.max_queue_size = max_queue_size
        self.max_concurrency = max_concurrency
        self.task_timeout_sec = task_timeout_sec
        self.max_retries = max_retries
        self.dedup_window_sec = dedup_window_sec

        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._worker_tasks: List[asyncio.Task] = []
        self._running = False
        self._ws_broadcast: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None

        # Deduplication & Provider Budget Tracking
        self._dedup_cache: Dict[str, float] = {}
        self._provider_budgets: Dict[str, Dict[str, Any]] = {
            "DEX_SCREENER": {"limit_per_min": 60, "used_in_window": 0, "window_start": time.time()},
            "SOLANA_RPC": {"limit_per_min": 120, "used_in_window": 0, "window_start": time.time()},
            "GMGN": {"limit_per_min": 30, "used_in_window": 0, "window_start": time.time()},
            "MOBULA": {"limit_per_min": 30, "used_in_window": 0, "window_start": time.time()},
        }

        # Six Operational Desks Registry
        self.desks: Dict[str, DeskStatusRecord] = {
            DeskId.DESK_MARKET.value: DeskStatusRecord(
                desk_id=DeskId.DESK_MARKET,
                name="Market Intelligence",
                supervisor="MarketSupervisor",
                description="Pair discovery, live price/volume/liquidity tracking, watchlist, and staleness detection.",
                status=ExecutionState.IDLE,
                agents=[AgentName.SCAN.value],
                polling_interval_sec=15.0,
            ),
            DeskId.DESK_WHALE.value: DeskStatusRecord(
                desk_id=DeskId.DESK_WHALE,
                name="Whale Intelligence",
                supervisor="WhaleSupervisor",
                description="Public wallet tracking, on-chain flow classification, and multi-wallet convergence.",
                status=ExecutionState.IDLE,
                agents=[AgentName.WHALE.value],
                polling_interval_sec=20.0,
            ),
            DeskId.DESK_INVESTIGATION.value: DeskStatusRecord(
                desk_id=DeskId.DESK_INVESTIGATION,
                name="Token Investigation",
                supervisor="InvestigationSupervisor",
                description="Token/pool metadata verification, mint format validation, provider comparison, and risk flags.",
                status=ExecutionState.IDLE,
                agents=[AgentName.VET.value, AgentName.AUDIT.value],
                polling_interval_sec=25.0,
            ),
            DeskId.DESK_QUANT.value: DeskStatusRecord(
                desk_id=DeskId.DESK_QUANT,
                name="Quant Research",
                supervisor="QuantSupervisor",
                description="Turnover/volatility indicators, dataset validation, and chronological TRAIN/VAL/TEST backtests.",
                status=ExecutionState.IDLE,
                agents=[AgentName.QUANT.value],
                polling_interval_sec=30.0,
            ),
            DeskId.DESK_RISK.value: DeskStatusRecord(
                desk_id=DeskId.DESK_RISK,
                name="Risk & Skeptic",
                supervisor="RiskSupervisor",
                description="Contrarian anomaly detection, exposure limits, and authoritative backend RISK VETO enforcement.",
                status=ExecutionState.IDLE,
                agents=[AgentName.RISK.value, AgentName.SKEPTIC.value, AgentName.SIZE.value],
                polling_interval_sec=15.0,
            ),
            DeskId.DESK_COMMAND.value: DeskStatusRecord(
                desk_id=DeskId.DESK_COMMAND,
                name="Command Center",
                supervisor="CHIEF",
                description="Cross-desk report aggregation, disagreement tracking, provider health, and final consensus.",
                status=ExecutionState.IDLE,
                agents=[AgentName.CHIEF.value, AgentName.AUDIT.value],
                polling_interval_sec=15.0,
            ),
        }

        # Real-time status of the 9 agents
        self.agent_states: Dict[str, Dict[str, Any]] = {}
        agent_desk_map = {
            AgentName.SCAN.value: DeskId.DESK_MARKET.value,
            AgentName.WHALE.value: DeskId.DESK_WHALE.value,
            AgentName.VET.value: DeskId.DESK_INVESTIGATION.value,
            AgentName.QUANT.value: DeskId.DESK_QUANT.value,
            AgentName.RISK.value: DeskId.DESK_RISK.value,
            AgentName.SKEPTIC.value: DeskId.DESK_RISK.value,
            AgentName.SIZE.value: DeskId.DESK_RISK.value,
            AgentName.CHIEF.value: DeskId.DESK_COMMAND.value,
            AgentName.AUDIT.value: DeskId.DESK_COMMAND.value,
        }
        for ag in AgentName:
            self.agent_states[ag.value] = {
                "agent_id": ag.value,
                "desk_id": agent_desk_map[ag.value],
                "status": ExecutionState.IDLE.value,
                "active_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "last_execution_at": None,
                "last_duration_ms": 0.0,
                "last_decision": None,
                "last_confidence": None,
                "model_usage_count": 0,
                "last_error": None,
            }

    def set_ws_broadcast_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        self._ws_broadcast = callback

    async def initialize(self) -> None:
        """Restore persisted desk states from SQLite V4 and seed default watchlists."""
        persisted = await self.repository.get_all_desks()
        persisted_map = {d["desk_id"]: d for d in persisted}

        for desk_id, record in self.desks.items():
            if desk_id in persisted_map:
                saved = persisted_map[desk_id]
                record.is_paused = bool(saved.get("is_paused", False))
                record.status = ExecutionState.PAUSED if record.is_paused else ExecutionState.IDLE
                record.completed_tasks = int(saved.get("completed_tasks", 0))
                record.failed_tasks = int(saved.get("failed_tasks", 0))
                record.skipped_tasks = int(saved.get("skipped_tasks", 0))
                record.retry_count = int(saved.get("retry_count", 0))
                record.last_execution_at = saved.get("last_execution_at")
                record.last_duration_ms = float(saved.get("last_duration_ms", 0.0))
                record.last_source = saved.get("last_source")
                record.has_stale_data = bool(saved.get("has_stale_data", False))
                record.has_missing_data = bool(saved.get("has_missing_data", False))
                record.last_error_code = saved.get("last_error_code")
                record.last_error_message = saved.get("last_error_message")
            await self.repository.upsert_desk_status(record)

        # Ensure default watchlist items exist
        existing_wl = await self.repository.get_watchlist_items()
        if not existing_wl:
            now = time.time()
            default_items = [
                WatchlistItem(
                    identifier="So11111111111111111111111111111111111111112",
                    item_type="TOKEN",
                    label="Wrapped SOL (WSOL)",
                    added_at=now,
                    notes="Primary Solana native liquidity benchmark",
                ),
                WatchlistItem(
                    identifier="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    item_type="TOKEN",
                    label="USD Coin (USDC)",
                    added_at=now,
                    notes="Solana Mainnet canonical USD stablecoin",
                ),
                WatchlistItem(
                    identifier="WhalePublicObs11111111111111111111111111111",
                    item_type="WALLET",
                    label="Observed Public Liquidity Wallet #1",
                    added_at=now,
                    notes="Read-only public on-chain address monitored for swap flows",
                ),
            ]
            for item in default_items:
                await self.repository.upsert_watchlist_item(item)

        self._running = True
        for i in range(2):
            self._worker_tasks.append(asyncio.create_task(self._scheduler_worker_loop(i)))

    async def shutdown(self) -> None:
        """Cancel background scheduler workers cleanly and persist final desk states."""
        self._running = False
        for t in self._worker_tasks:
            if not t.done():
                t.cancel()
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()
        for record in self.desks.values():
            if not record.is_paused:
                record.status = ExecutionState.IDLE
            record.active_tasks = 0
            record.queued_tasks = 0
            await self.repository.upsert_desk_status(record)

    async def _emit_ws(
        self,
        event_type: str,
        payload: Dict[str, Any],
        desk_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        if not self._ws_broadcast:
            return
        env = TerminalWsEnvelope(
            event_id=f"ev_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            timestamp_utc=time.time(),
            desk_id=desk_id,
            agent_id=agent_id,
            correlation_id=correlation_id,
            payload_version="1.0",
            payload=payload,
        )
        try:
            await self._ws_broadcast(env.model_dump())
        except Exception as e:
            logger.debug("WS broadcast failed for %s: %s", event_type, e)

    def check_provider_budget(self, source: str) -> bool:
        """Enforce per-provider request budgets per minute."""
        now = time.time()
        entry = self._provider_budgets.get(source)
        if not entry:
            return True
        if now - entry["window_start"] >= 60.0:
            entry["window_start"] = now
            entry["used_in_window"] = 0
        if entry["used_in_window"] >= entry["limit_per_min"]:
            return False
        entry["used_in_window"] += 1
        return True

    async def pause_desk(self, desk_id: str) -> DeskStatusRecord:
        if desk_id not in self.desks:
            raise ValueError(f"Unknown desk_id: {desk_id}")
        desk = self.desks[desk_id]
        desk.is_paused = True
        desk.status = ExecutionState.PAUSED
        for ag in desk.agents:
            if ag in self.agent_states:
                self.agent_states[ag]["status"] = ExecutionState.PAUSED.value
        await self.repository.upsert_desk_status(desk)
        await self._emit_ws("desk.status", desk.model_dump(), desk_id=desk_id)
        return desk

    async def resume_desk(self, desk_id: str) -> DeskStatusRecord:
        if desk_id not in self.desks:
            raise ValueError(f"Unknown desk_id: {desk_id}")
        desk = self.desks[desk_id]
        desk.is_paused = False
        desk.status = ExecutionState.IDLE
        for ag in desk.agents:
            if ag in self.agent_states:
                self.agent_states[ag]["status"] = ExecutionState.IDLE.value
        await self.repository.upsert_desk_status(desk)
        await self._emit_ws("desk.status", desk.model_dump(), desk_id=desk_id)
        return desk

    async def record_pipeline_execution(
        self,
        event: NormalizedMarketEvent,
        consensus: ChiefConsensusRecord,
        context: Dict[str, Any],
    ) -> List[StructuredAgentReport]:
        """Record real desk tasks and structured reports from a completed multi-agent pipeline cycle."""
        now = time.time()
        is_stale = (
            event.quality == EventQuality.STALE
            or event.observation_state == "STALE"
            or event.freshness_seconds > settings.DATA_STALENESS_THRESHOLD_SEC
        )
        missing = list(event.missing_fields or [])
        if event.price_usd is None and "price_usd" not in missing:
            missing.append("price_usd")
        if event.liquidity_usd is None and "liquidity_usd" not in missing:
            missing.append("liquidity_usd")
        if event.volume_24h_usd is None and "volume_24h_usd" not in missing:
            missing.append("volume_24h_usd")

        desk_agent_mapping = [
            (DeskId.DESK_MARKET, "MarketSupervisor", [AgentName.SCAN.value]),
            (DeskId.DESK_WHALE, "WhaleSupervisor", [AgentName.WHALE.value]),
            (DeskId.DESK_INVESTIGATION, "InvestigationSupervisor", [AgentName.VET.value, AgentName.AUDIT.value]),
            (DeskId.DESK_QUANT, "QuantSupervisor", [AgentName.QUANT.value]),
            (DeskId.DESK_RISK, "RiskSupervisor", [AgentName.RISK.value, AgentName.SKEPTIC.value, AgentName.SIZE.value]),
            (DeskId.DESK_COMMAND, "CHIEF", [AgentName.CHIEF.value]),
        ]

        created_reports: List[StructuredAgentReport] = []

        # Emit market.observation envelope
        await self._emit_ws(
            "market.observation",
            {
                "event_id": event.event_id,
                "token_mint": event.token_mint,
                "source": event.source.value,
                "price_usd": event.price_usd,
                "liquidity_usd": event.liquidity_usd,
                "volume_24h_usd": event.volume_24h_usd,
                "freshness_seconds": event.freshness_seconds,
                "quality": event.quality.value,
                "observation_state": event.observation_state,
                "missing_fields": missing,
            },
            desk_id=DeskId.DESK_MARKET.value,
            correlation_id=consensus.consensus_id,
        )

        for desk_enum, supervisor, agent_ids in desk_agent_mapping:
            desk = self.desks[desk_enum.value]
            if desk.is_paused:
                desk.skipped_tasks += 1
                await self.repository.upsert_desk_status(desk)
                continue

            desk_duration_ms = 0.0
            for ag_id in agent_ids:
                task_id = f"tsk_{ag_id.lower()}_{uuid.uuid4().hex[:10]}"
                ag_res: Optional[AgentResult] = consensus.contributing_agents.get(ag_id)

                if ag_id == AgentName.CHIEF.value:
                    dur_ms = consensus.processing_total_latency_ms
                    dec_str = consensus.final_decision.value
                    conf_val = consensus.confidence_score
                    reasons = [consensus.chief_reason]
                    details = {
                        "recommended_position_usd": consensus.recommended_position_usd,
                        "is_risk_vetoed": consensus.is_risk_vetoed,
                        "favorable_signals": consensus.favorable_signals,
                        "unfavorable_signals": consensus.unfavorable_signals,
                    }
                elif ag_res:
                    dur_ms = ag_res.processing_latency_ms
                    dec_str = ag_res.decision.value
                    conf_val = ag_res.confidence
                    reasons = ag_res.reason_codes
                    details = ag_res.details
                else:
                    continue

                desk_duration_ms += dur_ms
                prompt_ver = consensus.prompt_version if ag_id == AgentName.CHIEF.value else None
                model_id = (
                    consensus.llm_advisory.get("model")
                    if (ag_id == AgentName.CHIEF.value and isinstance(consensus.llm_advisory, dict))
                    else None
                )

                task_rec = AgentTaskExecution(
                    task_id=task_id,
                    event_id=event.event_id,
                    desk_id=desk_enum,
                    agent_id=ag_id,
                    started_at=now - (dur_ms / 1000.0),
                    finished_at=now,
                    duration_ms=round(dur_ms, 3),
                    status=ExecutionState.COMPLETED,
                    source=event.source.value,
                    source_timestamp=event.source_timestamp,
                    observation_quality=event.quality.value,
                    input_summary=f"mint={event.token_mint[:8]} px={event.price_usd} liq={event.liquidity_usd}",
                    output_summary=f"{dec_str}: {', '.join(reasons[:3])}",
                    missing_fields=missing,
                    confidence=conf_val,
                    prompt_version=prompt_ver,
                    model_id=model_id,
                )
                await self.repository.save_desk_task(task_rec)

                # Update in-memory agent state (IDLE after completion, never stuck on RUNNING)
                st = self.agent_states[ag_id]
                st["status"] = ExecutionState.IDLE.value
                st["completed_tasks"] += 1
                st["last_execution_at"] = now
                st["last_duration_ms"] = round(dur_ms, 3)
                st["last_decision"] = dec_str
                st["last_confidence"] = conf_val
                if model_id:
                    st["model_usage_count"] += 1

                await self._emit_ws(
                    "agent.task.completed",
                    task_rec.model_dump(),
                    desk_id=desk_enum.value,
                    agent_id=ag_id,
                    correlation_id=consensus.consensus_id,
                )

                # Build structured report separating observed facts, inferences, and unknowns
                observed_facts, inferred, risk_flags, contradictions = self._build_structured_evidence(
                    desk_enum, ag_id, event, consensus, details, reasons, is_stale
                )

                report = StructuredAgentReport(
                    report_id=f"rep_{desk_enum.value.lower()}_{ag_id.lower()}_{uuid.uuid4().hex[:8]}",
                    desk_id=desk_enum,
                    supervisor=supervisor,
                    agent_id=ag_id,
                    token_mint=event.token_mint,
                    event_id=event.event_id,
                    task_id=task_id,
                    observed_at=now,
                    source_timestamp=event.source_timestamp,
                    created_at=now,
                    source=event.source.value,
                    observation_quality=event.quality.value,
                    observed_facts=observed_facts,
                    inferred_conclusions=inferred,
                    unknown_or_missing=missing,
                    contradictions=contradictions,
                    risk_flags=risk_flags,
                    decision=dec_str,
                    confidence=conf_val,
                    rationale="; ".join(reasons),
                    is_stale=is_stale,
                    is_veto=(dec_str == AgentDecision.VETO.value),
                    metadata=details,
                )
                await self.repository.save_desk_report(report)
                created_reports.append(report)

                await self._emit_ws(
                    "agent.report.created",
                    report.model_dump(),
                    desk_id=desk_enum.value,
                    agent_id=ag_id,
                    correlation_id=consensus.consensus_id,
                )

                if dec_str == AgentDecision.VETO.value:
                    await self._emit_ws(
                        "risk.event",
                        {
                            "token_mint": event.token_mint,
                            "agent_id": ag_id,
                            "desk_id": desk_enum.value,
                            "is_authoritative_risk_veto": (ag_id == AgentName.RISK.value),
                            "reasons": reasons,
                            "timestamp": now,
                        },
                        desk_id=desk_enum.value,
                        agent_id=ag_id,
                        correlation_id=consensus.consensus_id,
                    )

            # Update desk status record
            desk.status = ExecutionState.IDLE
            desk.completed_tasks += len(agent_ids)
            desk.last_execution_at = now
            desk.last_duration_ms = round(desk_duration_ms, 3)
            desk.last_source = event.source.value
            desk.has_stale_data = is_stale
            desk.has_missing_data = len(missing) > 0
            await self.repository.upsert_desk_status(desk)
            await self._emit_ws(
                "desk.status",
                desk.model_dump(),
                desk_id=desk_enum.value,
                correlation_id=consensus.consensus_id,
            )

        # Emit chief.summary event
        await self._emit_ws(
            "chief.summary",
            {
                "consensus_id": consensus.consensus_id,
                "token_mint": consensus.token_mint,
                "final_decision": consensus.final_decision.value,
                "is_risk_vetoed": consensus.is_risk_vetoed,
                "chief_reason": consensus.chief_reason,
                "confidence_score": consensus.confidence_score,
                "recommended_position_usd": consensus.recommended_position_usd,
                "sources_used": consensus.sources_used,
                "timestamp": consensus.timestamp,
            },
            desk_id=DeskId.DESK_COMMAND.value,
            agent_id=AgentName.CHIEF.value,
            correlation_id=consensus.consensus_id,
        )

        return created_reports

    def _build_structured_evidence(
        self,
        desk_id: DeskId,
        agent_id: str,
        event: NormalizedMarketEvent,
        consensus: ChiefConsensusRecord,
        details: Dict[str, Any],
        reasons: List[str],
        is_stale: bool,
    ):
        observed_facts: List[str] = [
            f"Source provider: {event.source.value}",
            f"Data freshness: {event.freshness_seconds:.2f}s (quality={event.quality.value})",
        ]
        if event.price_usd is not None:
            observed_facts.append(f"Observed price USD: ${event.price_usd:.6f}")
        if event.liquidity_usd is not None:
            observed_facts.append(f"Observed pool liquidity USD: ${event.liquidity_usd:,.2f}")
        if event.volume_24h_usd is not None:
            observed_facts.append(f"Observed 24h volume USD: ${event.volume_24h_usd:,.2f}")

        inferred: List[str] = [f"Agent {agent_id} classification: {', '.join(reasons)}"]
        risk_flags: List[str] = []
        contradictions: List[str] = []

        if is_stale:
            risk_flags.append(f"STALE_OBSERVATION ({event.freshness_seconds:.1f}s > {settings.DATA_STALENESS_THRESHOLD_SEC}s)")
        if event.missing_fields:
            risk_flags.append(f"MISSING_FIELDS: {', '.join(event.missing_fields)}")

        if agent_id == AgentName.WHALE.value:
            net_flow = details.get("net_flow_usd")
            if net_flow is not None:
                observed_facts.append(f"Observed tracked wallet net flow USD: ${net_flow:,.2f}")
            inferred.append("Convergence score reflects wallet timing correlation, not confirmed entity identity.")
        elif agent_id == AgentName.VET.value:
            meta = event.metadata or {}
            if meta.get("freeze_authority_present") is True:
                risk_flags.append("FREEZE_AUTHORITY_ACTIVE_WARNING")
            inferred.append("Metadata check reflects observed fields; not an absolute guarantee of contract safety.")
        elif agent_id == AgentName.QUANT.value:
            ratio = details.get("vol_liq_ratio")
            unc = details.get("uncertainty_band")
            if ratio is not None:
                observed_facts.append(f"Computed 24h Volume/Liquidity ratio: {ratio:.3f}")
            if unc is not None:
                inferred.append(f"Statistical uncertainty band estimated at {unc:.3f} (includes fee/slippage assumptions).")
        elif agent_id in (AgentName.RISK.value, AgentName.SKEPTIC.value):
            for r in reasons:
                if "VETO" in r or "RISK" in r:
                    risk_flags.append(r)
        elif agent_id == AgentName.CHIEF.value:
            # Check for disagreements across contributing agents
            decisions_set = {
                ag: r.decision.value for ag, r in consensus.contributing_agents.items()
            }
            if AgentDecision.BUY_CANDIDATE.value in decisions_set.values() and AgentDecision.VETO.value in decisions_set.values():
                contradictions.append(
                    f"Inter-agent disagreement: bullish signals overridden by authoritative VETO ({decisions_set})"
                )
            if consensus.llm_advisory and isinstance(consensus.llm_advisory, dict):
                inferred.append(
                    f"LLM Advisory ({consensus.llm_advisory.get('model', 'model')}): {consensus.llm_advisory.get('summary', '')}"
                )

        return observed_facts, inferred, risk_flags, contradictions

    async def enqueue_desk_task(
        self,
        desk_id: str,
        event: NormalizedMarketEvent,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Enqueue an asynchronous desk analysis task with deduplication and bounded queue."""
        if desk_id not in self.desks:
            raise ValueError(f"Unknown desk_id: {desk_id}")

        desk = self.desks[desk_id]
        if desk.is_paused:
            desk.skipped_tasks += 1
            await self.repository.upsert_desk_status(desk)
            return {"status": ExecutionState.PAUSED.value, "desk_id": desk_id, "reason": "Desk is paused"}

        dedup_key = f"{desk_id}:{event.token_mint}:{event.event_id}"
        now = time.time()
        last_seen = self._dedup_cache.get(dedup_key)
        if last_seen and (now - last_seen) < self.dedup_window_sec:
            desk.skipped_tasks += 1
            await self.repository.upsert_desk_status(desk)
            return {"status": ExecutionState.SKIPPED.value, "desk_id": desk_id, "reason": "Deduplicated within window"}

        self._dedup_cache[dedup_key] = now
        if self._queue.full():
            desk.skipped_tasks += 1
            return {"status": ExecutionState.SKIPPED.value, "desk_id": desk_id, "reason": "Task queue full"}

        job_id = f"job_{uuid.uuid4().hex[:10]}"
        desk.queued_tasks += 1
        desk.status = ExecutionState.QUEUED
        await self._queue.put((job_id, desk_id, event, context or {}))
        return {"status": ExecutionState.QUEUED.value, "job_id": job_id, "desk_id": desk_id}

    async def run_desk_now(
        self,
        desk_id: str,
        event: NormalizedMarketEvent,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a desk's assigned real agents immediately with bounded timeout and retry backoff."""
        if desk_id not in self.desks:
            raise ValueError(f"Unknown desk_id: {desk_id}")

        desk = self.desks[desk_id]
        if desk.is_paused:
            desk.skipped_tasks += 1
            await self.repository.upsert_desk_status(desk)
            return {"status": ExecutionState.PAUSED.value, "desk_id": desk_id, "tasks": [], "reports": []}

        ctx = context or {}
        desk.active_tasks += 1
        desk.status = ExecutionState.RUNNING
        await self.repository.upsert_desk_status(desk)
        await self._emit_ws("desk.status", desk.model_dump(), desk_id=desk_id)

        agent_map = {
            AgentName.SCAN.value: self.orchestrator.scan,
            AgentName.WHALE.value: self.orchestrator.whale,
            AgentName.VET.value: self.orchestrator.vet,
            AgentName.QUANT.value: self.orchestrator.quant,
            AgentName.SKEPTIC.value: self.orchestrator.skeptic,
            AgentName.SIZE.value: self.orchestrator.size,
            AgentName.RISK.value: self.orchestrator.risk,
            AgentName.CHIEF.value: self.orchestrator.chief,
            AgentName.AUDIT.value: self.orchestrator.audit,
        }

        tasks_out: List[Dict[str, Any]] = []
        reports_out: List[Dict[str, Any]] = []
        t0 = time.perf_counter()

        try:
            for ag_id in desk.agents:
                agent_obj = agent_map.get(ag_id)
                if not agent_obj:
                    continue

                task_id = f"tsk_{ag_id.lower()}_{uuid.uuid4().hex[:10]}"
                started_at = time.time()
                self.agent_states[ag_id]["status"] = ExecutionState.RUNNING.value
                self.agent_states[ag_id]["active_tasks"] += 1

                await self._emit_ws(
                    "agent.task.started",
                    {"task_id": task_id, "desk_id": desk_id, "agent_id": ag_id, "token_mint": event.token_mint},
                    desk_id=desk_id,
                    agent_id=ag_id,
                )

                attempt = 0
                ag_res: Optional[AgentResult] = None
                last_err: Optional[Exception] = None

                while attempt <= self.max_retries:
                    try:
                        async with self._semaphore:
                            ag_res = await asyncio.wait_for(
                                agent_obj.evaluate(event, ctx),
                                timeout=self.task_timeout_sec,
                            )
                        break
                    except Exception as e:
                        last_err = e
                        attempt += 1
                        if attempt <= self.max_retries:
                            desk.retry_count += 1
                            await asyncio.sleep(0.05 * (2 ** (attempt - 1)))

                finished_at = time.time()
                dur_ms = round((finished_at - started_at) * 1000.0, 3)
                self.agent_states[ag_id]["active_tasks"] = max(0, self.agent_states[ag_id]["active_tasks"] - 1)

                missing = list(event.missing_fields or [])
                is_stale = (
                    event.quality == EventQuality.STALE
                    or event.observation_state == "STALE"
                    or event.freshness_seconds > settings.DATA_STALENESS_THRESHOLD_SEC
                )

                if ag_res is not None:
                    self.agent_states[ag_id]["status"] = ExecutionState.IDLE.value
                    self.agent_states[ag_id]["completed_tasks"] += 1
                    self.agent_states[ag_id]["last_execution_at"] = finished_at
                    self.agent_states[ag_id]["last_duration_ms"] = dur_ms
                    self.agent_states[ag_id]["last_decision"] = ag_res.decision.value
                    self.agent_states[ag_id]["last_confidence"] = ag_res.confidence

                    task_rec = AgentTaskExecution(
                        task_id=task_id,
                        event_id=event.event_id,
                        desk_id=DeskId(desk_id),
                        agent_id=ag_id,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_ms=dur_ms,
                        status=ExecutionState.COMPLETED,
                        source=event.source.value,
                        source_timestamp=event.source_timestamp,
                        observation_quality=event.quality.value,
                        input_summary=f"mint={event.token_mint[:8]} px={event.price_usd}",
                        output_summary=f"{ag_res.decision.value}: {', '.join(ag_res.reason_codes)}",
                        missing_fields=missing,
                        confidence=ag_res.confidence,
                    )
                    await self.repository.save_desk_task(task_rec)
                    tasks_out.append(task_rec.model_dump())

                    dummy_consensus = ChiefConsensusRecord(
                        consensus_id=f"desk_{uuid.uuid4().hex[:8]}",
                        token_mint=event.token_mint,
                        timestamp=finished_at,
                        final_decision=ag_res.decision,
                        is_risk_vetoed=(ag_id == AgentName.RISK.value and ag_res.decision == AgentDecision.VETO),
                        chief_reason=", ".join(ag_res.reason_codes),
                        contributing_agents={ag_id: ag_res},
                        processing_total_latency_ms=dur_ms,
                    )
                    obs_facts, inferred, r_flags, contrad = self._build_structured_evidence(
                        DeskId(desk_id),
                        ag_id,
                        event,
                        dummy_consensus,
                        ag_res.details,
                        ag_res.reason_codes,
                        is_stale,
                    )
                    rep = StructuredAgentReport(
                        report_id=f"rep_{desk_id.lower()}_{ag_id.lower()}_{uuid.uuid4().hex[:8]}",
                        desk_id=DeskId(desk_id),
                        supervisor=desk.supervisor,
                        agent_id=ag_id,
                        token_mint=event.token_mint,
                        event_id=event.event_id,
                        task_id=task_id,
                        observed_at=finished_at,
                        source_timestamp=event.source_timestamp,
                        created_at=finished_at,
                        source=event.source.value,
                        observation_quality=event.quality.value,
                        observed_facts=obs_facts,
                        inferred_conclusions=inferred,
                        unknown_or_missing=missing,
                        contradictions=contrad,
                        risk_flags=r_flags,
                        decision=ag_res.decision.value,
                        confidence=ag_res.confidence,
                        rationale="; ".join(ag_res.reason_codes),
                        is_stale=is_stale,
                        is_veto=(ag_res.decision == AgentDecision.VETO),
                        metadata=ag_res.details,
                    )
                    await self.repository.save_desk_report(rep)
                    reports_out.append(rep.model_dump())
                    desk.completed_tasks += 1
                    await self._emit_ws("agent.task.completed", task_rec.model_dump(), desk_id=desk_id, agent_id=ag_id)
                    await self._emit_ws("agent.report.created", rep.model_dump(), desk_id=desk_id, agent_id=ag_id)
                else:
                    err_clean = _sanitize_error(str(last_err))
                    self.agent_states[ag_id]["status"] = ExecutionState.FAILED.value
                    self.agent_states[ag_id]["failed_tasks"] += 1
                    self.agent_states[ag_id]["last_error"] = err_clean
                    desk.failed_tasks += 1
                    desk.last_error_code = type(last_err).__name__ if last_err else "EXECUTION_ERROR"
                    desk.last_error_message = err_clean

                    task_rec = AgentTaskExecution(
                        task_id=task_id,
                        event_id=event.event_id,
                        desk_id=DeskId(desk_id),
                        agent_id=ag_id,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_ms=dur_ms,
                        status=ExecutionState.FAILED,
                        source=event.source.value,
                        source_timestamp=event.source_timestamp,
                        observation_quality=event.quality.value,
                        input_summary=f"mint={event.token_mint[:8]}",
                        output_summary="Task execution failed",
                        missing_fields=missing,
                        error_code=desk.last_error_code,
                        error_message_sanitized=err_clean,
                    )
                    await self.repository.save_desk_task(task_rec)
                    tasks_out.append(task_rec.model_dump())
                    await self._emit_ws("agent.task.failed", task_rec.model_dump(), desk_id=desk_id, agent_id=ag_id)

            desk.last_execution_at = time.time()
            desk.last_duration_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            desk.last_source = event.source.value
        finally:
            desk.active_tasks = max(0, desk.active_tasks - 1)
            desk.status = ExecutionState.PAUSED if desk.is_paused else ExecutionState.IDLE
            await self.repository.upsert_desk_status(desk)
            await self._emit_ws("desk.status", desk.model_dump(), desk_id=desk_id)

        return {
            "status": desk.status.value,
            "desk_id": desk_id,
            "tasks": tasks_out,
            "reports": reports_out,
        }

    async def _scheduler_worker_loop(self, worker_idx: int) -> None:
        while self._running:
            try:
                job_id, desk_id, event, ctx = await self._queue.get()
                if desk_id in self.desks:
                    self.desks[desk_id].queued_tasks = max(0, self.desks[desk_id].queued_tasks - 1)
                await self.run_desk_now(desk_id, event, ctx)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Scheduler worker %d error: %s", worker_idx, e)
