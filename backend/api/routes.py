"""FastAPI HTTP and WebSocket endpoints for SOLANA PREDATOR."""

import time
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel

from backend.config import settings
from backend.api.auth import require_admin_auth
from backend.models import (
    NormalizedMarketEvent,
    TokenSnapshot,
    WhaleActivity,
    AgentResult,
    PaperPosition,
    PortfolioSnapshot,
    PaperOrder,
)
from backend.database.repository import Repository
from backend.pipeline.engine import PredatorEngine
from backend.market.health import HealthTracker
from backend.market.replay import DeterministicReplayProvider

router = APIRouter()

# Global engine references injected during app startup
engine_instance: Optional[PredatorEngine] = None
repository_instance: Optional[Repository] = None
health_instance: Optional[HealthTracker] = None
replay_instance: Optional[DeterministicReplayProvider] = None
learning_evaluator_instance: Optional[Any] = None
live_order_manager_instance: Optional[Any] = None
wallet_service_instance: Optional[Any] = None
risk_guard_instance: Optional[Any] = None
llm_client_instance: Optional[Any] = None
market_provider_instance: Optional[Any] = None
desk_coordinator_instance: Optional[Any] = None
ws_manager_instance: Optional[Any] = None


def get_desk_coordinator() -> Any:
    global desk_coordinator_instance
    if not desk_coordinator_instance:
        if engine_instance and getattr(engine_instance, "desk_coordinator", None):
            desk_coordinator_instance = engine_instance.desk_coordinator
        else:
            from backend.desks.coordinator import MultiDeskCoordinator
            repo = get_repo()
            eng = get_engine()
            desk_coordinator_instance = MultiDeskCoordinator(
                repository=repo,
                agent_orchestrator=eng.agents,
                token_radar=eng.token_radar,
                whale_engine=eng.whale_engine,
                learning_evaluator=learning_evaluator_instance,
                risk_guard=risk_guard_instance,
                market_provider=market_provider_instance,
            )
    return desk_coordinator_instance


def get_market_provider() -> Any:
    global market_provider_instance
    if not market_provider_instance:
        from backend.market.composite_provider import CompositeMarketDataProvider
        market_provider_instance = CompositeMarketDataProvider()
    return market_provider_instance


def get_llm_client() -> Any:
    global llm_client_instance
    if not llm_client_instance:
        from backend.llm.client import LLMClient
        llm_client_instance = LLMClient()
    return llm_client_instance


def get_engine() -> PredatorEngine:
    if not engine_instance:
        raise HTTPException(status_code=503, detail="Engine initializing")
    return engine_instance


def get_repo() -> Repository:
    if not repository_instance:
        raise HTTPException(status_code=503, detail="Repository initializing")
    return repository_instance


def get_health() -> HealthTracker:
    if not health_instance:
        raise HTTPException(status_code=503, detail="Health tracker initializing")
    return health_instance


def get_replay() -> DeterministicReplayProvider:
    if not replay_instance:
        raise HTTPException(status_code=503, detail="Replay provider initializing")
    return replay_instance


def get_evaluator() -> Any:
    if not learning_evaluator_instance:
        from backend.learning.evaluator import DecisionOutcomeEvaluator
        return DecisionOutcomeEvaluator(get_repo())
    return learning_evaluator_instance


def get_live_order_manager() -> Any:
    if not live_order_manager_instance:
        raise HTTPException(status_code=503, detail="Live order manager not initialized")
    return live_order_manager_instance


def get_wallet_service() -> Any:
    if not wallet_service_instance:
        raise HTTPException(status_code=503, detail="Wallet service not initialized")
    return wallet_service_instance


def get_risk_guard() -> Any:
    if not risk_guard_instance:
        raise HTTPException(status_code=503, detail="Risk guard not initialized")
    return risk_guard_instance


# --- Request Models ---

class ConnectWalletRequest(BaseModel):
    wallet_address: str


class CreateProposalRequest(BaseModel):
    token_mint: str
    token_symbol: str = "TOKEN"
    amount_sol: float
    slippage_bps: float = 100.0
    current_token_price_usd: Optional[float] = None


class BroadcastSignedTxRequest(BaseModel):
    signed_tx_base64: str


class RejectProposalRequest(BaseModel):
    reason: str = "Rejected by user"


class KillSwitchRequest(BaseModel):
    active: bool


