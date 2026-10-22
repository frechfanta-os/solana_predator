"""Tests for multi-agent output contracts and latency bounds."""

import time
import pytest
from backend.models import (
    NormalizedMarketEvent,
    MarketSource,
    AgentDecision,
    AgentName,
)
from backend.agents.orchestrator import AgentOrchestrator


@pytest.mark.asyncio
async def test_all_agents_return_validated_contract(agent_orchestrator):
    ev = NormalizedMarketEvent(
        source=MarketSource.SYNTHETIC,
        event_id="ev_agent_contract_test",
        token_mint="TokenMintContract11111111111111111111111111",
        pair_address="PairContract11111111111111111111111111",
        price_usd=0.00025,
        liquidity_usd=25000.0,
        volume_24h_usd=45000.0,
        local_receive_timestamp=100.0,
        processing_timestamp=100.1,
    )

    context = {
        "portfolio_equity": 10000.0,
        "cash_balance": 10000.0,
        "open_positions_count": 0,
        "current_drawdown_pct": 0.0,
        "has_existing_position": False,
    }

    consensus = await agent_orchestrator.run_pipeline(ev, context)
    assert consensus.consensus_id is not None
    assert consensus.token_mint == ev.token_mint
    assert consensus.processing_total_latency_ms >= 0.0

    # Verify each agent produced a contract
    required_agents = [
        AgentName.VET.value,
        AgentName.SCAN.value,
        AgentName.WHALE.value,
        AgentName.QUANT.value,
        AgentName.SKEPTIC.value,
        AgentName.SIZE.value,
        AgentName.RISK.value,
        AgentName.AUDIT.value,
    ]
    for name in required_agents:
        assert name in consensus.contributing_agents
        res = consensus.contributing_agents[name]
        assert res.agent_name.value == name
        assert res.processing_latency_ms >= 0.0
        assert res.confidence >= 0.0 and res.confidence <= 1.0
        assert res.decision in AgentDecision
