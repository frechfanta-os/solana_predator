"""Solana RPC on-chain truth implementation of BaseMarketDataProvider."""

import time
from typing import Optional, Dict, Any, List
from backend.market.base import BaseMarketDataProvider
from backend.market.solana_rpc import SolanaRpcClient
from backend.models.events import NormalizedMarketEvent, MarketSource, EventQuality
from backend.config import settings


class SolanaRpcProvider(BaseMarketDataProvider):
    """Adapter wrapping SolanaRpcClient to conform to BaseMarketDataProvider."""

    def __init__(self, client: Optional[SolanaRpcClient] = None):
        self._client = client or SolanaRpcClient()
        self._call_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0
        self._last_checked = time.time()
        self._last_error: Optional[str] = None

    @property
    def name(self) -> str:
        return "solana_rpc"

    @property
    def source(self) -> MarketSource:
        return MarketSource.SOLANA_RPC

    @property
    def is_configured(self) -> bool:
        return bool(self._client.http_url)

    @property
    def is_available(self) -> bool:
        return self._client._is_connected or self._error_count == 0

    async def get_token_market_data(self, token_mint: str) -> Optional[NormalizedMarketEvent]:
        """Fetch on-chain token state (slot, signatures) without faking pricing data."""
        start_mono = time.perf_counter()
        self._call_count += 1
        now = time.time()
        self._last_checked = now
        try:
            slot = await self._client.get_slot()
            sigs = await self._client.get_signatures_for_address(token_mint, limit=5)
            latency_ms = (time.perf_counter() - start_mono) * 1000.0
            self._total_latency_ms += latency_ms

            latest_sig = sigs[0].get("signature") if sigs else None
            source_ts = float(sigs[0].get("blockTime")) if sigs and sigs[0].get("blockTime") else None

            # Calculate freshness from on-chain blockTime when available
            if source_ts is not None:
                age = max(0.0, now - source_ts)
                freshness = round(age, 3)
                is_stale = age > settings.DATA_STALENESS_THRESHOLD_SEC
                quality = EventQuality.STALE if is_stale else EventQuality.ACCEPTABLE
                freshness_verified = True
            else:
                freshness = 0.0
                quality = EventQuality.UNVERIFIED
                freshness_verified = False

            # On-chain RPC provides on-chain truth, but NO USD pricing or liquidity: NEVER invent it!
            missing = ["price_usd", "volume_24h_usd", "liquidity_usd"]

            return NormalizedMarketEvent(
                source=MarketSource.SOLANA_RPC,
                event_id=f"rpc_{token_mint[:8]}_{int(now * 1000)}",
                token_mint=token_mint,
                slot=slot,
                source_timestamp=source_ts,
                local_receive_timestamp=now,
                processing_timestamp=time.time(),
                freshness_seconds=freshness,
                price_usd=None,
                volume_24h_usd=None,
                liquidity_usd=None,
                signature=latest_sig,
                observation_state="MISSING",
                missing_fields=missing,
                provider_latency_ms=round(latency_ms, 2),
                quality=quality,
                confidence_score=0.99,
                metadata={
                    "on_chain_observed": True,
                    "on_chain_slot": slot,
                    "recent_signatures_count": len(sigs),
                    "freshness_verified": freshness_verified,
                },
            )
        except Exception as e:
            self._error_count += 1
            self._last_error = f"Solana RPC query error: {e}"
            return None

    async def get_token_pairs(self, token_addresses: List[str]) -> List[NormalizedMarketEvent]:
        events = []
        for addr in token_addresses:
            ev = await self.get_token_market_data(addr)
            if ev:
                events.append(ev)
        return events

    async def check_health(self) -> Dict[str, Any]:
        self._last_checked = time.time()
        avg_lat = round(self._total_latency_ms / max(1, self._call_count), 2)
        reason = "ONLINE" if self.is_available else (self._last_error or "RPC_DISCONNECTED")
        return {
            "name": self.name,
            "source": self.source.value,
            "configured": self.is_configured,
            "available": self.is_available,
            "reason": reason,
            "last_checked": self._last_checked,
            "last_error": self._last_error,
            "call_count": self._call_count,
            "error_count": self._error_count,
            "avg_latency_ms": avg_lat,
            "auth_required": False,
        }

    async def close(self) -> None:
        await self._client.close()
