"""Position tracker and mark-to-market manager for simulated holdings."""

import time
import logging
from typing import Dict, List, Optional
from backend.models import PaperPosition
from backend.database.repository import Repository
from backend.config import settings

logger = logging.getLogger("predator.paper.positions")


class PositionManager:
    """Manages open and closed paper positions with real-time mark-to-market pricing."""

    def __init__(self, repository: Repository):
        self.repository = repository
        self._positions: Dict[str, PaperPosition] = {}  # token_mint -> PaperPosition

    async def restore_from_db(self) -> None:
        """Load open positions from database on startup."""
        open_pos = await self.repository.get_open_positions()
        for p in open_pos:
            self._positions[p.token_mint] = p
        logger.info("Restored %d open positions from repository.", len(self._positions))

    def get_position(self, token_mint: str) -> Optional[PaperPosition]:
        return self._positions.get(token_mint)

    def get_open_positions(self) -> List[PaperPosition]:
        return [p for p in self._positions.values() if p.is_open]

    def has_open_position(self, token_mint: str) -> bool:
        p = self._positions.get(token_mint)
        return p is not None and p.is_open

    async def add_position(self, position: PaperPosition) -> None:
        self._positions[position.token_mint] = position
        await self.repository.save_paper_position(position)

    async def mark_to_market(self, token_mint: str, current_price_usd: float, freshness_seconds: float) -> Optional[PaperPosition]:
        """Update position valuation using latest observed price."""
        pos = self._positions.get(token_mint)
        if not pos or not pos.is_open:
            return None

        is_stale = freshness_seconds > settings.DATA_STALENESS_THRESHOLD_SEC
        pos.is_stale_price = is_stale

        if not is_stale and current_price_usd > 0:
            pos.current_price_usd = current_price_usd
            pos.current_value_usd = round(pos.qty * current_price_usd, 4)
            pos.unrealized_pnl_usd = round(pos.current_value_usd - pos.invested_capital_usd, 4)
            if pos.invested_capital_usd > 0:
                pos.unrealized_pnl_pct = round((pos.unrealized_pnl_usd / pos.invested_capital_usd) * 100.0, 2)
            if current_price_usd > pos.peak_price_usd:
                pos.peak_price_usd = current_price_usd

        await self.repository.save_paper_position(pos)
        return pos

    async def close_position(
        self,
        token_mint: str,
        exit_price_usd: float,
        fee_usd: float,
        exit_reason: str,
    ) -> Optional[PaperPosition]:
        """Close an open paper position and finalize realized PnL."""
        pos = self._positions.get(token_mint)
        if not pos or not pos.is_open:
            return None

        now = time.time()
        gross_value = pos.qty * exit_price_usd
        net_value = gross_value - fee_usd
        realized_pnl = net_value - pos.invested_capital_usd

        pos.current_price_usd = exit_price_usd
        pos.current_value_usd = 0.0
        pos.realized_pnl_usd = round(realized_pnl, 4)
        pos.unrealized_pnl_usd = 0.0
        pos.unrealized_pnl_pct = 0.0
        pos.total_fees_paid_usd += fee_usd
        pos.is_open = False
        pos.closed_at = now
        pos.exit_reason = exit_reason

        await self.repository.save_paper_position(pos)
        return pos