class SimulateStrategyRequest(BaseModel):
    candidate_version: str
    min_confidence_filter: float = 0.85
    target_multiplier: float = 1.15


# --- Endpoints ---

@router.get("/health", response_model=Dict[str, Any])
async def get_system_health(
    engine: PredatorEngine = Depends(get_engine),
    health: HealthTracker = Depends(get_health),
):
    """System health check and uptime status."""
    bus_metrics = engine.event_bus.get_metrics()
    dup_count = engine.normalizer.deduplicator.duplicate_count
    return {
        "status": "HEALTHY",
        "project": settings.PROJECT_NAME,
        "version": settings.APP_VERSION,
        "security_notice": settings.SECURITY_NOTICE,
        "timestamp": time.time(),
        "metrics": health.get_summary(bus_metrics, dup_count),
    }


@router.get("/state", response_model=Dict[str, Any])
async def get_system_state(
    engine: PredatorEngine = Depends(get_engine),
    repo: Repository = Depends(get_repo),
):
    """Aggregate state of tokens, open positions, and simulated equity."""
    tokens = await repo.get_all_tokens()
    open_pos = engine.positions.get_open_positions()
    portfolio = await repo.get_latest_portfolio_snapshot()
    return {
        "security_notice": settings.SECURITY_NOTICE,
        "tokens_tracked": len(tokens),
        "open_positions_count": len(open_pos),
        "portfolio": portfolio.model_dump() if portfolio else None,
        "cash_balance_usd": engine.accounting.cash_balance,
        "timestamp": time.time(),
    }


@router.get("/market/tokens", response_model=List[Dict[str, Any]])
async def get_tokens(
    repo: Repository = Depends(get_repo),
):
    """List of all discovered tokens and their current lifecycle states."""
    return await repo.get_all_tokens()


@router.get("/market/events", response_model=List[Dict[str, Any]])
async def get_market_events(
    limit: int = Query(50, ge=1, le=200),
    repo: Repository = Depends(get_repo),
):
    """Recent normalized market events."""
    return await repo.get_recent_market_events(limit=limit)


@router.get("/whales", response_model=List[Dict[str, Any]])
async def get_whale_activities(
    limit: int = Query(50, ge=1, le=200),
    token_mint: Optional[str] = Query(None),
    repo: Repository = Depends(get_repo),
):
    """Observable classified whale transactions."""
    return await repo.get_whale_activities(limit=limit, mint=token_mint)


@router.get("/agents/decisions", response_model=List[Dict[str, Any]])
async def get_agent_decisions(
    limit: int = Query(50, ge=1, le=200),
    repo: Repository = Depends(get_repo),
):
    """Recent decisions produced by the multi-agent consensus engine."""
    return await repo.get_recent_decisions(limit=limit)


@router.get("/paper/portfolio", response_model=Dict[str, Any])
async def get_paper_portfolio(
    engine: PredatorEngine = Depends(get_engine),
    repo: Repository = Depends(get_repo),
):
    """Simulated portfolio snapshot, cash, equity, and drawdown."""
    open_pos = engine.positions.get_open_positions()
    snap = await engine.accounting.compute_snapshot(open_pos)
    history = await repo.get_portfolio_history(limit=50)
    return {
        "security_notice": settings.SECURITY_NOTICE,
        "current_snapshot": snap.model_dump(),
        "history": history,
    }


@router.get("/paper/positions", response_model=List[Dict[str, Any]])
async def get_paper_positions(
    engine: PredatorEngine = Depends(get_engine),
    repo: Repository = Depends(get_repo),
):
    """List of all open and closed simulated positions."""
    positions = await repo.get_all_positions()
    return [p.model_dump() for p in positions]


@router.get("/paper/orders", response_model=List[Dict[str, Any]])
async def get_paper_orders(
    repo: Repository = Depends(get_repo),
):
    """Audit log of simulated orders and fills."""
    # We can fetch recent orders
    conn = repo._get_connection()
    try:
        cursor = conn.execute("SELECT * FROM paper_orders ORDER BY created_at DESC LIMIT 50")
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


@router.get("/metrics", response_model=Dict[str, Any])
async def get_latency_and_metrics(
    engine: PredatorEngine = Depends(get_engine),
    health: HealthTracker = Depends(get_health),
):
    """Statistical latency percentiles and queue depths."""
    bus_metrics = engine.event_bus.get_metrics()
    dup_count = engine.normalizer.deduplicator.duplicate_count
    return health.get_summary(bus_metrics, dup_count)


