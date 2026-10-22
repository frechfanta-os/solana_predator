"""Tests for Whale Intelligence classification and convergence calculation."""

import time
import pytest
from backend.whale.whale_intelligence import WhaleIntelligenceEngine
from backend.models import WhaleActivityType


@pytest.mark.asyncio
async def test_whale_activity_classification(whale_engine):
    sig = "sig_whale_test_001"
    wallet = "wha1e8sF3G5wK8eA9Z8oA2V4dE6mB1nC7xY9uL0kP3r"
    mint = "TokenMintWhaleTarget111111111111111111111111"

    # Classify swap
    act_swap = whale_engine.classify_raw_transaction(
        signature=sig,
        wallet_address=wallet,
        token_mint=mint,
        event_metadata={"swap_type": "BUY", "amount_usd": 5000.0, "amount_tokens": 100000.0},
    )
    assert act_swap.activity_type == WhaleActivityType.SWAP
    assert act_swap.amount_usd == 5000.0

    # Record activity
    recorded = await whale_engine.record_activity(act_swap)
    assert recorded is True

    # Duplicate signature record should return False
    dup_recorded = await whale_engine.record_activity(act_swap)
    assert dup_recorded is False


@pytest.mark.asyncio
async def test_whale_convergence_and_cluster_detection(whale_engine):
    mint = "TokenMintConvergence111111111111111111111111"
    
    # 2 independent whales buying
    act1 = whale_engine.classify_raw_transaction(
        signature="sig_c1",
        wallet_address="wha1e8sF3G5wK8eA9Z8oA2V4dE6mB1nC7xY9uL0kP3r",
        token_mint=mint,
        event_metadata={"swap_type": "BUY", "amount_usd": 4000.0, "amount_tokens": 50000.0},
    )
    act2 = whale_engine.classify_raw_transaction(
        signature="sig_c2",
        wallet_address="wha2eN4mX9pQ2vR6tY8uW1zC3bK5dE7gH0jL4mP8sT2",
        token_mint=mint,
        event_metadata={"swap_type": "BUY", "amount_usd": 6000.0, "amount_tokens": 75000.0},
    )

    await whale_engine.record_activity(act1)
    await whale_engine.record_activity(act2)

    metrics = whale_engine.calculate_convergence(mint)
    assert metrics.unique_whales_active == 2
    assert metrics.buy_volume_usd == 10000.0
    assert metrics.sell_volume_usd == 0.0
    assert metrics.net_flow_usd == 10000.0
    assert metrics.convergence_score > 0.50
    assert metrics.is_correlated_cluster is False
