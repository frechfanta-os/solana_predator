"""
Technical validation tests for Multi-Agent Decision Engine (Step 2 & Step 7.1).
Tests structured decisions, reproducibility, SKEPTIC contradictions, RISK veto, and persistence.
"""
import pytest
import time
from backend.models import (
    NormalizedMarketEvent,
    MarketSource,
    AgentDecision,
    AgentName,
    ChiefConsensusRecord,
)
from backend.agents.orchestrator import AgentOrchestrator


@pytest.fixture
def sample_event():
    return NormalizedMarketEvent(
        source=MarketSource.SOLANA_RPC,
        event_id="ev_multi_agent_test_01",
        token_mint="TokenMintMultiAgent11111111111111111111111",
        pair_address="PairMultiAgent111111111111111111111111111",
        price_usd=1.25,
        liquidity_usd=50000.0,
        volume_24h_usd=80000.0,
        local_receive_timestamp=time.time(),
        processing_timestamp=time.time() + 0.001,
        signature="5SigTestEventForMultiAgents1111111111111111111111111111111111111",
    )


@pytest.fixture
def base_context():
    return {
        "portfolio_equity": 10000.0,
        "cash_balance": 10000.0,
        "open_positions_count": 0,
        "current_drawdown_pct": 0.0,
        "has_existing_position": False,
    }


@pytest.mark.asyncio
async def test_all_nine_agents_executed_in_pipeline(repo, sample_event, base_context):
    orchestrator = AgentOrchestrator(repository=repo)
    consensus = await orchestrator.run_pipeline(sample_event, base_context)

    assert consensus is not None
    assert isinstance(consensus, ChiefConsensusRecord)
    
    # CHIEF synthesizes the consensus, and all other 8 analytical agents contribute
    expected_contributing_agents = {
        AgentName.SCAN.value,
        AgentName.WHALE.value,
        AgentName.VET.value,
        AgentName.QUANT.value,
        AgentName.SKEPTIC.value,
        AgentName.SIZE.value,
        AgentName.RISK.value,
        AgentName.AUDIT.value,
    }
    present_agents = set(consensus.contributing_agents.keys())
    assert expected_contributing_agents.issubset(present_agents), f"Missing agents: {expected_contributing_agents - present_agents}"


@pytest.mark.asyncio
async def test_structured_decision_fields_completeness(repo, sample_event, base_context):
    orchestrator = AgentOrchestrator(repository=repo)
    c = await orchestrator.run_pipeline(sample_event, base_context)

    # Verify all mandatory schema fields
    assert c.consensus_id.startswith("chief_")
    assert c.token_mint == sample_event.token_mint
    assert c.timestamp > 0
    assert isinstance(c.sources_used, list) and len(c.sources_used) > 0
    assert isinstance(c.favorable_signals, list)
    assert isinstance(c.unfavorable_signals, list)
    assert 0.0 <= c.confidence_score <= 1.0
    assert len(c.confidence_method) > 0
    assert c.final_decision in (AgentDecision.BUY_CANDIDATE, AgentDecision.PASS, AgentDecision.VETO)
    assert isinstance(c.invalidation_conditions, list) and len(c.invalidation_conditions) > 0
    assert isinstance(c.identified_risks, list)
    assert "consensus" in c.strategy_version
    assert len(c.expected_outcome) > 0
    assert c.evaluation_horizon_sec > 0
    assert c.entry_price_usd == 1.25
    assert c.target_price_usd > 0.0
    assert c.invalidation_price_usd > 0.0


@pytest.mark.asyncio
async def test_decision_reproducibility(repo, sample_event, base_context):
    """Running pipeline twice with identical inputs produces identical results."""
    orchestrator = AgentOrchestrator(repository=repo)
    
    c1 = await orchestrator.run_pipeline(sample_event, base_context)
    c2 = await orchestrator.run_pipeline(sample_event, base_context)

    assert c1.final_decision == c2.final_decision
    assert c1.confidence_score == c2.confidence_score
    assert c1.target_price_usd == c2.target_price_usd
    assert c1.invalidation_price_usd == c2.invalidation_price_usd
    assert c1.favorable_signals == c2.favorable_signals
    assert c1.unfavorable_signals == c2.unfavorable_signals


@pytest.mark.asyncio
async def test_skeptic_agent_contradiction_detection(repo, sample_event, base_context):
    orchestrator = AgentOrchestrator(repository=repo)
    consensus = await orchestrator.run_pipeline(sample_event, base_context)
    
    assert AgentName.SKEPTIC.value in consensus.contributing_agents
    skeptic_res = consensus.contributing_agents[AgentName.SKEPTIC.value]
    assert skeptic_res.agent_name == AgentName.SKEPTIC
    # SKEPTIC actively inspects counter-arguments and tracks risk factors
    assert len(skeptic_res.reason_codes) > 0


@pytest.mark.asyncio
async def test_risk_veto_blocks_decision(repo, sample_event):
    """When a severe drawdown violation occurs, RISK issues a hard VETO, forcing PASS or VETO."""
    orchestrator = AgentOrchestrator(repository=repo)
    
    # Context with severe drawdown exceeding maximum allowable
    high_risk_context = {
        "portfolio_equity": 10000.0,
        "cash_balance": 5000.0,
        "open_positions_count": 3,
        "current_drawdown_pct": 25.0,  # Exceeds max 15% drawdown
        "has_existing_position": False,
    }

    consensus = await orchestrator.run_pipeline(sample_event, high_risk_context)
    assert consensus.final_decision in (AgentDecision.PASS, AgentDecision.VETO)
    assert consensus.is_risk_vetoed is True


@pytest.mark.asyncio
async def test_persistence_of_chief_decisions(repo, sample_event, base_context):
    orchestrator = AgentOrchestrator(repository=repo)
    consensus = await orchestrator.run_pipeline(sample_event, base_context)

    # Verify retrieval from repository
    saved = await repo.get_recent_chief_decisions(limit=10)
    assert len(saved) >= 1
    found = next((d for d in saved if d["consensus_id"] == consensus.consensus_id), None)
    assert found is not None
    assert found["token_mint"] == sample_event.token_mint
    assert found["final_decision"] == consensus.final_decision.value
    assert found["confidence_score"] == consensus.confidence_score
