"""Whale activity and convergence classification models."""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class WhaleActivityType(str, Enum):
    SWAP = "SWAP"
    TRANSFER = "TRANSFER"
    DEPOSIT_WITHDRAW = "DEPOSIT_WITHDRAW"
    UNKNOWN_AMBIGUOUS = "UNKNOWN_AMBIGUOUS"


class WhaleActivity(BaseModel):
    activity_id: str
    signature: str
    wallet_address: str
    token_mint: str
    activity_type: WhaleActivityType
    amount_tokens: float
    amount_usd: Optional[float] = None
    timestamp: float
    slot: Optional[int] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_details: Dict[str, Any] = Field(default_factory=dict)


class WhaleConvergenceMetrics(BaseModel):
    token_mint: str
    unique_whales_active: int = 0
    net_flow_usd: float = 0.0
    buy_volume_usd: float = 0.0
    sell_volume_usd: float = 0.0
    convergence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_correlated_cluster: bool = False
    sample_size: int = 0
    calculated_at: float
