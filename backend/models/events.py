"""Market event models with strict timestamps and data quality tracking."""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class MarketSource(str, Enum):
    SOLANA_RPC = "SOLANA_RPC"
    DEX_SCREENER = "DEX_SCREENER"
    GMGN = "GMGN"
    REPLAY = "REPLAY"
    SYNTHETIC = "SYNTHETIC"


class EventQuality(str, Enum):
    EXCELLENT = "EXCELLENT"
    ACCEPTABLE = "ACCEPTABLE"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    UNVERIFIED = "UNVERIFIED"
    MISSING = "MISSING"


class NormalizedMarketEvent(BaseModel):
    source: MarketSource
    event_id: str
    token_mint: str
    pair_address: Optional[str] = None
    slot: Optional[int] = None
    
    # Timestamps (Explicit separation)
    source_timestamp: Optional[float] = None
    local_receive_timestamp: float
    processing_timestamp: float
    freshness_seconds: float = 0.0
    
    # Market Metrics (None if unverified, NEVER fabricated)
    price_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    liquidity_usd: Optional[float] = None
    
    # Observation status: GENUINELY_OBSERVED, STALE, or MISSING
    observation_state: str = "GENUINELY_OBSERVED"
    missing_fields: list[str] = Field(default_factory=list)
    provider_latency_ms: float = 0.0

    # Identifiers & Hashes
    signature: Optional[str] = None
    raw_payload_hash: Optional[str] = None
    
    # Quality & Confidence
    quality: EventQuality = EventQuality.ACCEPTABLE
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