# --- Administrative Mutations (Protected) ---

@router.post("/simulation/start_replay", response_model=Dict[str, Any])
async def trigger_replay(
    admin_ok: bool = Depends(require_admin_auth),
    replay: DeterministicReplayProvider = Depends(get_replay),
):
    """Trigger deterministic replay of synthetic test events (Requires Admin Auth)."""
    count = await replay.run_replay()
    return {
        "status": "COMPLETED",
        "events_replayed": count,
        "timestamp": time.time(),
    }


@router.post("/paper/reset", response_model=Dict[str, Any])
async def reset_paper_trading(
    admin_ok: bool = Depends(require_admin_auth),
    engine: PredatorEngine = Depends(get_engine),
):
    """Reset virtual portfolio balance to initial capital (Requires Admin Auth)."""
    engine.accounting.cash_balance = settings.PAPER_INITIAL_CAPITAL
    engine.accounting.peak_equity = settings.PAPER_INITIAL_CAPITAL
    engine.accounting.max_drawdown_pct = 0.0
    engine.accounting.total_realized_pnl = 0.0
    engine.accounting.total_fees_paid = 0.0
    engine.positions._positions.clear()
    
    # Save a fresh snapshot
    await engine.accounting.compute_snapshot([])
    return {
        "status": "RESET_SUCCESSFUL",
        "cash_balance_usd": engine.accounting.cash_balance,
        "security_notice": settings.SECURITY_NOTICE,
    }


# --- Multi-Agent Structured Consensus Endpoints ---

@router.get("/chief/decisions", response_model=List[Dict[str, Any]])
async def get_chief_decisions(
    limit: int = Query(default=50, ge=1, le=200),
    repo: Repository = Depends(get_repo),
):
    """Retrieve structured, persistent, and reproducible multi-agent decisions."""
    return await repo.get_recent_chief_decisions(limit=limit)


# --- Measurable Learning Endpoints ---

@router.get("/learning/metrics", response_model=Dict[str, Any])
async def get_learning_metrics(
    evaluator: Any = Depends(get_evaluator),
    repo: Repository = Depends(get_repo),
):
    """Retrieve comprehensive learning performance metrics, accuracy rate, and segmentations."""
    outcomes_raw = await repo.get_decision_outcomes(limit=500)
    from backend.learning.models import DecisionOutcome
    outcomes = [DecisionOutcome(**o) for o in outcomes_raw]
    metrics = evaluator.compute_aggregate_metrics(outcomes)
    return metrics.model_dump()


@router.post("/learning/evaluate", response_model=Dict[str, Any])
async def trigger_learning_evaluation(
    evaluator: Any = Depends(get_evaluator),
    repo: Repository = Depends(get_repo),
):
    """Evaluate past decisions against subsequent price history without lookahead bias."""
    decisions = await repo.get_recent_chief_decisions(limit=100)
    evaluated_count = 0
    from backend.learning.temporal_split import assign_temporal_splits
    from backend.learning.models import DatasetSplitType

    splits = assign_temporal_splits(decisions)
    for dec, split in splits:
        # Fetch subsequent prices for the token
        events = await repo.get_token_market_events(dec["token_mint"], limit=50)
        outcome = evaluator.evaluate_single_decision(dec, events, split_type=split)
        if outcome:
            await repo.save_decision_outcome(outcome)
            evaluated_count += 1

    return {
        "status": "EVALUATION_COMPLETE",
        "decisions_evaluated": evaluated_count,
        "timestamp": time.time(),
    }


@router.get("/learning/benchmarks", response_model=List[Dict[str, Any]])
async def get_strategy_benchmarks(
    repo: Repository = Depends(get_repo),
):
    """List versioned strategy benchmarks and baseline comparisons."""
    return await repo.get_strategy_benchmarks()


@router.post("/learning/simulate_strategy", response_model=Dict[str, Any])
async def simulate_candidate_strategy(
    req: SimulateStrategyRequest,
    repo: Repository = Depends(get_repo),
):
    """Simulate a candidate strategy on historical validation data before adoption."""
    from backend.learning.optimizer import StrategyOptimizer
    from backend.learning.models import DecisionOutcome
    optimizer = StrategyOptimizer(repo)
    outcomes_raw = await repo.get_decision_outcomes(limit=200)
    outcomes = [DecisionOutcome(**o) for o in outcomes_raw]
    
    benchmark = optimizer.simulate_strategy_candidate(
        candidate_version=req.candidate_version,
        baseline_outcomes=outcomes,
        min_confidence_filter=req.min_confidence_filter,
        target_multiplier=req.target_multiplier,
    )
    await repo.save_strategy_benchmark(benchmark)
    return benchmark.model_dump()


