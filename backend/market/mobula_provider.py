"""Optional Mobula API market data provider for SOLANA PREDATOR.

DESIGN & CONSTRAINTS:
1. OPTIONAL: Pluggable provider alongside GMGN, DEX Screener, and Solana RPC.
2. FREE PLAN RESTRICTION HANDLING: Mobula blocks API calls on the Free plan with HTTP 403
   ("API access is unavailable on the Free plan"). This provider gracefully catches this,
   flags the plan restriction with a 60s cooldown probe, and falls back to DEX Screener.
3. ZERO FABRICATION: Missing fields remain None and are tracked in missing_fields.
4. RECONFIGURABLE: Easily enabled via MOBULA_ENABLED=true and MOBULA_API_KEY.
5. RESILIENCE: Bounded LRU cache, concurrency bounding, and retries.
"""

import time
import logging
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from collections import OrderedDict
import aiohttp

from backend.market.base import BaseMarketDataProvider
from backend.models.events import NormalizedMarketEvent, MarketSource, EventQuality
from backend.config import settings

logger = logging.getLogger("predator.market.mobula")


class MobulaMarketProvider(BaseMarketDataProvider):
    """Adapter for Mobula multi-chain token details and market quotation."""

    RESTRICTION_COOLDOWN_SEC: float = 60.0
    MAX_CACHE_SIZE: int = 1000

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        enabled: Optional[bool] = None,
        timeout_seconds: Optional[float] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.base_url = (base_url or settings.MOBULA_API_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.MOBULA_API_KEY
        self.enabled = enabled if enabled is not None else settings.MOBULA_ENABLED
        self.timeout_seconds = timeout_seconds or settings.MOBULA_TIMEOUT_SECONDS

        self._session = session
        self._owns_session = session is None
        self._call_count = 0
        self._error_count = 0
        self._consecutive_failures = 0
        self._auth_restricted = False
        self._last_failure_timestamp: Optional[float] = None
        self._last_checked = time.time()
        self._total_latency_ms = 0.0
        self._last_error: Optional[str] = None

        # Bounded LRU cache: mint -> (NormalizedMarketEvent, cached_at)
        self._cache: OrderedDict[str, Tuple[NormalizedMarketEvent, float]] = OrderedDict()
        self._cache_ttl = settings.MOBULA_CACHE_TTL_SEC
        self._semaphore = asyncio.Semaphore(5)
        self._max_retries = settings.MOBULA_MAX_RETRIES

    @property
    def name(self) -> str:
        return "mobula"

    @property
    def source(self) -> MarketSource:
        return MarketSource.MOBULA

    @property
    def is_configured(self) -> bool:
        """True only if enabled and a valid API key string is present."""
        return self.enabled and bool(self.api_key and len(self.api_key.strip()) > 5)

    @property
    def is_available(self) -> bool:
        """Available only if configured, not in active restriction cooldown, and healthy."""
        if not self.is_configured:
            return False

        now = time.time()
        if self._auth_restricted:
            if self._last_failure_timestamp and (now - self._last_failure_timestamp > self.RESTRICTION_COOLDOWN_SEC):
                # Cooldown expired: allow a probe
                return True
            return False

        if self._consecutive_failures >= 3:
            if self._last_failure_timestamp and (now - self._last_failure_timestamp > self.RESTRICTION_COOLDOWN_SEC):
                return True
            return False

        return True

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def get_token_market_data(self, token_mint: str) -> Optional[NormalizedMarketEvent]:
        """Fetch token market quotation from Mobula with automatic plan-restriction detection."""
        if not self.is_configured or not self.is_available:
            return None

        now = time.time()
        self._last_checked = now

        # Cache lookup
        if token_mint in self._cache:
            cached_ev, cached_at = self._cache[token_mint]
            if now - cached_at <= self._cache_ttl:
                return cached_ev
            else:
                del self._cache[token_mint]

        url = f"{self.base_url}/api/2/token/details"
        params = {
            "chainId": "solana",
            "address": token_mint,
        }
        headers = {
            "Authorization": self.api_key,
            "Accept": "application/json",
        }

        async with self._semaphore:
            retries = self._max_retries
            for attempt in range(retries + 1):
                start_mono = time.perf_counter()
                self._call_count += 1
                try:
                    session = await self._get_session()
                    async with session.get(url, params=params, headers=headers) as resp:
                        status = resp.status
                        latency_ms = (time.perf_counter() - start_mono) * 1000.0
                        self._total_latency_ms += latency_ms

                        # Handle Mobula Free Plan restriction or Invalid Key (401/403)
                        if status in (401, 403):
                            body = await resp.text()
                            self._last_error = f"Mobula API rejected (HTTP {status}): {body[:150]}"
                            self._error_count += 1
                            self._consecutive_failures += 1
                            self._auth_restricted = True
                            self._last_failure_timestamp = time.time()
                            logger.warning("Mobula provider access restricted (%s). Falling back gracefully.", self._last_error)
                            return None

                        # Rate Limit (429)
                        if status == 429:
                            self._last_error = "Mobula Rate limit exceeded (HTTP 429)"
                            if attempt < retries:
                                await asyncio.sleep(1.0 * (attempt + 1))
                                continue
                            self._error_count += 1
                            self._consecutive_failures += 1
                            self._last_failure_timestamp = time.time()
                            return None

                        # Server error (5xx)
                        if status >= 500:
                            self._last_error = f"Mobula HTTP server error ({status})"
                            if attempt < retries:
                                await asyncio.sleep(0.5 * (attempt + 1))
                                continue
                            self._error_count += 1
                            self._consecutive_failures += 1
                            self._last_failure_timestamp = time.time()
                            return None

                        # Client error (4xx)
                        if status >= 400:
                            self._last_error = f"Mobula HTTP client error ({status})"
                            self._error_count += 1
                            self._consecutive_failures += 1
                            return None

                        data = await resp.json()
                        token_data = data.get("data") or {}
                        if not token_data:
                            return None

                        # Success: reset error/restriction state
                        self._consecutive_failures = 0
                        self._auth_restricted = False
                        self._last_error = None

                        # Extract metrics without fabricating missing numbers
                        price = token_data.get("price")
                        price_usd = float(price) if price is not None else None

                        liq = token_data.get("liquidity")
                        liquidity_usd = float(liq) if liq is not None else None

                        vol = token_data.get("volume24h") or token_data.get("volume_24h")
                        volume_24h = float(vol) if vol is not None else None

                        missing = []
                        if price_usd is None:
                            missing.append("price_usd")
                        if liquidity_usd is None:
                            missing.append("liquidity_usd")
                        if volume_24h is None:
                            missing.append("volume_24h_usd")

                        # Parse remote timestamp if present
                        source_ts = None
                        for ts_key in ("updated_at", "timestamp", "time", "created_at"):
                            val = token_data.get(ts_key)
                            if val is not None:
                                try:
                                    fval = float(val)
                                    if fval > 1e11:
                                        fval /= 1000.0
                                    source_ts = fval
                                    break
                                except (ValueError, TypeError):
                                    pass

                        if source_ts is not None:
                            age = max(0.0, now - source_ts)
                            freshness = round(age, 3)
                            is_stale = age > settings.DATA_STALENESS_THRESHOLD_SEC
                            freshness_verified = True
                        else:
                            age = 0.0
                            freshness = 0.0
                            is_stale = False
                            freshness_verified = False

                        if len(missing) >= 2:
                            obs_state = "MISSING"
                            quality = EventQuality.MISSING
                        elif is_stale:
                            obs_state = "STALE"
                            quality = EventQuality.STALE
                        elif not freshness_verified:
                            obs_state = "GENUINELY_OBSERVED"
                            quality = EventQuality.UNVERIFIED if not missing else EventQuality.DEGRADED
                        else:
                            obs_state = "GENUINELY_OBSERVED"
                            quality = EventQuality.EXCELLENT if not missing else EventQuality.ACCEPTABLE

                        event = NormalizedMarketEvent(
                            source=MarketSource.MOBULA,
                            event_id=f"mobula_{token_mint[:8]}_{int(now * 1000)}",
                            token_mint=token_mint,
                            pair_address=token_data.get("address"),
                            source_timestamp=source_ts,
                            local_receive_timestamp=now,
                            processing_timestamp=time.time(),
                            freshness_seconds=freshness,
                            price_usd=price_usd,
                            volume_24h_usd=volume_24h,
                            liquidity_usd=liquidity_usd,
                            observation_state=obs_state,
                            missing_fields=missing,
                            provider_latency_ms=round(latency_ms, 2),
                            quality=quality,
                            confidence_score=0.98 if not missing else 0.60,
                            metadata={
                                "symbol": token_data.get("symbol"),
                                "name": token_data.get("name"),
                                "market_cap": token_data.get("market_cap"),
                                "is_og": token_data.get("isOGCoin"),
                                "freshness_verified": freshness_verified,
                            },
                        )

                        self._cache[token_mint] = (event, now)
                        if len(self._cache) > self.MAX_CACHE_SIZE:
                            self._cache.popitem(last=False)

                        return event
                except Exception as e:
                    self._last_error = f"Mobula connection exception: {e}"
                    if attempt < retries:
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    self._error_count += 1
                    self._consecutive_failures += 1
                    self._last_failure_timestamp = time.time()
                    return None
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
        if not self.enabled:
            reason = "DISABLED_BY_CONFIG"
        elif not self.api_key:
            reason = "API_KEY_REQUIRED"
        elif self._auth_restricted:
            cooldown_rem = max(0.0, round(self.RESTRICTION_COOLDOWN_SEC - (time.time() - (self._last_failure_timestamp or 0.0)), 1))
            reason = f"AUTH_OR_PLAN_RESTRICTED (cooldown remaining: {cooldown_rem}s)"
        elif self._consecutive_failures >= 3:
            cooldown_rem = max(0.0, round(self.RESTRICTION_COOLDOWN_SEC - (time.time() - (self._last_failure_timestamp or 0.0)), 1))
            reason = f"CONSECUTIVE_FAILURES_CIRCUIT_OPEN (cooldown remaining: {cooldown_rem}s)"
        elif self._consecutive_failures > 0:
            reason = self._last_error or "CONNECTION_WARNING"
        else:
            reason = "ONLINE"

        return {
            "name": self.name,
            "source": self.source.value,
            "configured": self.is_configured,
            "enabled": self.enabled,
            "available": self.is_available,
            "reason": reason,
            "last_checked": self._last_checked,
            "call_count": self._call_count,
            "error_count": self._error_count,
            "consecutive_failures": self._consecutive_failures,
            "avg_latency_ms": avg_lat,
            "cache_size": len(self._cache),
            "auth_required": True,
            "last_error": self._last_error,
        }
