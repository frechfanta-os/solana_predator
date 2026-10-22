# Paper Trading Simulator Specification — SOLANA PREDATOR

## 1. Simulation Principles

The Paper Broker is a fully isolated simulated execution component designed to model realistic trading conditions without touching the Solana blockchain.

### Execution Parameters
- **Virtual Initial Capital**: $10,000.00 virtual USD.
- **Taker Fee**: 25 basis points (0.25%).
- **Base Slippage**: 30 basis points (0.30%).
- **Market Depth Impact**:
  $$\text{Price Impact (bps)} = \left(\frac{\text{Order Size USD}}{\text{Pool Liquidity USD}}\right) \times 5000$$
  $$\text{Effective Execution Price} = \text{Observed Price} \times \left(1 + \frac{\text{Base Slippage} + \text{Price Impact}}{10000}\right)$$
- **Partial Fill Rule**: If an order exceeds 10% of pool liquidity, it is partially filled up to a maximum of 5% of available liquidity. Orders exceeding available capital are strictly rejected.

---

## 2. Exit Monitor & Liquidation Triggers

The Exit Monitor continuously tracks open positions across every incoming price update:

1. **Stop Loss Trigger**: Position unrealized loss $\le -15.0\%$.
2. **Take Profit Trigger**: Position unrealized gain $\ge +50.0\%$.
3. **Trailing Stop Trigger**: Pullback $\ge 20.0\%$ from peak price (only active once unrealized gain $> 10.0\%$).
4. **Liquidity Collapse Warning**: Pool liquidity drops below $2,000 USD (Emergency liquidation).
5. **Whale Dump Trigger**: Observable whale selling volume exceeds 2x whale buying and $> \$5,000$ USD.
6. **Price Staleness Flag**: If market data age exceeds 30.0s, the position is flagged as stale/unpriced rather than inventing a valuation.

---

## 3. Double-Entry Accounting & Restart Reconciliation

All simulated transactions generate immutable `paper_orders` and `paper_fills` records. On application startup, `PaperAccounting.reconcile_on_startup()` recalculates:
$$\text{Expected Cash} = \text{Initial Capital} + \sum \text{Realized PnL} - \sum \text{Invested Open Capital} - \sum \text{Fees Paid}$$
This total is verified against the latest `portfolio_snapshots` record, ensuring 100% auditability across restarts.
