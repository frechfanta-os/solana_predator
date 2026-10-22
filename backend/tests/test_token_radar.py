"""Tests for Token Discovery Radar and state lifecycle transitions."""

import time
import pytest
from backend.discovery.token_radar import TokenRadar
from backend.models import NormalizedMarketEvent, MarketSource, TokenLifecycleState


@pytest.mark.asyncio
async def test_token_discovery_and_observation_lifecycle(token_radar, repo):
    now = time.time()
    mint = "TestMintToken1111111111111111111111111111111"

    # 1. First event: token discovered
    ev1 = NormalizedMarketEvent(
        source=MarketSource.SOLANA_RPC,
        event_id="ev_init",
        token_mint=mint,
        local_receive_timestamp=now,
        processing_timestamp=now + 0.01,
        metadata={"pool_created_at": now - 300.0, "name": "TestToken", "symbol": "TEST"},
    )
    s1 = await token_radar.process_event(ev1)
    assert s1 == TokenLifecycleState.DISCOVERED
    assert token_radar.get_state(mint) == TokenLifecycleState.DISCOVERED

    # 2. Second event: price/liquidity verified -> OBSERVED
    ev2 = NormalizedMarketEvent(
        source=MarketSource.DEX_SCREENER,
        event_id="ev_obs",
        token_mint=mint,
        local_receive_timestamp=now + 1.0,
        processing_timestamp=now + 1.01,
        price_usd=0.0012,
        liquidity_usd=15000.0,
    )
    s2 = await token_radar.process_event(ev2)
    assert s2 == TokenLifecycleState.OBSERVED

    # 3. Transition to PAPER_CANDIDATE
    await token_radar.advance_lifecycle(mint, TokenLifecycleState.PAPER_CANDIDATE, "Chief consensus buy approval")
    assert token_radar.get_state(mint) == TokenLifecycleState.PAPER_CANDIDATE

    # Verify repository records
    tokens = await repo.get_all_tokens()
    matching = [t for t in tokens if t["mint"] == mint]
    assert len(matching) == 1
    assert matching[0]["current_lifecycle_state"] == TokenLifecycleState.PAPER_CANDIDATE.value
    assert matching[0]["first_observed_timestamp"] is not None
    assert matching[0]["pool_created_timestamp"] == (now - 300.0)