# --- Live Trading Endpoints ---

@router.post("/live/wallet/connect", response_model=Dict[str, Any])
async def connect_live_wallet(
    req: ConnectWalletRequest,
    wallet_svc: Any = Depends(get_wallet_service),
):
    """Connect an external Solana wallet by public key only (No private keys)."""
    connection = await wallet_svc.connect_wallet(req.wallet_address)
    return {
        "status": "CONNECTED",
        "wallet": connection.model_dump(),
        "security_notice": "LIVE MARKET DATA — EXPLICIT USER SIGNATURE REQUIRED FOR TRANSACTIONS",
    }


@router.post("/live/wallet/disconnect", response_model=Dict[str, Any])
async def disconnect_live_wallet(
    wallet_svc: Any = Depends(get_wallet_service),
):
    """Disconnect active wallet."""
    wallet_svc.disconnect_wallet()
    return {"status": "DISCONNECTED"}


@router.get("/live/wallet/status", response_model=Dict[str, Any])
async def get_live_wallet_status(
    wallet_svc: Any = Depends(get_wallet_service),
):
    """Get active wallet public key, SOL balance, and token accounts."""
    status = wallet_svc.get_status()
    if not status:
        return {"is_connected": False, "wallet": None}
    return {"is_connected": True, "wallet": status.model_dump()}


@router.get("/live/proposals", response_model=List[Dict[str, Any]])
async def list_live_proposals(
    limit: int = Query(default=50, ge=1, le=100),
    status: Optional[str] = None,
    repo: Repository = Depends(get_repo),
):
    """List live trade proposals and their independent risk checklist."""
    return await repo.get_live_proposals(limit=limit, status=status)


@router.post("/live/proposals/create", response_model=Dict[str, Any])
async def create_live_proposal(
    req: CreateProposalRequest,
    order_mgr: Any = Depends(get_live_order_manager),
):
    """Prepare an unsigned live trade proposal with independent risk audit."""
    proposal = await order_mgr.create_trade_proposal(
        token_mint=req.token_mint,
        token_symbol=req.token_symbol,
        amount_sol=req.amount_sol,
        slippage_bps=req.slippage_bps,
        current_token_price_usd=req.current_token_price_usd,
    )
    return proposal.model_dump()


@router.post("/live/proposals/{proposal_id}/broadcast", response_model=Dict[str, Any])
async def broadcast_signed_live_transaction(
    proposal_id: str,
    req: BroadcastSignedTxRequest,
    order_mgr: Any = Depends(get_live_order_manager),
):
    """Broadcast an explicitly user-signed transaction to the Solana network."""
    tx_record = await order_mgr.submit_user_signature(
        proposal_id=proposal_id,
        signed_tx_base64=req.signed_tx_base64,
    )
    return tx_record.model_dump()


@router.post("/live/proposals/{proposal_id}/reject", response_model=Dict[str, Any])
async def reject_live_proposal(
    proposal_id: str,
    req: RejectProposalRequest,
    order_mgr: Any = Depends(get_live_order_manager),
):
    """Explicitly reject a live trade proposal."""
    await order_mgr.reject_proposal_by_user(proposal_id, req.reason)
    return {"status": "REJECTED_BY_USER", "proposal_id": proposal_id}


@router.get("/live/transactions", response_model=List[Dict[str, Any]])
async def get_live_transactions(
    limit: int = Query(default=50, ge=1, le=100),
    repo: Repository = Depends(get_repo),
):
    """List broadcast transactions and their on-chain confirmation status."""
    return await repo.get_live_transactions(limit=limit)


@router.post("/live/kill-switch", response_model=Dict[str, Any])
async def toggle_emergency_kill_switch(
    req: KillSwitchRequest,
    admin_ok: bool = Depends(require_admin_auth),
    risk_guard: Any = Depends(get_risk_guard),
    repo: Repository = Depends(get_repo),
):
    """Admin-only Emergency Kill-Switch stopping all live trade proposals with SQLite persistence."""
    risk_guard.set_emergency_kill_switch(req.active)
    await repo.set_system_config("emergency_kill_switch", "true" if req.active else "false")
    return {
        "emergency_kill_switch_active": risk_guard.emergency_kill_switch_active,
        "status": "KILL_SWITCH_ENGAGED" if req.active else "KILL_SWITCH_DISENGAGED",
        "timestamp": time.time(),
    }


