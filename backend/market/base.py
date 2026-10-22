"""Common abstract base interface for all market data providers in SOLANA PREDATOR.

INVARIANTS:
1. Strict read-only market data access (zero private keys, zero signing, zero funds).
2. Explicit categorization of data state: GENUINELY_OBSERVED, STALE, or MISSING.
3. NEVER fabricate or interpolate prices, volumes, or liquidity.
4. Resilient fallback across alternative providers without interrupting agents.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from backend.models.events import NormalizedMarketEvent, MarketSource


class BaseMarketDataProvider(ABC):
    """Abstract interface standardizing market data ingestion across heterogeneous providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g. 'dex_screener', 'gmgn', 'solana_rpc')."""
        pass

    @property
    @abstractmethod
    def source(self) -> MarketSource:
        """MarketSource enum identifying the provider."""
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Whether the provider possesses necessary credentials and endpoint configuration."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether the provider is currently responsive and online."""
        pass

    @abstractmethod
    async def get_token_market_data(self, token_mint: str) -> Optional[NormalizedMarketEvent]:
        """Fetch normalized market metrics for a token mint.
        
        Returns None if token is unlisted or data is unavailable, without fabricating values.
        """
        pass

    @abstractmethod
    async def get_token_pairs(self, token_addresses: List[str]) -> List[NormalizedMarketEvent]:
        """Batch query market data for multiple token addresses."""
        pass

    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """Return operational health telemetry without leaking secrets."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Gracefully release HTTP sessions and resources."""
        pass
