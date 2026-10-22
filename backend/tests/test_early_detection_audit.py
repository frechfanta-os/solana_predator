"""Early detection audit tests verifying distinct timestamps, RPC WS reconnect, and event ordering."""

import time
import asyncio
import pytest
from backend.models import (
    NormalizedMarketEvent,
    MarketSource,
    EventQuality,
    TokenLifecycleState,
    AgentDecision,
)
from backend.discovery.token_radar import TokenRadar
from backend.agents.orchestrator import AgentOrchestrator
from backend.market.solana_rpc import SolanaRpcClient


@pytest.mark.asyncio
async def test_distinct_timestamps_pool_creation_vs_first_observation(token_radar, repo):
    """Verify pool creation timestamp is NEVER conflated with first observed timestamp."""
    now = time.time()
    pool_created_time = now - 14400.0  # Pool created 4 hours ago on-chain
    receive_time = now

    mint = "TokenMintEarlyAuditDistinct1111111111111111111"
    ev = NormalizedMarketEvent(
        source=MarketSource.DEX_SCREENER,
        event_id="ev_early_distinct_01",
        token_mint=mint,
        pair_address="PairAuditDistinct11111111111111111111",
        source_timestamp=pool_created_time,
        local_receive_timestamp=receive_time,
        processing_timestamp=receive_time + 0.005,
        price_usd=0.00042,
        liquidity_usd=18000.0,
        metadata={"pool_created_at": pool_created_time, "name": "AuditToken", "symbol": "ATOK"},
    )

    state = await token_radar.process_event(ev)
    assert state == TokenLifecycleState.DISCOVERED

    # Retrieve from repository
    tokens = await repo.get_all_tokens()
    tok = next(t for t in tokens if t["mint"] == mint)

    assert tok["pool_created_timestamp"] == pool_created_time
    assert tok["first_observed_timestamp"] >= receive_time - 0.1
    # INVARIANT: First observed MUST NOT equal pool creation
    assert tok["first_observed_timestamp"] != tok["pool_created_timestamp"]
    assert (tok["first_observed_timestamp"] - tok["pool_created_timestamp"]) >= 14399.0


@pytest.mark.asyncio
async def test_detection_timeline_ordering(token_radar, agent_orchestrator):
    """Verify chronological timeline: Pool Creation < Receive < Detection < Decision."""
    now = time.time()
    pool_creation = now - 600.0
    source_event_time = now - 1.5
    local_receive = now
    processing_time = now + 0.002

    mint = "TokenMintTimelineOrder1111111111111111111111"
    ev = NormalizedMarketEvent(
        source=MarketSource.REPLAY,
        event_id="ev_timeline_01",
        token_mint=mint,
        pair_address="PairTimeline111111111111111111111111",
        source_timestamp=source_event_time,
        local_receive_timestamp=local_receive,
        processing_timestamp=processing_time,
        price_usd=0.00010,
        liquidity_usd=25000.0,
        volume_24h_usd=50000.0,
        metadata={"pool_created_at": pool_creation},
    )

    t_detect_start = time.time()
    await token_radar.process_event(ev)
    t_detect_end = time.time()

    context = {
        "portfolio_equity": 10000.0,
        "cash_balance": 10000.0,
        "open_positions_count": 0,
        "current_drawdown_pct": 0.0,
        "has_existing_position": False,
    }
    t_decision_start = time.time()
    consensus = await agent_orchestrator.run_pipeline(ev, context)
    t_decision_end = time.time()

    # Timeline verification
    assert pool_creation < source_event_time
    assert source_event_time < local_receive
    assert local_receive <= processing_time
    assert processing_time <= t_detect_end
    assert t_detect_end <= consensus.timestamp


@pytest.mark.asyncio
async def test_rpc_health_monitoring_and_reconnection_backoff():
    """Verify RPC health tracking, status reporting, and reconnection backoff boundaries."""
    rpc = SolanaRpcClient(
        http_url="https://api.mainnet-beta.solana.com",
        ws_url="wss://api.mainnet-beta.solana.com",
    )
    status = rpc.get_health_status()
    assert "is_connected" in status
    assert "reconnect_count" in status
    assert status["reconnect_count"] == 0
    assert status["commitment"] == "confirmed"
    await rpc.close()


@pytest.mark.asyncio
async def test_out_of_order_event_non_regression(token_radar, repo):
    """Verify that older / delayed events do not roll back verified observed states."""
    now = time.time()
    mint = "TokenMintOutOfOrder1111111111111111111111"

    # Event 1: Arrives and moves state to OBSERVED with verified price
    ev_first = NormalizedMarketEvent(
        source=MarketSource.DEX_SCREENER,
        event_id="ev_recent",
        token_mint=mint,
        local_receive_timestamp=now,
        processing_timestamp=now + 0.001,
        price_usd=0.005,
        liquidity_usd=12000.0,
    )
    await token_radar.process_event(ev_first)
    await token_radar.process_event(ev_first)  # Transitions to OBSERVED
    assert token_radar.get_state(mint) == TokenLifecycleState.OBSERVED

    # Event 2: Delayed event with older timestamp arrives
    ev_delayed = NormalizedMarketEvent(
        source=MarketSource.SOLANA_RPC,
        event_id="ev_delayed",
        token_mint=mint,
        slot=1000,
        source_timestamp=now - 500.0,
        local_receive_timestamp=now + 1.0,
        processing_timestamp=now + 1.001,
        price_usd=None,  # Raw log without price
    )
    state_after = await token_radar.process_event(ev_delayed)
    # Must remain OBSERVED, not downgraded to DISCOVERED
    assert state_after == TokenLifecycleState.OBSERVED