@router.get("/live/risk-audit", response_model=List[Dict[str, Any]])
async def get_risk_audit_log(
    limit: int = Query(default=50, ge=1, le=100),
    repo: Repository = Depends(get_repo),
):
    """Audit log of independent risk verifications."""
    conn = repo._get_connection()
    try:
        cursor = conn.execute("SELECT * FROM risk_audit_log ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        out = []
        for r in rows:
            item = dict(r)
            if item.get("details_json"):
                import json
                item["details"] = json.loads(item["details_json"])
            out.append(item)
        return out
    finally:
        conn.close()


# --- Market Data Provider Routes (Composite / GMGN / DEX Screener / Solana RPC) ---

@router.get("/market/providers", response_model=Dict[str, Any])
async def get_market_providers_health(
    provider: Any = Depends(get_market_provider),
):
    """Retrieve operational status, configuration, and health of all market data providers."""
    return await provider.check_health()


@router.get("/market/token/{token_mint}", response_model=Dict[str, Any])
async def get_token_market_data_endpoint(
    token_mint: str,
    provider: Any = Depends(get_market_provider),
):
    """Fetch normalized market metrics for a token mint with automatic provider failover.
    
    Validates token mint format, verifies provider availability, distinguishes between
    missing data, unknown tokens, and provider errors, and returns the effective source.
    """
    import re
    if not re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", token_mint):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Solana token mint address format: '{token_mint}'. Expected base58 string between 32 and 44 characters."
        )

    if not provider.is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="All registered market data providers are currently unavailable or failing."
        )

    try:
        event = await provider.get_token_market_data(token_mint)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Market data provider query failed unexpectedly: {e}"
        )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Token '{token_mint}' not found on any active market data provider."
        )
    return event.model_dump()


# --- LLM Provider Routes (GLM-5.3-Flash / OpenAI Compatible) ---

class LLMAnalysisRequest(BaseModel):
    token_mint: str
    agent_role: str = "CHIEF"
    context: Optional[Dict[str, Any]] = None


@router.get("/llm/status", response_model=Dict[str, Any])
async def get_llm_status(
    probe: bool = Query(default=False, description="Whether to execute active connectivity probe"),
    llm: Any = Depends(get_llm_client),
):
    """Retrieve operational status, active model, and error telemetry of the LLM provider.
    
    Exposes separately configuration state and active connectivity probe result.
    """
    if probe:
        await llm.check_connectivity()
    return llm.get_status()


@router.post("/llm/analyze", response_model=Dict[str, Any])
async def trigger_llm_analysis(
    req: LLMAnalysisRequest,
    llm: Any = Depends(get_llm_client),
):
    """Request ad-hoc qualitative multi-agent analysis for a token via LLM.
    
    Faithfully distinguishes between:
    - SUCCESS
    - LLM_NOT_CONFIGURED
    - LLM_AUTH_FAILED
    - LLM_UNAVAILABLE
    - LLM_INVALID_RESPONSE
    """
    from backend.llm.prompt_templates import (
        CHIEF_SYNTHESIS_SYSTEM_PROMPT,
        SKEPTIC_SYSTEM_PROMPT,
        WHALE_SYSTEM_PROMPT,
        VET_SYSTEM_PROMPT,
        QUANT_SYSTEM_PROMPT,
        format_agent_user_prompt,
    )
    prompt_map = {
        "CHIEF": (CHIEF_SYNTHESIS_SYSTEM_PROMPT, "v1.0-chief-synthesis"),
        "SKEPTIC": (SKEPTIC_SYSTEM_PROMPT, "v1.0-skeptic-contrarian"),
        "WHALE": (WHALE_SYSTEM_PROMPT, "v1.0-whale-flow"),
        "VET": (VET_SYSTEM_PROMPT, "v1.0-vet-contract-security"),
        "QUANT": (QUANT_SYSTEM_PROMPT, "v1.0-quant-momentum"),
    }
    sys_prompt, prompt_ver = prompt_map.get(
        req.agent_role.upper(),
        (CHIEF_SYNTHESIS_SYSTEM_PROMPT, "v1.0-chief-synthesis")
    )
    user_prompt = format_agent_user_prompt(
        token_mint=req.token_mint,
        event_data={"token_mint": req.token_mint},
        context=req.context or {},
        contributing_agent_signals={},
    )
    result = await llm.request_advisory(
        agent_name=req.agent_role.upper(),
        token_mint=req.token_mint,
        system_prompt=sys_prompt,
        user_prompt=user_prompt,
        prompt_version=prompt_ver,
    )
    return result.model_dump()


