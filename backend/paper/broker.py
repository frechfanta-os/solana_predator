"""Deterministic Paper Trading Broker for SOLANA PREDATOR.

SECURITY BOUNDARY ENFORCEMENT:
- THIS BROKER OPERATES EXCLUSIVELY ON VIRTUAL CAPITAL.
- ZERO WALLET PRIVATE KEYS, ZERO SEED PHRASES.
- ZERO TRANSACTION SIGNING CODE PATHS.
- ZERO BLOCKCHAIN BROADCAST LOGIC.
- CANNOT INTERACT WITH REAL DECENTRALIZED EXCHANGES OR SWAP ROUTERS.
"""

import time
import uuid
import logging
from typing import Optional, Dict, Any
from backend.models import (
    PaperOrder,
    PaperFill,
    PaperPosition,
    OrderSide,
    OrderStatus,
)
from backend.paper.accounting import PaperAccounting
from backend.paper.positions import PositionManager
from backend.database.repository import Repository
from backend.config import settings

logger = logging.getLogger("predator.paper.broker")


class PaperBroker:
    """Simulated execution broker enforcing fees, slippage, and liquidity limits."""

    def __init__(
        self,
        accounting: PaperAccounting,
        position_manager: PositionManager,
        repository: Repository,
    ):
        self.accounting = accounting
        self.position_manager = position_manager
        self.repository = repository
        self.taker_fee_bps = settings.PAPER_TAKER_FEE_BPS
        self.base_slippage_bps = settings.PAPER_BASE_SLIPPAGE_BPS

    async def execute_simulated_buy(
        self,
        token_mint: str,
        token_symbol: str,
        requested_usd: float,
        current_price_usd: float,
        pool_liquidity_usd: Optional[float] = None,
    ) -> Optional[PaperPosition]:
        """Execute simulated buy order with fee, slippage, and liquidity validation."""
        now = time.time()
        order_id = f"ord_{uuid.uuid4().hex[:12]}"

        if current_price_usd <= 0:
            logger.warning("Rejected simulated buy for %s: invalid price $%.6f", token_mint, current_price_usd)
            return None

        # Check cash balance
        if self.accounting.cash_balance < requested_usd:
            logger.warning(
                "Rejected simulated buy: Cash $%.2f < Requested $%.2f",
                self.accounting.cash_balance,
                requested_usd,
            )
            order = PaperOrder(
                order_id=order_id,
                token_mint=token_mint,
                side=OrderSide.BUY,
                requested_amount_usd=requested_usd,
                requested_qty=requested_usd / current_price_usd,
                created_at=now,
                status=OrderStatus.REJECTED,
                rejection_reason="Insufficient virtual cash balance",
            )
            await self.repository.save_paper_order(order)
            return None

        # Check liquidity depth and calculate impact
        liq = pool_liquidity_usd or 10000.0
        if requested_usd > (liq * 0.10):
            # Order is too large for pool: partial fill up to 5% of liquidity
            fillable_usd = round(liq * 0.05, 2)
            logger.info("Order size $%.2f exceeds pool depth $%.2f; partial fill at $%.2f", requested_usd, liq, fillable_usd)
            order_status = OrderStatus.PARTIALLY_FILLED
            effective_usd = fillable_usd
        else:
            order_status = OrderStatus.FILLED
            effective_usd = requested_usd

        # Calculate slippage: base + price impact
        price_impact_bps = (effective_usd / max(liq, 1.0)) * 5000.0  # Conservative impact model
        total_slippage_bps = self.base_slippage_bps + price_impact_bps
        slippage_mult = 1.0 + (total_slippage_bps / 10000.0)
        
        executed_price = current_price_usd * slippage_mult
        fee_usd = round(effective_usd * (self.taker_fee_bps / 10000.0), 4)
        
        total_cost = effective_usd + fee_usd
        if not self.accounting.debit_cash(total_cost):
            return None

        self.accounting.total_fees_paid += fee_usd
        executed_qty = effective_usd / executed_price

        # Persist Order & Fill
        order = PaperOrder(
            order_id=order_id,
            token_mint=token_mint,
            side=OrderSide.BUY,
            requested_amount_usd=requested_usd,
            requested_qty=requested_usd / current_price_usd,
            limit_price_usd=None,
            created_at=now,
            status=order_status,
        )
        await self.repository.save_paper_order(order)

        fill_id = f"fill_{uuid.uuid4().hex[:12]}"
        fill = PaperFill(
            fill_id=fill_id,
            order_id=order_id,
            token_mint=token_mint,
            side=OrderSide.BUY,
            executed_qty=round(executed_qty, 6),
            executed_price_usd=round(executed_price, 8),
            fee_usd=fee_usd,
            slippage_bps=round(total_slippage_bps, 2),
            fill_timestamp=now,
        )
        await self.repository.save_paper_fill(fill)

        # Create or update position
        position_id = f"pos_{uuid.uuid4().hex[:12]}"
        position = PaperPosition(
            position_id=position_id,
            token_mint=token_mint,
            token_symbol=token_symbol,
            qty=round(executed_qty, 6),
            average_entry_price_usd=round(executed_price, 8),
            current_price_usd=round(executed_price, 8),
            invested_capital_usd=round(effective_usd, 4),
            current_value_usd=round(effective_usd, 4),
            unrealized_pnl_usd=0.0,
            unrealized_pnl_pct=0.0,
            realized_pnl_usd=0.0,
            total_fees_paid_usd=fee_usd,
            is_open=True,
            is_stale_price=False,
            opened_at=now,
            peak_price_usd=round(executed_price, 8),
        )
        await self.position_manager.add_position(position)
        logger.info(
            "EXECUTED SIMULATED BUY: %s (%s) Qty=%.4f @ $%.6f | Fee=$%.2f | Slip=%.1fbps",
            token_mint,
            token_symbol,
            executed_qty,
            executed_price,
            fee_usd,
            total_slippage_bps,
        )
        return position

    async def execute_simulated_sell(
        self,
        token_mint: str,
        current_price_usd: float,
        exit_reason: str,
        pool_liquidity_usd: Optional[float] = None,
    ) -> Optional[PaperPosition]:
        """Execute simulated sell to close out a holding."""
        pos = self.position_manager.get_position(token_mint)
        if not pos or not pos.is_open:
            return None

        now = time.time()
        order_id = f"ord_exit_{uuid.uuid4().hex[:12]}"

        # Calculate exit slippage
        liq = pool_liquidity_usd or 10000.0
        expected_exit_usd = pos.qty * current_price_usd
        price_impact_bps = (expected_exit_usd / max(liq, 1.0)) * 5000.0
        total_slippage_bps = self.base_slippage_bps + price_impact_bps
        slippage_mult = 1.0 - (total_slippage_bps / 10000.0)

        executed_price = max(0.0, current_price_usd * slippage_mult)
        gross_usd = pos.qty * executed_price
        fee_usd = round(gross_usd * (self.taker_fee_bps / 10000.0), 4)
        net_credit_usd = round(gross_usd - fee_usd, 4)

        self.accounting.credit_cash(net_credit_usd)
        self.accounting.total_fees_paid = round(self.accounting.total_fees_paid + fee_usd, 4)
        realized_pnl = round(net_credit_usd - pos.invested_capital_usd, 4)
        self.accounting.total_realized_pnl = round(self.accounting.total_realized_pnl + realized_pnl, 4)

        # Orders & Fills
        order = PaperOrder(
            order_id=order_id,
            token_mint=token_mint,
            side=OrderSide.SELL,
            requested_amount_usd=gross_usd,
            requested_qty=pos.qty,
            created_at=now,
            status=OrderStatus.FILLED,
        )
        await self.repository.save_paper_order(order)

        fill_id = f"fill_{uuid.uuid4().hex[:12]}"
        fill = PaperFill(
            fill_id=fill_id,
            order_id=order_id,
            token_mint=token_mint,
            side=OrderSide.SELL,
            executed_qty=pos.qty,
            executed_price_usd=round(executed_price, 8),
            fee_usd=fee_usd,
            slippage_bps=round(total_slippage_bps, 2),
            fill_timestamp=now,
        )
        await self.repository.save_paper_fill(fill)

        closed_pos = await self.position_manager.close_position(
            token_mint,
            exit_price_usd=executed_price,
            fee_usd=fee_usd,
            exit_reason=exit_reason,
        )
        logger.info(
            "EXECUTED SIMULATED EXIT: %s Qty=%.4f @ $%.6f | Realized PnL=$%.2f | Reason: %s",
            token_mint,
            pos.qty,
            executed_price,
            realized_pnl,
            exit_reason,
        )
        return closed_pos
