"""Tests enforcing deterministic risk limits and unconditional veto power."""

import time
import pytest
from backend.models import (
    AgentName,
    AgentDecision,
    AgentResult,
    NormalizedMarketEvent,
    MarketSource,
)
from backend.agents.risk import RiskAgent
from backend.agents.chief import ChiefAgent


@pytest.mark.asyncio
async def test_risk_veto_on_max_drawdown():
    risk_agent = RiskAgent(max_drawdown_pct=0.15)
    ev = NormalizedMarketEvent(
        source=MarketSource.SYNTHETIC,
        event_id="ev_risk_dd",
        token_mint="TokenMintRisk1",
        local_receive_timestamp=100.0,
        processing_timestamp=100.1,
    )
    # Context with 20% drawdown (exceeding 15% limit)
    res = await risk_agent.evaluate(ev, {"current_drawdown_pct": 0.20, "open_positions_count": 1, "cash_balance": 5000.0})
    assert res.decision == AgentDecision.VETO
    assert any("MAX_DRAWDOWN_EXCEEDED" in r for r in res.reason_codes)


@pytest.mark.asyncio
async def test_risk_veto_on_max_positions():
    risk_agent = RiskAgent(max_open_positions=5)
    ev = NormalizedMarketEvent(
        source=MarketSource.SYNTHETIC,
        event_id="ev_risk_pos",
        token_mint="TokenMintRisk2",
        local_receive_timestamp=100.0,
        processing_timestamp=100.1,
    )
    # Context with 5 open positions
    res = await risk_agent.evaluate(ev, {"current_drawdown_pct": 0.02, "open_positions_count": 5, "cash_balance": 5000.0})
    assert res.decision == AgentDecision.VETO
    assert any("MAX_CONCURRENT_POSITIONS" in r for r in res.reason_codes)


def test_chief_cannot_override_risk_veto():
    """Verify that even if ALL other agents vote BUY, a RISK veto guarantees final VETO."""
    chief = ChiefAgent()
    ev = NormalizedMarketEvent(
        source=MarketSource.SYNTHETIC,
        event_id="ev_chief_override_test",
        token_mint="TokenMintOverride",
        local_receive_timestamp=100.0,
        processing_timestamp=100.1,
    )

    # Fake unanimous BUY from other agents
    agent_results = {
        AgentName.SCAN.value: AgentResult(
            agent_name=AgentName.SCAN,
            input_event_identifiers=["ev_1"],
            timestamp=100.0,
            decision=AgentDecision.BUY_CANDIDATE,
            reason_codes=["SCAN_OK"],
            score=0.99,
            confidence=0.99,
            confidence_interpretation="Top signal",
            data_quality="GOOD",
            processing_latency_ms=1.0,
        ),
        AgentName.WHALE.value: AgentResult(
            agent_name=AgentName.WHALE,
            input_event_identifiers=["ev_1"],
            timestamp=100.0,
            decision=AgentDecision.BUY_CANDIDATE,
            reason_codes=["WHALE_OK"],
            score=0.99,
            confidence=0.99,
            confidence_interpretation="Whale buy",
            data_quality="GOOD",
            processing_latency_ms=1.0,
        ),
        AgentName.QUANT.value: AgentResult(
            agent_name=AgentName.QUANT,
            input_event_identifiers=["ev_1"],
            timestamp=100.0,
            decision=AgentDecision.BUY_CANDIDATE,
            reason_codes=["QUANT_OK"],
            score=0.99,
            confidence=0.99,
            confidence_interpretation="Quant momentum",
            data_quality="GOOD",
            processing_latency_ms=1.0,
        ),
        # BUT RISK VETOES:
        AgentName.RISK.value: AgentResult(
            agent_name=AgentName.RISK,
            input_event_identifiers=["ev_1"],
            timestamp=100.0,
            decision=AgentDecision.VETO,
            reason_codes=["RISK_VETO_MAX_DRAWDOWN_EXCEEDED"],
            score=0.0,
            confidence=1.0,
            confidence_interpretation="Circuit breaker",
            data_quality="GOOD",
            processing_latency_ms=1.0,
        ),
    }

    consensus = chief.synthesize(ev, agent_results, time.perf_counter())
    assert consensus.final_decision == AgentDecision.VETO
    assert consensus.is_risk_vetoed is True
    assert "VETOED BY RISK" in consensus.chief_reason
    assert consensus.recommended_position_usd is None