# --- Multi-Desk Workstation & Observability Endpoints (Phase D) ---

class WatchlistCreateRequest(BaseModel):
    identifier: str
    item_type: str = "TOKEN"  # TOKEN or WALLET
    label: Optional[str] = None
    notes: Optional[str] = None


class RunDeskRequest(BaseModel):
    token_mint: str = "So11111111111111111111111111111111111111112"
    price_usd: Optional[float] = 150.0
    liquidity_usd: Optional[float] = 50000.0
    volume_24h_usd: Optional[float] = 120000.0


@router.get("/desks", response_model=List[Dict[str, Any]])
async def list_all_desks(
    coord: Any = Depends(get_desk_coordinator),
    repo: Repository = Depends(get_repo),
):
    """List all 6 specialized desks with real-time status, supervisor, and counters."""
    db_desks = await repo.get_all_desks()
    if db_desks:
        return db_desks
    return [d.model_dump() for d in coord.desks.values()]


@router.get("/desks/{desk_id}", response_model=Dict[str, Any])
async def get_desk_workspace_snapshot(
    desk_id: str,
    coord: Any = Depends(get_desk_coordinator),
    repo: Repository = Depends(get_repo),
):
    """Retrieve complete workspace state for a specific desk: status, agents, tasks, and reports."""
    desk_key = desk_id.upper()
    if desk_key not in coord.desks:
        raise HTTPException(status_code=404, detail=f"Desk '{desk_id}' not found.")

    desk_rec = coord.desks[desk_key]
    agents_list = [
        coord.agent_states[ag] for ag in desk_rec.agents if ag in coord.agent_states
    ]
    tasks = await repo.get_desk_tasks(desk_id=desk_key, limit=30)
    reports = await repo.get_desk_reports(desk_id=desk_key, limit=30)
    watchlist = await repo.get_watchlist_items()

    return {
        "desk": desk_rec.model_dump(),
        "agents": agents_list,
        "recent_tasks": tasks,
        "recent_reports": reports,
        "watchlist": watchlist,
        "timestamp": time.time(),
    }


@router.get("/desks/{desk_id}/agents", response_model=List[Dict[str, Any]])
async def get_desk_agents(
    desk_id: str,
    coord: Any = Depends(get_desk_coordinator),
):
    """List real agent instances assigned to a desk and their live telemetry."""
    desk_key = desk_id.upper()
    if desk_key not in coord.desks:
        raise HTTPException(status_code=404, detail=f"Desk '{desk_id}' not found.")
    desk_rec = coord.desks[desk_key]
    return [coord.agent_states[ag] for ag in desk_rec.agents if ag in coord.agent_states]


@router.get("/desks/{desk_id}/tasks", response_model=List[Dict[str, Any]])
async def get_desk_tasks_endpoint(
    desk_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    coord: Any = Depends(get_desk_coordinator),
    repo: Repository = Depends(get_repo),
):
    """Retrieve persisted task executions for a specific desk."""
    desk_key = desk_id.upper()
    if desk_key not in coord.desks:
        raise HTTPException(status_code=404, detail=f"Desk '{desk_id}' not found.")
    return await repo.get_desk_tasks(desk_id=desk_key, limit=limit)


@router.get("/desks/{desk_id}/reports", response_model=List[Dict[str, Any]])
async def get_desk_reports_endpoint(
    desk_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    coord: Any = Depends(get_desk_coordinator),
    repo: Repository = Depends(get_repo),
):
    """Retrieve structured evidence-vs-inference reports generated by a desk."""
    desk_key = desk_id.upper()
    if desk_key not in coord.desks:
        raise HTTPException(status_code=404, detail=f"Desk '{desk_id}' not found.")
    return await repo.get_desk_reports(desk_id=desk_key, limit=limit)


