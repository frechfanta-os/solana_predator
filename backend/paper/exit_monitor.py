"""Exit Monitor engine continuously tracking liquidation triggers for open paper positions."""

import time
import logging
from typing import Dict, Any, List, Optional
from backend.models import (
    PaperPosition,
    ExitDecision,
    NormalizedMarketEvent,
    WhaleConvergenceMetrics,
)
from backend.paper.positions import PositionManager
from backend.config import settings

logger = logging.getLogger("predator.paper.exit_monitor")


class ExitMonitor:
    """Continuously evaluates open simulated positions against risk scenarios."""

    def __init__(
        self,
        position_manager: PositionManager,
        stop_loss_pct: float = -15.0,
        take_profit_pct: float = 50.0,
        trailing_stop_pct: float = 20.0,
    ):
        self.position_manager = position_manager
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct

    def evaluate_position(
        self,
        pos: PaperPosition,
        latest_event: Optional[NormalizedMarketEvent],
        whale_convergence: Optional[WhaleConvergenceMetrics],
    ) -> ExitDecision:
        """Evaluate whether a position must be closed and record contributing factors."""
        reasons: List[str] = []
        urgency = "LOW"
        should_exit = False
        is_liquidity_sufficient = True

        if not pos.is_open:
            return ExitDecision(token_mint=pos.token_mint, should_exit=False, urgency="NONE")

        # 1. Price Staleness Check
        if latest_event:
            if latest_event.freshness_seconds > settings.DATA_STALENESS_THRESHOLD_SEC:
                reasons.append(f"EXIT_FLAG_STALE_PRICE_{latest_event.freshness_seconds:.1f}s")
                urgency = "MEDIUM"

            # 2. Liquidity Collapse Check (Rug pull proxy)
            liq = latest_event.liquidity_usd
            if liq is not None and liq < 2000.0:
                reasons.append(f"EXIT_LIQUIDITY_COLLAPSE_CRITICAL_${liq:,.0f}")
                urgency = "EMERGENCY"
                should_exit = True
                is_liquidity_sufficient = False

        # 3. Stop-Loss Trigger
        if pos.unrealized_pnl_pct <= self.stop_loss_pct:
            reasons.append(f"EXIT_STOP_LOSS_TRIGGERED_{pos.unrealized_pnl_pct:.1f}%")
            urgency = "HIGH"
            should_exit = True

        # 4. Take-Profit Trigger
        if pos.unrealized_pnl_pct >= self.take_profit_pct:
            reasons.append(f"EXIT_TAKE_PROFIT_TRIGGERED_{pos.unrealized_pnl_pct:.1f}%")
            urgency = "MEDIUM"
            should_exit = True

        # 5. Trailing Stop from Peak
        if pos.peak_price_usd > 0 and pos.current_price_usd > 0:
            pullback_pct = ((pos.peak_price_usd - pos.current_price_usd) / pos.peak_price_usd) * 100.0
            if pullback_pct >= self.trailing_stop_pct and pos.unrealized_pnl_pct > 10.0:
                reasons.append(f"EXIT_TRAILING_STOP_PULLBACK_{pullback_pct:.1f}%_FROM_PEAK")
                urgency = "HIGH"
                should_exit = True

        # 6. Whale Selling Pressure Trigger
        if whale_convergence and whale_convergence.sell_volume_usd > (whale_convergence.buy_volume_usd * 2.0) and whale_convergence.sell_volume_usd > 5000.0:
            reasons.append(f"EXIT_WHALE_DUMP_OBSERVED_SELLS_${whale_convergence.sell_volume_usd:,.0f}")
            urgency = "HIGH"
            should_exit = True

        # Estimated exit cost (taker fee + base slippage)
        est_cost_bps = settings.PAPER_TAKER_FEE_BPS + settings.PAPER_BASE_SLIPPAGE_BPS

        return ExitDecision(
            token_mint=pos.token_mint,
            should_exit=should_exit,
            urgency=urgency,
            reason_codes=reasons,
            estimated_exit_cost_bps=est_cost_bps,
            is_liquidity_sufficient=is_liquidity_sufficient,
            details={
                "unrealized_pnl_pct": pos.unrealized_pnl_pct,
                "current_price_usd": pos.current_price_usd,
                "peak_price_usd": pos.peak_price_usd,
            },
        )
