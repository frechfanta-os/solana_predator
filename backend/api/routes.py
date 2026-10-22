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
