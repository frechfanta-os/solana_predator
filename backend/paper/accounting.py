"""Paper Accounting system enforcing idempotent balance mutations and reconciliation."""

import time
import uuid
import logging
from typing import Dict, Any, Optional, List
from backend.models import PortfolioSnapshot, PaperPosition
from backend.database.repository import Repository
from backend.config import settings

logger = logging.getLogger("predator.paper.accounting")


class PaperAccounting:
    """Manages virtual cash balance, equity calculations, and startup reconciliation."""

    def __init__(self, repository: Repository, initial_capital: Optional[float] = None):
        self.repository = repository
        self.initial_capital = initial_capital or settings.PAPER_INITIAL_CAPITAL
        self.cash_balance = self.initial_capital
        self.peak_equity = self.initial_capital
        self.max_drawdown_pct = 0.0
        self.total_realized_pnl = 0.0
        self.total_fees_paid = 0.0

    async def reconcile_on_startup(self) -> None:
        """Audit and reconcile virtual balances from persistent order, fill, and position records."""
        latest_snap = await self.repository.get_latest_portfolio_snapshot()
        all_positions = await self.repository.get_all_positions()

        # Recompute totals from historical positions
        realized_pnl_sum = sum(p.realized_pnl_usd for p in all_positions if not p.is_open)
        fees_sum = sum(p.total_fees_paid_usd for p in all_positions)
        invested_open = sum(p.invested_capital_usd for p in all_positions if p.is_open)

        # Expected cash balance = Initial Capital + Realized PnL - Open Invested Capital - Fees
        computed_cash = self.initial_capital + realized_pnl_sum - invested_open - fees_sum

        if latest_snap:
            logger.info(
                "Reconciliation check: Saved Snapshot Cash=$%.2f, Computed Ledger Cash=$%.2f",
                latest_snap.cash_balance_usd,
                computed_cash,
            )
            self.cash_balance = round(latest_snap.cash_balance_usd, 4)
            self.peak_equity = max(self.initial_capital, latest_snap.peak_equity_usd)
            self.max_drawdown_pct = latest_snap.max_drawdown_pct
            self.total_realized_pnl = round(latest_snap.total_realized_pnl_usd, 4)
            self.total_fees_paid = round(latest_snap.total_fees_paid_usd, 4)
        else:
            self.cash_balance = round(computed_cash, 4)
            self.total_realized_pnl = round(realized_pnl_sum, 4)
            self.total_fees_paid = round(fees_sum, 4)
            logger.info("Initialized fresh paper balance from ledger: $%.2f", self.cash_balance)

    def debit_cash(self, amount: float) -> bool:
        """Debit cash for position entry or fees."""
        if self.cash_balance < amount:
            return False
        self.cash_balance = round(self.cash_balance - amount, 4)
        return True

    def credit_cash(self, amount: float) -> None:
        """Credit cash on position exit."""
        self.cash_balance = round(self.cash_balance + amount, 4)

    async def compute_snapshot(self, open_positions: List[PaperPosition]) -> PortfolioSnapshot:
        """Compute current portfolio snapshot and track drawdown curve."""
        now = time.time()
        positions_value = sum(p.current_value_usd for p in open_positions if p.is_open)
        unrealized_pnl = sum(p.unrealized_pnl_usd for p in open_positions if p.is_open)
        
        total_equity = round(self.cash_balance + positions_value, 4)
        if total_equity > self.peak_equity:
            self.peak_equity = total_equity

        # Drawdown calculation
        current_drawdown = 0.0
        if self.peak_equity > 0:
            current_drawdown = round((self.peak_equity - total_equity) / self.peak_equity, 4)

        if current_drawdown > self.max_drawdown_pct:
            self.max_drawdown_pct = current_drawdown

        snapshot = PortfolioSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:12]}",
            timestamp=now,
            cash_balance_usd=self.cash_balance,
            positions_value_usd=round(positions_value, 4),
            total_equity_usd=total_equity,
            total_realized_pnl_usd=round(self.total_realized_pnl, 4),
            total_unrealized_pnl_usd=round(unrealized_pnl, 4),
            total_fees_paid_usd=round(self.total_fees_paid, 4),
            peak_equity_usd=self.peak_equity,
            current_drawdown_pct=current_drawdown,
            max_drawdown_pct=self.max_drawdown_pct,
            open_positions_count=len(open_positions),
        )

        await self.repository.save_portfolio_snapshot(snapshot)
        return snapshot
