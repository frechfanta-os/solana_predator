"""Tests for Exit Monitor scenarios and triggers."""

import time
import pytest
from backend.paper.exit_monitor import ExitMonitor
from backend.models import PaperPosition, NormalizedMarketEvent, MarketSource, WhaleConvergenceMetrics


def test_exit_monitor_stop_loss_and_take_profit(exit_monitor):
    # 1. Stop loss test (-20% unrealized PnL, limit is -15%)
    pos_loss = PaperPosition(
        position_id="pos_l",
        token_mint="MintLoss",
        qty=100.0,
        average_entry_price_usd=1.0,
        current_price_usd=0.80,
        invested_capital_usd=100.0,
        current_value_usd=80.0,
        unrealized_pnl_usd=-20.0,
        unrealized_pnl_pct=-20.0,
        opened_at=time.time(),
        peak_price_usd=1.0,
    )
    dec_loss = exit_monitor.evaluate_position(pos_loss, None, None)
    assert dec_loss.should_exit is True
    assert dec_loss.urgency == "HIGH"
    assert any("STOP_LOSS" in r for r in dec_loss.reason_codes)

    # 2. Take profit test (+60% unrealized PnL, limit is +50%)
    pos_profit = PaperPosition(
        position_id="pos_p",
        token_mint="MintProfit",
        qty=100.0,
        average_entry_price_usd=1.0,
        current_price_usd=1.60,
        invested_capital_usd=100.0,
        current_value_usd=160.0,
        unrealized_pnl_usd=60.0,
        unrealized_pnl_pct=60.0,
        opened_at=time.time(),
        peak_price_usd=1.60,
    )
    dec_profit = exit_monitor.evaluate_position(pos_profit, None, None)
    assert dec_profit.should_exit is True
    assert dec_profit.urgency == "MEDIUM"
    assert any("TAKE_PROFIT" in r for r in dec_profit.reason_codes)


def test_exit_monitor_liquidity_collapse(exit_monitor):
    pos = PaperPosition(
        position_id="pos_rug",
        token_mint="MintRug",
        qty=100.0,
        average_entry_price_usd=1.0,
        current_price_usd=0.95,
        invested_capital_usd=100.0,
        current_value_usd=95.0,
        unrealized_pnl_usd=-5.0,
        unrealized_pnl_pct=-5.0,
        opened_at=time.time(),
        peak_price_usd=1.0,
    )
    # Liquidity collapsed to $500
    ev = NormalizedMarketEvent(
        source=MarketSource.SYNTHETIC,
        event_id="ev_collapse",
        token_mint="MintRug",
        liquidity_usd=500.0,
        local_receive_timestamp=time.time(),
        processing_timestamp=time.time(),
    )
    dec = exit_monitor.evaluate_position(pos, ev, None)
    assert dec.should_exit is True
    assert dec.urgency == "EMERGENCY"
    assert any("LIQUIDITY_COLLAPSE" in r for r in dec.reason_codes)
