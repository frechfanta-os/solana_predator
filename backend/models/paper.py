"""Paper Trading Simulator models and strict accounting data structures."""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class PaperOrder(BaseModel):
    order_id: str
    token_mint: str
    side: OrderSide
    requested_amount_usd: float
    requested_qty: float
    limit_price_usd: Optional[float] = None
    created_at: float
    status: OrderStatus = OrderStatus.PENDING
    rejection_reason: Optional[str] = None


class PaperFill(BaseModel):
    fill_id: str
    order_id: str
    token_mint: str
    side: OrderSide
    executed_qty: float
    executed_price_usd: float
    fee_usd: float
    slippage_bps: float
    fill_timestamp: float


class PaperPosition(BaseModel):
    position_id: str
    token_mint: str
    token_symbol: str = "UNKNOWN"
    qty: float
    average_entry_price_usd: float
    current_price_usd: float
    invested_capital_usd: float
    current_value_usd: float
    unrealized_pnl_usd: float
    unrealized_pnl_pct: float
    realized_pnl_usd: float = 0.0
    total_fees_paid_usd: float = 0.0
    is_open: bool = True
    is_stale_price: bool = False
    opened_at: float
    closed_at: Optional[float] = None
    peak_price_usd: float = 0.0
    exit_reason: Optional[str] = None


class PortfolioSnapshot(BaseModel):
    snapshot_id: str
    timestamp: float
    cash_balance_usd: float
    positions_value_usd: float
    total_equity_usd: float
    total_realized_pnl_usd: float
    total_unrealized_pnl_usd: float
    total_fees_paid_usd: float
    peak_equity_usd: float
    current_drawdown_pct: float
    max_drawdown_pct: float
    open_positions_count: int


class ExitDecision(BaseModel):
    token_mint: str
    should_exit: bool
    urgency: str = "LOW"  # LOW, MEDIUM, HIGH, EMERGENCY
    reason_codes: List[str] = Field(default_factory=list)
    estimated_exit_cost_bps: float = 0.0
    is_liquidity_sufficient: bool = True
    details: Dict[str, Any] = Field(default_factory=dict)
