"""Tests for paper accounting reconciliation after simulated restart."""

import pytest
from backend.paper.accounting import PaperAccounting
from backend.paper.positions import PositionManager
from backend.paper.broker import PaperBroker


@pytest.mark.asyncio
async def test_reconciliation_after_restart(temp_db_path, repo):
    # Phase 1: Run broker operations and close a position
    accounting1 = PaperAccounting(repo, initial_capital=10000.0)
    pos_manager1 = PositionManager(repo)
    broker1 = PaperBroker(accounting1, pos_manager1, repo)

    await broker1.execute_simulated_buy(
        token_mint="TokenRecon1",
        token_symbol="REC1",
        requested_usd=1000.0,
        current_price_usd=1.0,
        pool_liquidity_usd=50000.0,
    )

    await broker1.execute_simulated_sell(
        token_mint="TokenRecon1",
        current_price_usd=1.20,
        exit_reason="Test Profit Exit",
        pool_liquidity_usd=50000.0,
    )

    snap1 = await accounting1.compute_snapshot([])
    ending_cash = accounting1.cash_balance
    ending_realized = accounting1.total_realized_pnl

    # Phase 2: Simulate complete application restart (new instances reading same DB)
    accounting2 = PaperAccounting(repo, initial_capital=10000.0)
    pos_manager2 = PositionManager(repo)
    await pos_manager2.restore_from_db()
    await accounting2.reconcile_on_startup()

    assert accounting2.cash_balance == pytest.approx(ending_cash, abs=1e-3)
    assert accounting2.total_realized_pnl == pytest.approx(ending_realized, abs=1e-3)
    assert len(pos_manager2.get_open_positions()) == 0