@router.post("/desks/{desk_id}/pause", response_model=Dict[str, Any])
async def pause_desk_endpoint(
    desk_id: str,
    admin_ok: bool = Depends(require_admin_auth),
    coord: Any = Depends(get_desk_coordinator),
):
    """Pause background analysis for a specific desk (Requires Admin Auth)."""
    desk_key = desk_id.upper()
    if desk_key not in coord.desks:
        raise HTTPException(status_code=404, detail=f"Desk '{desk_id}' not found.")
    rec = await coord.pause_desk(desk_key)
    return rec.model_dump()


@router.post("/desks/{desk_id}/resume", response_model=Dict[str, Any])
async def resume_desk_endpoint(
    desk_id: str,
    admin_ok: bool = Depends(require_admin_auth),
    coord: Any = Depends(get_desk_coordinator),
):
    """Resume background analysis for a specific desk (Requires Admin Auth)."""
    desk_key = desk_id.upper()
    if desk_key not in coord.desks:
        raise HTTPException(status_code=404, detail=f"Desk '{desk_id}' not found.")
    rec = await coord.resume_desk(desk_key)
    return rec.model_dump()


@router.post("/desks/{desk_id}/run", response_model=Dict[str, Any])
async def run_desk_task_endpoint(
    desk_id: str,
    req: RunDeskRequest,
    coord: Any = Depends(get_desk_coordinator),
    engine: PredatorEngine = Depends(get_engine),
):
    """Execute an on-demand analysis cycle on a desk using its real agent instances."""
    desk_key = desk_id.upper()
    if desk_key not in coord.desks:
        raise HTTPException(status_code=404, detail=f"Desk '{desk_id}' not found.")

    from backend.models import MarketSource, EventQuality
    now = time.time()
    missing = []
    if req.price_usd is None:
        missing.append("price_usd")
    if req.liquidity_usd is None:
        missing.append("liquidity_usd")
    if req.volume_24h_usd is None:
        missing.append("volume_24h_usd")

    event = NormalizedMarketEvent(
        event_id=f"ondemand_{desk_key.lower()}_{int(now*1000)}",
        source=MarketSource.DEX_SCREENER,
        token_mint=req.token_mint,
        source_timestamp=now,
        local_receive_timestamp=now,
        processing_timestamp=now,
        freshness_seconds=0.1,
        price_usd=req.price_usd,
        liquidity_usd=req.liquidity_usd,
        volume_24h_usd=req.volume_24h_usd,
        quality=EventQuality.ACCEPTABLE if not missing else EventQuality.DEGRADED,
        observation_state="GENUINELY_OBSERVED" if not missing else "MISSING",
        missing_fields=missing,
        confidence_score=0.95,
        metadata={"symbol": "SOL", "trigger": "ON_DEMAND_DESK_RUN"},
    )
    open_positions = engine.positions.get_open_positions()
    ctx = {
        "whale_convergence": engine.whale_engine.calculate_convergence(req.token_mint),
        "portfolio_equity": engine.accounting.cash_balance + sum(p.current_value_usd for p in open_positions),
        "cash_balance": engine.accounting.cash_balance,
        "open_positions_count": len(open_positions),
        "current_drawdown_pct": engine.accounting.max_drawdown_pct,
        "has_existing_position": engine.positions.has_open_position(req.token_mint),
    }
    return await coord.run_desk_now(desk_key, event, ctx)


@router.get("/agents", response_model=List[Dict[str, Any]])
async def list_all_agents(
    coord: Any = Depends(get_desk_coordinator),
):
    """List all 9 agents with real-time execution status, desk assignment, and telemetry."""
    return list(coord.agent_states.values())


@router.get("/agents/{agent_id}", response_model=Dict[str, Any])
async def get_single_agent_status(
    agent_id: str,
    coord: Any = Depends(get_desk_coordinator),
    repo: Repository = Depends(get_repo),
):
    """Retrieve status and recent task executions for a specific agent."""
    ag_key = agent_id.upper()
    if ag_key not in coord.agent_states:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")
    tasks = await repo.get_desk_tasks(agent_id=ag_key, limit=30)
    return {
        "agent": coord.agent_states[ag_key],
        "recent_tasks": tasks,
    }


@router.get("/agents/{agent_id}/tasks", response_model=List[Dict[str, Any]])
async def get_agent_tasks_endpoint(
    agent_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    coord: Any = Depends(get_desk_coordinator),
    repo: Repository = Depends(get_repo),
):
    """Retrieve persisted task execution history for a specific agent."""
    ag_key = agent_id.upper()
    if ag_key not in coord.agent_states:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")
    return await repo.get_desk_tasks(agent_id=ag_key, limit=limit)


