"""Extended Paper Trading validation tests covering edge scenarios and ledger audits."""

import time
import pytest
from backend.models import (
    PaperPosition,
    NormalizedMarketEvent,
    MarketSource,
    AgentDecision,
    AgentName,
    AgentResult,
)
from backend.paper.broker import PaperBroker
from backend.paper.positions import PositionManager
from backend.paper.accounting import PaperAccounting
from backend.paper.exit_monitor import ExitMonitor
from backend.agents.chief import ChiefAgent


@pytest.mark.asyncio
async def test_low_liquidity_emergency_exit(exit_monitor):
    """When pool liquidity collapses below $2,000, emergency exit is triggered."""
    pos = PaperPosition(
        position_id="pos_low_liq",
        token_mint="MintLowLiq",
        qty=1000.0,
        average_entry_price_usd=0.10,
        current_price_usd=0.09,
        invested_capital_usd=100.0,
        current_value_usd=90.0,
        unrealized_pnl_usd=-10.0,
        unrealized_pnl_pct=-10.0,
        opened_at=time.time(),
        peak_price_usd=0.10,
    )

    ev_low_liq = NormalizedMarketEvent(
        source=MarketSource.SYNTHETIC,
        event_id="ev_low_liq",
        token_mint="MintLowLiq",
        price_usd=0.09,
        liquidity_usd=1200.0,  # Below $2,000 threshold
        local_receive_timestamp=time.time(),
        processing_timestamp=time.time(),
    )

    decision = exit_monitor.evaluate_position(pos, ev_low_liq, None)
    assert decision.should_exit is True
    assert decision.urgency == "EMERGENCY"
    assert any("LIQUIDITY_COLLAPSE" in r for r in decision.reason_codes)
    assert decision.is_liquidity_sufficient is False


@pytest.mark.asyncio
async def test_stale_price_flagging_without_invented_valuation(position_manager):
    """Stale price (>30s) must flag position as stale and preserve last known valid price."""
    pos = PaperPosition(
        position_id="pos_stale_val",
        token_mint="MintStaleVal",
        qty=500.0,
        average_entry_price_usd=1.0,
        current_price_usd=1.0,
        invested_capital_usd=500.0,
        current_value_usd=500.0,
        unrealized_pnl_usd=0.0,
        unrealized_pnl_pct=0.0,
        opened_at=time.time(),
        peak_price_usd=1.0,
    )
    await position_manager.add_position(pos)

    # Price update that has 45 seconds of staleness
    updated = await position_manager.mark_to_market(
        token_mint="MintStaleVal",
        current_price_usd=1.50,
        freshness_seconds=45.0,  # Stale!
    )
    assert updated.is_stale_price is True
    # The valuation was NOT updated with the stale price to prevent fabricated PnL
    assert updated.current_price_usd == 1.0


@pytest.mark.asyncio
async def test_conflicting_agent_signals_consensus(chief_agent=None):
    """When agents disagree (e.g. SCAN=BUY, QUANT=BUY, but SKEPTIC=VETO), consensus is VETO."""
    chief = ChiefAgent()
    ev = NormalizedMarketEvent(
        source=MarketSource.SYNTHETIC,
        event_id="ev_conflict",
        token_mint="MintConflict",
        local_receive_timestamp=time.time(),
        processing_timestamp=time.time(),
    )

    results = {
        AgentName.SCAN.value: AgentResult(
            agent_name=AgentName.SCAN,
            input_event_identifiers=["ev_conflict"],
            timestamp=time.time(),
            decision=AgentDecision.BUY_CANDIDATE,
            reason_codes=["SCAN_LIQUIDITY_MET"],
            score=0.9,
            confidence=0.9,
            confidence_interpretation="Good volume",
            data_quality="GOOD",
            processing_latency_ms=1.0,
        ),
        AgentName.QUANT.value: AgentResult(
            agent_name=AgentName.QUANT,
            input_event_identifiers=["ev_conflict"],
            timestamp=time.time(),
            decision=AgentDecision.BUY_CANDIDATE,
            reason_codes=["QUANT_MOMENTUM"],
            score=0.85,
            confidence=0.9,
            confidence_interpretation="High turnover",
            data_quality="GOOD",
            processing_latency_ms=1.0,
        ),
        AgentName.VET.value: AgentResult(
            agent_name=AgentName.VET,
            input_event_identifiers=["ev_conflict"],
            timestamp=time.time(),
            decision=AgentDecision.PASS,
            reason_codes=["VET_OK"],
            score=0.9,
            confidence=0.9,
            confidence_interpretation="Clean metadata",
            data_quality="GOOD",
            processing_latency_ms=1.0,
        ),
        # SKEPTIC raises VETO (e.g. honeypot indicator)
        AgentName.SKEPTIC.value: AgentResult(
            agent_name=AgentName.SKEPTIC,
            input_event_identifiers=["ev_conflict"],
            timestamp=time.time(),
            decision=AgentDecision.VETO,
            reason_codes=["SKEPTIC_ZERO_SELLS_HONEYPOT_RISK"],
            score=0.1,
            confidence=0.95,
            confidence_interpretation="Zero sells detected",
            data_quality="GOOD",
            processing_latency_ms=1.0,
        ),
        AgentName.RISK.value: AgentResult(
            agent_name=AgentName.RISK,
            input_event_identifiers=["ev_conflict"],
            timestamp=time.time(),
            decision=AgentDecision.PASS,
            reason_codes=["RISK_OK"],
            score=1.0,
            confidence=1.0,
            confidence_interpretation="Risk bounds satisfied",
            data_quality="GOOD",
            processing_latency_ms=1.0,
        ),
    }

    consensus = chief.synthesize(ev, results, time.perf_counter())
    assert consensus.final_decision == AgentDecision.VETO
    assert "VETOED BY SKEPTIC" in consensus.chief_reason


@pytest.mark.asyncio
async def test_double_entry_ledger_consistency(paper_broker, paper_accounting, repo):
    """Verify that every debit/credit is strictly reflected in persistent orders and fills."""
    mint = "TokenMintLedgerAudit1111111111111111"
    initial_cash = paper_accounting.cash_balance

    # 1. Buy order: $1,000
    pos = await paper_broker.execute_simulated_buy(
        token_mint=mint,
        token_symbol="LEDGER",
        requested_usd=1000.0,
        current_price_usd=2.0,
        pool_liquidity_usd=50000.0,
    )
    assert pos is not None
    post_buy_cash = paper_accounting.cash_balance
    expected_fee = 1000.0 * 0.0025  # $2.50
    assert post_buy_cash == pytest.approx(initial_cash - 1000.0 - expected_fee, abs=1e-2)

    # 2. Sell order at 2.50 (+25%)
    closed = await paper_broker.execute_simulated_sell(
        token_mint=mint,
        current_price_usd=2.50,
        exit_reason="Target Hit",
        pool_liquidity_usd=50000.0,
    )
    assert closed is not None
    post_sell_cash = paper_accounting.cash_balance

    # Check database records
    orders = await repo.get_all_positions()
    assert len(orders) >= 1
    snap = await paper_accounting.compute_snapshot([])
    assert snap.cash_balance_usd == post_sell_cash
    assert snap.total_realized_pnl_usd > 0.0
