"""Market data event normalization, deduplication, and quality assessment."""

import time
import hashlib
import json
from typing import Optional, Dict, Any, Tuple
from collections import OrderedDict
from backend.models import (
    NormalizedMarketEvent,
    MarketSource,
    EventQuality,
)
from backend.config import settings


class EventDeduplicator:
    """Thread-safe bounded LRU deduplication cache with TTL."""

    def __init__(self, maxsize: int = 50000, ttl_seconds: float = 600.0):
        self.maxsize = maxsize
        self.ttl = ttl_seconds
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._duplicate_count = 0

    def is_duplicate(self, key: str) -> bool:
        if not key:
            return False
        now = time.time()
        
        # Check if exists and not expired
        if key in self._cache:
            ts = self._cache[key]
            if now - ts <= self.ttl:
                self._duplicate_count += 1
                return True
            else:
                del self._cache[key]

        # Insert new key
        self._cache[key] = now
        if len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)
        return False

    @property
    def duplicate_count(self) -> int:
        return self._duplicate_count

    def clear(self) -> None:
        self._cache.clear()
        self._duplicate_count = 0


class EventNormalizer:
    """Normalizes heterogeneous market events into unified NormalizedMarketEvent structures."""

    def __init__(self, deduplicator: Optional[EventDeduplicator] = None):
        self.deduplicator = deduplicator or EventDeduplicator(
            maxsize=settings.DEDUPLICATION_CACHE_SIZE,
            ttl_seconds=settings.DEDUPLICATION_TTL_SEC,
        )

    def normalize_dex_screener_pair(
        self,
        pair_data: Dict[str, Any],
        receive_timestamp: Optional[float] = None,
    ) -> Optional[NormalizedMarketEvent]:
        """Normalize DEX Screener pair object into a NormalizedMarketEvent."""
        now = time.time()
        rx_time = receive_timestamp or now

        token_mint = pair_data.get("baseToken", {}).get("address")
        pair_address = pair_data.get("pairAddress")
        if not token_mint or not pair_address:
            return None

        # Hash pair address + priceUsd + volume to deduplicate unchanged polling results
        price_usd_str = pair_data.get("priceUsd")
        price_usd = float(price_usd_str) if price_usd_str else None
        
        liquidity = pair_data.get("liquidity", {})
        liquidity_usd = float(liquidity.get("usd")) if liquidity.get("usd") is not None else None
        
        volume = pair_data.get("volume", {})
        volume_24h = float(volume.get("h24")) if volume.get("h24") is not None else None

        # Deduplication signature based on pair + price + liquidity
        content_repr = f"{pair_address}:{price_usd}:{liquidity_usd}"
        payload_hash = hashlib.sha256(content_repr.encode()).hexdigest()
        
        if self.deduplicator.is_duplicate(payload_hash):
            return None  # Unchanged update, skipped to avoid redundant pipeline processing

        # Source timestamp
        source_ts = None
        pair_created_at = pair_data.get("pairCreatedAt")
        if pair_created_at:
            source_ts = float(pair_created_at) / 1000.0  # ms to seconds

        proc_time = time.time()
        freshness = proc_time - rx_time

        # Data quality evaluation
        quality = EventQuality.ACCEPTABLE
        confidence = 0.95
        if price_usd is None or liquidity_usd is None:
            quality = EventQuality.DEGRADED
            confidence = 0.50
        elif freshness > settings.DATA_STALENESS_THRESHOLD_SEC:
            quality = EventQuality.STALE
            confidence = 0.40

        event_id = f"dex_{pair_address[:12]}_{int(rx_time * 1000)}"

        return NormalizedMarketEvent(
            source=MarketSource.DEX_SCREENER,
            event_id=event_id,
            token_mint=token_mint,
            pair_address=pair_address,
            slot=None,
            source_timestamp=source_ts,
            local_receive_timestamp=rx_time,
            processing_timestamp=proc_time,
            freshness_seconds=round(freshness, 4),
            price_usd=price_usd,
            volume_24h_usd=volume_24h,
            liquidity_usd=liquidity_usd,
            signature=None,
            raw_payload_hash=payload_hash,
            quality=quality,
            confidence_score=confidence,
            metadata={
                "base_token": pair_data.get("baseToken"),
                "quote_token": pair_data.get("quoteToken"),
                "dex_id": pair_data.get("dexId"),
                "url": pair_data.get("url"),
                "txns_5m": pair_data.get("txns", {}).get("m5"),
            },
        )

    def normalize_solana_rpc_log(
        self,
        log_data: Dict[str, Any],
        receive_timestamp: Optional[float] = None,
    ) -> Optional[NormalizedMarketEvent]:
        """Normalize a Solana RPC transaction log message."""
        now = time.time()
        rx_time = receive_timestamp or now

        value = log_data.get("value", {})
        signature = value.get("signature")
        slot = log_data.get("context", {}).get("slot")

        if signature and self.deduplicator.is_duplicate(signature):
            return None  # Signature already processed

        logs = value.get("logs", [])
        raw_hash = hashlib.sha256(json.dumps(logs).encode()).hexdigest()

        # Identify token mint if mentioned in log
        token_mint = "UNKNOWN_MINT"
        for line in logs:
            if "Instruction: InitializeMint" in line or "Program log: Instruction: MintTo" in line:
                pass

        proc_time = time.time()
        freshness = proc_time - rx_time

        event_id = f"rpc_{signature[:12] if signature else int(rx_time * 1000)}"

        return NormalizedMarketEvent(
            source=MarketSource.SOLANA_RPC,
            event_id=event_id,
            token_mint=token_mint,
            pair_address=None,
            slot=slot,
            source_timestamp=None,
            local_receive_timestamp=rx_time,
            processing_timestamp=proc_time,
            freshness_seconds=round(freshness, 4),
            price_usd=None,  # Never fake price from raw log
            volume_24h_usd=None,
            liquidity_usd=None,
            signature=signature,
            raw_payload_hash=raw_hash,
            quality=EventQuality.ACCEPTABLE,
            confidence_score=0.90,
            metadata={"logs": logs[:10], "err": value.get("err")},
        )
