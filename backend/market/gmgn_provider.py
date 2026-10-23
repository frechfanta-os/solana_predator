"""Optional GMGN OpenAPI market data provider for SOLANA PREDATOR.

DESIGN & CONSTRAINTS:
1. OPTIONAL: Can be disabled or absent without degrading terminal functionality.
2. ZERO DEPOSITS: Respects the platform rule to never deposit funds.
3. FAIL-SAFE: Gracefully returns None on unconfigured, 401/403 balance restrictions,
   429 rate limits, or timeouts, allowing instant fallback to DEX Screener & Solana RPC.
4. ZERO FABRICATION: Missing fields remain None and are tagged as MISSING.
5. RECONFIGURABLE: Easily re-enabled later via environment variables without modifying agents.
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

logger = logging.getLogger("predator.market.gmgn")


class GmgnMarketProvider(BaseMarketDataProvider):
    """Optional adapter for GMGN market quotation and token metrics.
    
    RESILIENCE & RELIABILITY:
    1. ZERO DEPOSITS: Strictly enforces the platform mandate never to deposit funds.
    2. RECALCULATED AVAILABILITY: Uses explicit cooldown probing (RESTRICTION_COOLDOWN_SEC)
       instead of permanent terminal disabling.
    3. BOUNDED TTL CACHE: In-memory LRU cache preventing duplicate network queries.
    4. CONCURRENCY BOUNDING: Semaphore-limited parallel outbound requests.
    5. STRICT STALENESS & TRACEABILITY: Calculates observation freshness from remote timestamps
       when available; never fabricates values or claims unverified data is fresh.
    """

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
        self.base_url = (base_url or settings.GMGN_API_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.GMGN_API_KEY
        self.enabled = enabled if enabled is not None else settings.GMGN_ENABLED
        self.timeout_seconds = timeout_seconds or settings.GMGN_TIMEOUT_SECONDS

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
        self._cache_ttl = settings.GMGN_CACHE_TTL_SEC
        self._semaphore = asyncio.Semaphore(5)
        self._max_retries = settings.GMGN_MAX_RETRIES

    @property
    def name(self) -> str:
        return "gmgn"

    @property
    def source(self) -> MarketSource:
        return MarketSource.GMGN

    @property
    def is_configured(self) -> bool:
        """True only if enabled and a valid API key string is present."""
        return self.enabled and bool(self.api_key and len(self.api_key.strip()) > 5)

    @property
    def is_available(self) -> bool:
        """Available only if configured, not in active restriction cooldown, and healthy.
        
        Explicit Availability Recalculation Policy:
        - When an auth/balance error or failure threshold is reached, provider enters
          cooldown for RESTRICTION_COOLDOWN_SEC.
        - After cooldown elapses, availability is restored to allow a controlled probe.
        - If the subsequent probe succeeds, the provider fully recovers.
        """
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
                # Cooldown expired: allow a probe
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
        """Fetch token market quotation from GMGN with bounded cache, retries, and strict staleness tracking.
        
        Returns None gracefully if unconfigured or restricted, enabling immediate fallback.
        """
        if not self.is_configured or not self.is_available:
            return None

        now = time.time()
        self._last_checked = now

        # 1. Bounded TTL cache lookup
        if token_mint in self._cache:
            cached_ev, cached_at = self._cache[token_mint]
            if now - cached_at <= self._cache_ttl:
                return cached_ev
            else:
                del self._cache[token_mint]

        url = f"{self.base_url}/defi/quotation/v1/tokens/sol/{token_mint}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        async with self._semaphore:
            retries = self._max_retries
            for attempt in range(retries + 1):
                start_mono = time.perf_counter()
                self._call_count += 1
                try:
                    session = await self._get_session()
                    async with session.get(url, headers=headers) as resp:
                        status = resp.status
                        latency_ms = (time.perf_counter() - start_mono) * 1000.0
                        self._total_latency_ms += latency_ms

                        # Auth / Balance restriction (e.g. 401/403 requires 100 USD balance)
                        if status in (401, 403):
                            body = await resp.text()
                            self._last_error = f"GMGN Authentication/Balance check rejected (HTTP {status}): {body[:150]}"
                            self._error_count += 1
                            self._consecutive_failures += 1
                            self._auth_restricted = True
                            self._last_failure_timestamp = time.time()
                            logger.warning("GMGN provider access restricted (%s). Falling back gracefully.", self._last_error)
                            return None

                        # Rate Limit (429)
                        if status == 429:
                            self._last_error = "GMGN Rate limit exceeded (HTTP 429)"
                            if attempt < retries:
                                await asyncio.sleep(1.0 * (attempt + 1))
                                continue
                            self._error_count += 1
                            self._consecutive_failures += 1
                            self._last_failure_timestamp = time.time()
                            return None

                        # Server error (5xx)
                        if status >= 500:
                            self._last_error = f"GMGN HTTP server error ({status})"
                            if attempt < retries:
                                await asyncio.sleep(0.5 * (attempt + 1))
                                continue
                            self._error_count += 1
                            self._consecutive_failures += 1
                            self._last_failure_timestamp = time.time()
                            return None

                        # Client error (4xx)
                        if status >= 400:
                            self._last_error = f"GMGN HTTP client error ({status})"
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

                        vol = token_data.get("volume_24h") or token_data.get("volume24h")
                        volume_24h = float(vol) if vol is not None else None

                        missing = []
                        if price_usd is None:
                            missing.append("price_usd")
                        if liquidity_usd is None:
                            missing.append("liquidity_usd")
                        if volume_24h is None:
                            missing.append("volume_24h_usd")

                        # Parse remote observation timestamp if available
                        source_ts = None
                        for ts_key in ("updated_at", "timestamp", "time", "last_trade_time"):
                            val = token_data.get(ts_key)
                            if val is not None:
                                try:
                                    fval = float(val)
                                    if fval > 1e11:  # ms to seconds
                                        fval /= 1000.0
                                    source_ts = fval
                                    break
                                except (ValueError, TypeError):
                                    pass

                        # Calculate freshness from observation timestamp
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
                            source=MarketSource.GMGN,
                            event_id=f"gmgn_{token_mint[:8]}_{int(now * 1000)}",
                            token_mint=token_mint,
                            pair_address=token_data.get("pair_address"),
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
                                "holder_count": token_data.get("holder_count"),
                                "swaps_24h": token_data.get("swaps_24h"),
                                "freshness_verified": freshness_verified,
                            },
                        )

                        # Cache insertion (bounded LRU)
                        self._cache[token_mint] = (event, now)
                        if len(self._cache) > self.MAX_CACHE_SIZE:
                            self._cache.popitem(last=False)

                        return event
                except Exception as e:
                    self._last_error = f"GMGN connection exception: {e}"
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
            reason = "ACCOUNT_BALANCE_THRESHOLD_REQUIRED_100USD"
        elif self._auth_restricted:
            cooldown_rem = max(0.0, round(self.RESTRICTION_COOLDOWN_SEC - (time.time() - (self._last_failure_timestamp or 0.0)), 1))
            reason = f"AUTH_OR_BALANCE_RESTRICTED (cooldown remaining: {cooldown_rem}s)"
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
