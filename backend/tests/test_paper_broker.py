"""Tests for Paper Trading Broker, fees, slippage, and fills."""

import pytest
from backend.models import OrderSide, OrderStatus


@pytest.mark.asyncio
async def test_paper_broker_simulated_buy(paper_broker, paper_accounting):
    mint = "TokenMintPaperBuy111111111111111111111111"
    initial_cash = paper_accounting.cash_balance

    pos = await paper_broker.execute_simulated_buy(
        token_mint=mint,
        token_symbol="PBUY",
        requested_usd=1000.0,
        current_price_usd=0.01,
        pool_liquidity_usd=50000.0,
    )

    assert pos is not None
    assert pos.is_open is True
    assert pos.invested_capital_usd == 1000.0
    assert pos.total_fees_paid_usd > 0.0  # 25 bps taker fee
    # Entry price should be slightly higher than base price due to slippage
    assert pos.average_entry_price_usd > 0.01
    assert paper_accounting.cash_balance < initial_cash


@pytest.mark.asyncio
async def test_paper_broker_partial_fill_on_oversized_order(paper_broker):
    mint = "TokenMintPaperPartial11111111111111111111"
    
    # Request $2000 in a pool with only $5000 liquidity (> 10% limit)
    pos = await paper_broker.execute_simulated_buy(
        token_mint=mint,
        token_symbol="PARTIAL",
        requested_usd=2000.0,
        current_price_usd=1.0,
        pool_liquidity_usd=5000.0,
    )

    assert pos is not None
    # Effective filled amount should be clamped to 5% of liquidity ($250)
    assert pos.invested_capital_usd == 250.0


@pytest.mark.asyncio
async def test_paper_broker_simulated_exit(paper_broker, paper_accounting):
    mint = "TokenMintPaperExit11111111111111111111"
    await paper_broker.execute_simulated_buy(
        token_mint=mint,
        token_symbol="PEXIT",
        requested_usd=500.0,
        current_price_usd=0.50,
        pool_liquidity_usd=20000.0,
    )

    # Sell at $0.75 (50% price increase)
    closed = await paper_broker.execute_simulated_sell(
        token_mint=mint,
        current_price_usd=0.75,
        exit_reason="Take Profit Target Hit",
        pool_liquidity_usd=20000.0,
    )

    assert closed is not None
    assert closed.is_open is False
    assert closed.realized_pnl_usd > 0.0
    assert closed.exit_reason == "Take Profit Target Hit"
