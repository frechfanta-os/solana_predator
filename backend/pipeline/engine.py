"""High-performance event processing pipeline for SOLANA PREDATOR."""

import time
import asyncio
import logging
from typing import Dict, Any, Optional, Callable, Awaitable
from backend.models import (
    NormalizedMarketEvent,
    TokenSnapshot,
    TokenLifecycleState,
    AgentDecision,
    WhaleActivity,
    ChiefConsensusRecord,
)
from backend.database.repository import Repository
from backend.market.normalizer import EventNormalizer
from backend.market.event_bus import EventBus
from backend.market.health import HealthTracker
from backend.discovery.token_radar import TokenRadar
from backend.whale.whale_intelligence import WhaleIntelligenceEngine
from backend.agents.orchestrator import AgentOrchestrator
from backend.paper.positions import PositionManager
from backend.paper.accounting import PaperAccounting
from backend.paper.broker import PaperBroker
from backend.paper.exit_monitor import ExitMonitor
from backend.config import settings

logger = logging.getLogger("predator.pipeline.engine")


class PredatorEngine:
    """End-to-end pipeline driving the market terminal, multi-agent engine, and paper trading."""

    def __init__(
        self,
        repository: Repository,
        event_bus: EventBus,
        health_tracker: HealthTracker,
        normalizer: EventNormalizer,
        token_radar: TokenRadar,
        whale_engine: WhaleIntelligenceEngine,
        agent_orchestrator: AgentOrchestrator,
        position_manager: PositionManager,
        paper_accounting: PaperAccounting,
        paper_broker: PaperBroker,
        exit_monitor: ExitMonitor,
        live_order_manager: Optional[Any] = None,
        learning_evaluator: Optional[Any] = None,
        trading_mode: str = "PAPER",
    ):
        self.repository = repository
        self.event_bus = event_bus
        self.health = health_tracker
        self.normalizer = normalizer
        self.token_radar = token_radar
        self.whale_engine = whale_engine
        self.agents = agent_orchestrator
        self.positions = position_manager
        self.accounting = paper_accounting
        self.broker = paper_broker
        self.exit_monitor = exit_monitor
        self.live_order_manager = live_order_manager
        self.learning_evaluator = learning_evaluator
        self.trading_mode = trading_mode

        # WebSocket broadcast hook
        self._ws_broadcast_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
        self._is_running = False

    def set_ws_broadcast_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        self._ws_broadcast_callback = callback

    async def initialize(self) -> None:
        """Startup sequence: position restoration, accounting reconciliation, event bus hook."""
        logger.info("Initializing SOLANA PREDATOR pipeline engine...")
        await self.positions.restore_from_db()
        await self.accounting.reconcile_on_startup()
        self.event_bus.subscribe(self.process_market_event)
        self._is_running = True
        logger.info("Pipeline engine ready. Starting event bus...")
        await self.event_bus.start()

    async def shutdown(self) -> None:
        """Gracefully shutdown engine."""
        logger.info("Shutting down SOLANA PREDATOR pipeline engine...")
        self._is_running = False
        await self.event_bus.stop()
        open_pos = self.positions.get_open_positions()
        await self.accounting.compute_snapshot(open_pos)

    async def process_market_event(self, event: NormalizedMarketEvent) -> None:
        """Complete deterministic pipeline flow for an incoming normalized event."""
        e2e_start_mono = time.perf_counter()
        self.health.record_event_received(event.source.value, event.local_receive_timestamp)

        # Stage 1: Reception Latency
        rx_latency_ms = max(0.0, (event.processing_timestamp - event.local_receive_timestamp) * 1000.0)
        self.health.latency_receive.record(rx_latency_ms)

        # Stage 2: Normalization Latency
        norm_latency_ms = max(0.01, event.freshness_seconds * 1000.0)
        self.health.latency_normalize.record(norm_latency_ms)

        # Stage 6 Prep: Persistence Timer
        t_persist_start = time.perf_counter()
        await self.repository.save_market_event(event)

        # Stage 3: Indicators Timer (Radar State + Whale Intelligence)
        t_ind_start = time.perf_counter()
        current_state = await self.token_radar.process_event(event)

        # Save Token Snapshot
        now = time.time()
        txns_5m = event.metadata.get("txns_5m") if event.metadata else {}
        buys_5m = txns_5m.get("buys", 0) if isinstance(txns_5m, dict) else 0
        sells_5m = txns_5m.get("sells", 0) if isinstance(txns_5m, dict) else 0

        snapshot = TokenSnapshot(
            snapshot_id=f"snap_{event.token_mint[:8]}_{int(now*1000)}",
            token_mint=event.token_mint,
            timestamp=now,
            price_usd=event.price_usd,
            volume_24h_usd=event.volume_24h_usd,
            liquidity_usd=event.liquidity_usd,
            fdv_usd=None,
            buys_5m=buys_5m,
            sells_5m=sells_5m,
            lifecycle_state=current_state,
            lifecycle_reason=f"Updated via {event.source.value}",
            is_stale=event.freshness_seconds > settings.DATA_STALENESS_THRESHOLD_SEC,
        )
        await self.repository.save_token_snapshot(snapshot)
        persist_elapsed_ms = (time.perf_counter() - t_persist_start) * 1000.0
        self.health.latency_persistence.record(persist_elapsed_ms)

        # Check & Update Whale Activity if present in event metadata
        if event.metadata and "whale_wallet" in event.metadata and event.signature:
            activity = self.whale_engine.classify_raw_transaction(
                signature=event.signature,
                wallet_address=event.metadata["whale_wallet"],
                token_mint=event.token_mint,
                event_metadata=event.metadata,
            )
            await self.whale_engine.record_activity(activity)

        convergence = self.whale_engine.calculate_convergence(event.token_mint)
        ind_latency_ms = (time.perf_counter() - t_ind_start) * 1000.0
        self.health.latency_indicators.record(ind_latency_ms)

        # Mark to Market Open Positions & Evaluate Exits
        t_fill_start = time.perf_counter()
        has_pos = self.positions.has_open_position(event.token_mint)
        if has_pos and event.price_usd:
            pos = await self.positions.mark_to_market(
                event.token_mint,
                event.price_usd,
                event.freshness_seconds,
            )
            if pos:
                exit_dec = self.exit_monitor.evaluate_position(pos, event, convergence)
                if exit_dec.should_exit:
                    exit_reason = f"EXIT_MONITOR_{exit_dec.urgency}: {', '.join(exit_dec.reason_codes)}"
                    await self.broker.execute_simulated_sell(
                        event.token_mint,
                        event.price_usd,
                        exit_reason,
                        pool_liquidity_usd=event.liquidity_usd,
                    )
                    await self.token_radar.advance_lifecycle(
                        event.token_mint,
                        TokenLifecycleState.ANALYZED,
                        f"Position exited: {exit_reason}",
                    )

        # Stage 4: Multi-Agent Orchestration
        open_positions = self.positions.get_open_positions()
        await self.accounting.compute_snapshot(open_positions)

        agent_context = {
            "whale_convergence": convergence,
            "portfolio_equity": self.accounting.cash_balance + sum(p.current_value_usd for p in open_positions),
            "cash_balance": self.accounting.cash_balance,
            "open_positions_count": len(open_positions),
            "current_drawdown_pct": self.accounting.max_drawdown_pct,
            "has_existing_position": has_pos,
        }

        agent_start_mono = time.perf_counter()
        consensus: ChiefConsensusRecord = await self.agents.run_pipeline(event, agent_context)
        agent_latency_ms = (time.perf_counter() - agent_start_mono) * 1000.0
        self.health.latency_agents.record(agent_latency_ms)

        # Stage 5: Record RISK Check Latency specifically
        if "RISK" in consensus.contributing_agents:
            self.health.latency_risk.record(consensus.contributing_agents["RISK"].processing_latency_ms)

        # Stage 7: Act on Consensus Decision & Simulated Fill
        if consensus.final_decision == AgentDecision.BUY_CANDIDATE:
            await self.token_radar.advance_lifecycle(
                event.token_mint,
                TokenLifecycleState.PAPER_CANDIDATE,
                consensus.chief_reason,
            )
            if consensus.recommended_position_usd and event.price_usd:
                token_symbol = event.metadata.get("symbol", "TOKEN") if event.metadata else "TOKEN"
                await self.broker.execute_simulated_buy(
                    token_mint=event.token_mint,
                    token_symbol=token_symbol,
                    requested_usd=consensus.recommended_position_usd,
                    current_price_usd=event.price_usd,
                    pool_liquidity_usd=event.liquidity_usd,
                )
                # If Live Order Manager is enabled and wallet connected, generate an audited proposal for user review
                if self.live_order_manager and self.live_order_manager.wallet_service.get_status():
                    try:
                        amt_sol = round(consensus.recommended_position_usd / 150.0, 4)
                        await self.live_order_manager.create_trade_proposal(
                            token_mint=event.token_mint,
                            token_symbol=token_symbol,
                            amount_sol=amt_sol,
                            current_token_price_usd=event.price_usd,
                            data_freshness_sec=event.freshness_seconds,
                        )
                    except Exception as e:
                        logger.debug("Live proposal creation skipped: %s", e)
        elif consensus.final_decision == AgentDecision.VETO:
            await self.token_radar.advance_lifecycle(
                event.token_mint,
                TokenLifecycleState.REJECTED,
                consensus.chief_reason,
            )
        else:
            if current_state == TokenLifecycleState.OBSERVED:
                await self.token_radar.advance_lifecycle(
                    event.token_mint,
                    TokenLifecycleState.ANALYZED,
                    consensus.chief_reason,
                )

        fill_elapsed_ms = (time.perf_counter() - t_fill_start) * 1000.0
        self.health.latency_paper_fill.record(fill_elapsed_ms)

        # Stage 8: Real-time WebSocket Broadcast
        t_ws_start = time.perf_counter()
        if self._ws_broadcast_callback:
            try:
                latest_portfolio = await self.repository.get_latest_portfolio_snapshot()
                ws_payload = {
                    "type": "PIPELINE_UPDATE",
                    "timestamp": now,
                    "event": event.model_dump(),
                    "decision": consensus.model_dump(),
                    "whale_convergence": convergence.model_dump(),
                    "portfolio": latest_portfolio.model_dump() if latest_portfolio else None,
                    "open_positions": [p.model_dump() for p in self.positions.get_open_positions()],
                    "e2e_latency_ms": round((time.perf_counter() - e2e_start_mono) * 1000.0, 2),
                }
                await self._ws_broadcast_callback(ws_payload)
            except Exception as e:
                logger.error("Error broadcasting to WebSockets: %s", e)

        ws_elapsed_ms = (time.perf_counter() - t_ws_start) * 1000.0
        self.health.latency_ws_broadcast.record(ws_elapsed_ms)

        # Stage 9: End-to-End Latency
        e2e_latency_ms = (time.perf_counter() - e2e_start_mono) * 1000.0
        self.health.latency_end_to_end.record(e2e_latency_ms)
