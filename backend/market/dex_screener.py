"""DEX Screener REST adapter for SOLANA PREDATOR.

Compliant with DEX Screener public API specifications:
- Bounded rate limiting and batching (up to 30 addresses).
- Explicit timestamps for observation and data freshness.
- No fabricated prices or liquidity values.
"""

import time
import asyncio
import logging
import aiohttp
from typing import Optional, Dict, Any, List
from backend.config import settings

logger = logging.getLogger("predator.market.dex_screener")


class DexScreenerClient:
    """Async DEX Screener client with caching, batching, and rate limiting."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.DEXSCREENER_BASE_URL).rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Dict[str, Any]] = {}  # key -> {data, timestamp}
        self._cache_ttl = settings.DEXSCREENER_CACHE_TTL_SEC
        self._last_request_time = 0.0
        self._min_request_interval = 0.2  # Up to 300 requests/min
        self._lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=10.0)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, endpoint: str) -> Optional[Any]:
        """Make an HTTP GET request respecting rate limits."""
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self._min_request_interval:
                await asyncio.sleep(self._min_request_interval - elapsed)
            self._last_request_time = time.time()

        url = f"{self.base_url}{endpoint}"
        session = await self._get_session()

        for attempt in range(3):
            try:
                async with session.get(url) as resp:
                    if resp.status == 429:
                        wait = 2.0 * (attempt + 1)
                        logger.warning("DexScreener 429 rate limit hit on %s. Waiting %.1fs", endpoint, wait)
                        await asyncio.sleep(wait)
                        continue
                    if resp.status == 404:
                        return None
                    resp.raise_for_status()
                    return await resp.json()
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.debug("DexScreener error on %s attempt %d: %s", endpoint, attempt + 1, e)
                if attempt == 2:
                    return None
                await asyncio.sleep(1.0)
        return None

    # --- API Endpoints ---

    async def get_latest_token_profiles(self) -> List[Dict[str, Any]]:
        """Retrieve latest token profiles."""
        endpoint = "/token-profiles/latest/v1"
        data = await self._request(endpoint)
        if isinstance(data, list):
            return [
                {
                    "url": item.get("url"),
                    "chainId": item.get("chainId"),
                    "tokenAddress": item.get("tokenAddress"),
                    "icon": item.get("icon"),
                    "header": item.get("header"),
                    "description": item.get("description"),
                    "received_at": time.time(),
                }
                for item in data
                if item.get("chainId") == "solana"
            ]
        return []

    async def get_tokens_pairs(self, token_addresses: List[str]) -> List[Dict[str, Any]]:
        """Batch query pair information for up to 30 Solana token addresses."""
        if not token_addresses:
            return []

        # Deduplicate and batch up to 30 tokens
        clean_addresses = list(dict.fromkeys(token_addresses))[:30]
        cache_key = ",".join(clean_addresses)
        now = time.time()

        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if now - entry["timestamp"] < self._cache_ttl:
                return entry["data"]

        endpoint = f"/latest/dex/tokens/{cache_key}"
        raw = await self._request(endpoint)

        if not raw or "pairs" not in raw or not raw["pairs"]:
            return []

        pairs = [p for p in raw["pairs"] if p.get("chainId") == "solana"]
        self._cache[cache_key] = {"data": pairs, "timestamp": now}
        return pairs

    async def search_pairs(self, query: str) -> List[Dict[str, Any]]:
        """Search pairs by symbol, name, or address."""
        if not query.strip():
            return []
        endpoint = f"/latest/dex/search?q={query.strip()}"
        raw = await self._request(endpoint)
        if not raw or "pairs" not in raw or not raw["pairs"]:
            return []
        return [p for p in raw["pairs"] if p.get("chainId") == "solana"]

    async def get_pair_by_address(self, pair_address: str) -> Optional[Dict[str, Any]]:
        """Fetch market snapshot for a specific pair address."""
        cache_key = f"pair_{pair_address}"
        now = time.time()
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if now - entry["timestamp"] < self._cache_ttl:
                return entry["data"]

        endpoint = f"/latest/dex/pairs/solana/{pair_address}"
        raw = await self._request(endpoint)
        if not raw or "pair" not in raw:
            return None

        pair = raw.get("pair")
        if pair and pair.get("chainId") == "solana":
            self._cache[cache_key] = {"data": pair, "timestamp": now}
            return pair
        return None
