"""Token discovery, metadata, and lifecycle models."""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class TokenLifecycleState(str, Enum):
    DISCOVERED = "DISCOVERED"
    OBSERVED = "OBSERVED"
    ANALYZED = "ANALYZED"
    REJECTED = "REJECTED"
    PAPER_CANDIDATE = "PAPER_CANDIDATE"


class TokenMetadata(BaseModel):
    mint: str
    name: Optional[str] = None
    symbol: Optional[str] = None
    decimals: int = 9
    first_observed_timestamp: float
    pool_created_timestamp: Optional[float] = None
    pair_address: Optional[str] = None
    dex_id: Optional[str] = None
    initial_liquidity_usd: Optional[float] = None


class TokenLifecycleRecord(BaseModel):
    token_mint: str
    from_state: Optional[TokenLifecycleState] = None
    to_state: TokenLifecycleState
    transition_timestamp: float
    reason: str


class TokenSnapshot(BaseModel):
    snapshot_id: str
    token_mint: str
    timestamp: float
    price_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    liquidity_usd: Optional[float] = None
    fdv_usd: Optional[float] = None
    buys_5m: int = 0
    sells_5m: int = 0
    lifecycle_state: TokenLifecycleState = TokenLifecycleState.DISCOVERED
    lifecycle_reason: str = "Initial discovery"
    is_stale: bool = False