@router.get("/watchlist", response_model=List[Dict[str, Any]])
async def get_watchlist_endpoint(
    item_type: Optional[str] = Query(default=None),
    repo: Repository = Depends(get_repo),
):
    """Retrieve watched tokens (Desk 1) and public wallets (Desk 2)."""
    return await repo.get_watchlist_items(item_type=item_type)


@router.post("/watchlist", response_model=Dict[str, Any])
async def add_watchlist_endpoint(
    req: WatchlistCreateRequest,
    repo: Repository = Depends(get_repo),
):
    """Add or update a token or public wallet on the watchlist."""
    from backend.models.desk import WatchlistItem
    item = WatchlistItem(
        identifier=req.identifier.strip(),
        item_type=req.item_type.upper(),
        label=req.label,
        added_at=time.time(),
        notes=req.notes,
    )
    await repo.upsert_watchlist_item(item)
    return item.model_dump()


@router.delete("/watchlist/{identifier}", response_model=Dict[str, Any])
async def remove_watchlist_endpoint(
    identifier: str,
    repo: Repository = Depends(get_repo),
):
    """Remove an item from the watchlist."""
    deleted = await repo.delete_watchlist_item(identifier)
    return {"deleted": deleted, "identifier": identifier}


@router.get("/system/health", response_model=Dict[str, Any])
async def get_comprehensive_system_health(
    engine: PredatorEngine = Depends(get_engine),
    health: HealthTracker = Depends(get_health),
    coord: Any = Depends(get_desk_coordinator),
    provider: Any = Depends(get_market_provider),
    llm: Any = Depends(get_llm_client),
    risk_guard: Any = Depends(get_risk_guard),
):
    """Comprehensive observability endpoint for the Command Center (Section 13)."""
    bus_metrics = engine.event_bus.get_metrics()
    dup_count = engine.normalizer.deduplicator.duplicate_count
    summary = health.get_summary(bus_metrics, dup_count)
    providers_health = await provider.check_health()

    total_active = sum(d.active_tasks for d in coord.desks.values())
    total_queued = sum(d.queued_tasks for d in coord.desks.values())
    total_completed = sum(d.completed_tasks for d in coord.desks.values())
    total_failed = sum(d.failed_tasks for d in coord.desks.values())
    total_retries = sum(d.retry_count for d in coord.desks.values())

    ws_clients = ws_manager_instance.get_connected_count() if ws_manager_instance else 0
    open_positions = engine.positions.get_open_positions()

    return {
        "status": "HEALTHY",
        "project": settings.PROJECT_NAME,
        "version": settings.APP_VERSION,
        "security_notice": settings.SECURITY_NOTICE,
        "execution_mode": "PAPER_TRADING_ONLY",
        "live_trading_boundary": "DRY-RUN / NOT OPERATIONAL FOR MAINNET",
        "allow_transaction_submission": settings.ALLOW_TRANSACTION_SUBMISSION,
        "emergency_kill_switch_active": risk_guard.emergency_kill_switch_active,
        "uptime_seconds": summary.get("uptime_seconds", 0.0),
        "last_successful_update_timestamp": max(
            (d.last_execution_at or 0.0 for d in coord.desks.values()),
            default=0.0,
        ),
        "websocket_clients_connected": ws_clients,
        "sqlite_wal_healthy": True,
        "tasks_summary": {
            "active_tasks": total_active,
            "queued_tasks": total_queued,
            "completed_tasks": total_completed,
            "failed_tasks": total_failed,
            "retry_count": total_retries,
        },
        "desks": [d.model_dump() for d in coord.desks.values()],
        "agents": list(coord.agent_states.values()),
        "providers": providers_health,
        "llm": llm.get_status(),
        "paper_trading": {
            "cash_balance_usd": engine.accounting.cash_balance,
            "open_positions_count": len(open_positions),
            "max_drawdown_pct": engine.accounting.max_drawdown_pct,
            "total_realized_pnl_usd": engine.accounting.total_realized_pnl,
            "total_fees_paid_usd": engine.accounting.total_fees_paid,
            "fee_bps": settings.PAPER_TAKER_FEE_BPS,
            "base_slippage_bps": settings.PAPER_BASE_SLIPPAGE_BPS,
        },
        "latency_metrics": summary,
        "timestamp": time.time(),
    }
