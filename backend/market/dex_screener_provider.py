"""DEX Screener implementation of BaseMarketDataProvider."""

import time
from typing import Optional, Dict, Any, List
from backend.market.base import BaseMarketDataProvider
from backend.market.dex_screener import DexScreenerClient
from backend.market.normalizer import EventNormalizer
from backend.models.events import NormalizedMarketEvent, MarketSource, EventQuality
from backend.config import settings


class DexScreenerProvider(BaseMarketDataProvider):
    """Adapter wrapping DexScreenerClient to conform to BaseMarketDataProvider."""

    def __init__(
        self,
        client: Optional[DexScreenerClient] = None,
        normalizer: Optional[EventNormalizer] = None,
    ):
        self._client = client or DexScreenerClient()
        self._normalizer = normalizer or EventNormalizer()
        self._consecutive_failures = 0
        self._call_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0

    @property
    def name(self) -> str:
        return "dex_screener"

    @property
    def source(self) -> MarketSource:
        return MarketSource.DEX_SCREENER

    @property
    def is_configured(self) -> bool:
        return bool(self._client.base_url)

    @property
    def is_available(self) -> bool:
        return self._consecutive_failures < 3

    async def get_token_market_data(self, token_mint: str) -> Optional[NormalizedMarketEvent]:
        """Fetch normalized market data for a token mint from DEX Screener."""
        start_mono = time.perf_counter()
        self._call_count += 1
        try:
            pairs = await self._client.get_tokens_pairs([token_mint])
            latency_ms = (time.perf_counter() - start_mono) * 1000.0
            self._total_latency_ms += latency_ms
            self._consecutive_failures = 0

            if not pairs:
                return None

            # Pick highest liquidity Solana pair
            best_pair = max(
                pairs,
                key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0.0),
                default=pairs[0]
            )

            event = self._normalizer.normalize_dex_screener_pair(best_pair, receive_timestamp=time.time())
            if not event:
                return None

            event.provider_latency_ms = round(latency_ms, 2)
            self._tag_observation_quality(event)
            return event
        except Exception as e:
            self._error_count += 1
            self._consecutive_failures += 1
            return None

    async def get_token_pairs(self, token_addresses: List[str]) -> List[NormalizedMarketEvent]:
        """Batch query up to 30 tokens from DEX Screener."""
        start_mono = time.perf_counter()
        self._call_count += 1
        try:
            pairs = await self._client.get_tokens_pairs(token_addresses)
            latency_ms = (time.perf_counter() - start_mono) * 1000.0
            self._total_latency_ms += latency_ms
            self._consecutive_failures = 0

            events: List[NormalizedMarketEvent] = []
            rx = time.time()
            for p in pairs:
                ev = self._normalizer.normalize_dex_screener_pair(p, receive_timestamp=rx)
                if ev:
                    ev.provider_latency_ms = round(latency_ms, 2)
                    self._tag_observation_quality(ev)
                    events.append(ev)
            return events
        except Exception:
            self._error_count += 1
            self._consecutive_failures += 1
            return []

    def _tag_observation_quality(self, event: NormalizedMarketEvent) -> None:
        """Categorize data as GENUINELY_OBSERVED, STALE, or MISSING."""
        now = time.time()
        missing = []
        if event.price_usd is None:
            missing.append("price_usd")
        if event.liquidity_usd is None:
            missing.append("liquidity_usd")
        if event.volume_24h_usd is None:
            missing.append("volume_24h_usd")
        event.missing_fields = missing

        if len(missing) >= 2:
            event.observation_state = "MISSING"
            event.quality = EventQuality.MISSING
        elif (now - event.local_receive_timestamp) > settings.DATA_STALENESS_THRESHOLD_SEC:
            event.observation_state = "STALE"
            event.quality = EventQuality.STALE
        else:
            event.observation_state = "GENUINELY_OBSERVED"
            event.quality = EventQuality.EXCELLENT if not missing else EventQuality.ACCEPTABLE

    async def check_health(self) -> Dict[str, Any]:
        avg_lat = round(self._total_latency_ms / max(1, self._call_count), 2)
        return {
            "name": self.name,
            "source": self.source.value,
            "configured": self.is_configured,
            "available": self.is_available,
            "call_count": self._call_count,
            "error_count": self._error_count,
            "consecutive_failures": self._consecutive_failures,
            "avg_latency_ms": avg_lat,
            "auth_required": False,
        }

    async def close(self) -> None:
        await self._client.close()
