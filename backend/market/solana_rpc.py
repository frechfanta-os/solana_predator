"""Read-only Solana RPC client and WebSocket listener for SOLANA PREDATOR.

SECURITY MANDATE:
- READ-ONLY ACCESS ONLY.
- NO PRIVATE KEYS. NO SEED PHRASES.
- NO TRANSACTION SIGNING OR BROADCAST LOGIC.
"""

import asyncio
import json
import time
import logging
import aiohttp
from typing import Optional, Dict, Any, List, Callable, Awaitable
from backend.config import settings

logger = logging.getLogger("predator.market.solana_rpc")


class SolanaRpcClient:
    """Read-only HTTP and WebSocket Solana RPC interface."""

    def __init__(
        self,
        http_url: Optional[str] = None,
        ws_url: Optional[str] = None,
        commitment: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self.http_url = http_url or settings.SOLANA_RPC_HTTP
        self.ws_url = ws_url or settings.SOLANA_RPC_WS
        self.commitment = commitment or settings.SOLANA_COMMITMENT
        self.timeout = timeout_seconds or settings.RPC_TIMEOUT_SECONDS
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_running = False
        self._ws_task: Optional[asyncio.Task] = None
        self._last_slot: Optional[int] = None
        self._reconnect_count = 0
        self._is_connected = False
        self._last_heartbeat = 0.0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Gracefully close HTTP session and WebSocket task."""
        self._ws_running = False
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        if self._session and not self._session.closed:
            await self._session.close()
        self._is_connected = False

    # --- Read-Only JSON-RPC Calls ---

    async def _call_rpc(self, method: str, params: list) -> Dict[str, Any]:
        """Execute a read-only RPC call with bounded retries and timeout."""
        session = await self._get_session()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        retries = settings.RPC_MAX_RETRIES
        backoff = 1.0

        for attempt in range(retries):
            try:
                async with session.post(self.http_url, json=payload) as resp:
                    if resp.status == 429:
                        logger.warning("Solana RPC rate-limited (429). Backing off %.1fs", backoff)
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2.0, settings.RPC_RECONNECT_MAX_BACKOFF)
                        continue
                    resp.raise_for_status()
                    data = await resp.json()
                    if "error" in data:
                        raise ValueError(f"Solana RPC error: {data['error']}")
                    self._last_heartbeat = time.time()
                    self._is_connected = True
                    return data.get("result", {})
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
                logger.warning("Solana RPC call %s attempt %d/%d failed: %s", method, attempt + 1, retries, e)
                if attempt == retries - 1:
                    self._is_connected = False
                    raise
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, settings.RPC_RECONNECT_MAX_BACKOFF)

        raise RuntimeError(f"Solana RPC call {method} failed after {retries} retries")

    async def get_slot(self) -> int:
        """Fetch current slot from network."""
        res = await self._call_rpc("getSlot", [{"commitment": self.commitment}])
        slot = int(res)
        self._last_slot = slot
        return slot

    async def get_latest_blockhash(self) -> Dict[str, Any]:
        """Fetch recent blockhash info for slot/network freshness verification."""
        return await self._call_rpc("getLatestBlockhash", [{"commitment": self.commitment}])

    async def get_signatures_for_address(self, address: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Fetch confirmed transaction signatures for a monitored token pool or whale wallet."""
        params = [address, {"limit": limit, "commitment": self.commitment}]
        res = await self._call_rpc("getSignaturesForAddress", params)
        return res if isinstance(res, list) else []

    async def get_parsed_transaction(self, signature: str) -> Optional[Dict[str, Any]]:
        """Fetch parsed transaction details for classified on-chain analysis."""
        params = [
            signature,
            {
                "encoding": "jsonParsed",
                "commitment": self.commitment,
                "maxSupportedTransactionVersion": 0,
            },
        ]
        try:
            return await self._call_rpc("getTransaction", params)
        except Exception as e:
            logger.debug("Failed to get transaction %s: %s", signature, e)
            return None

    async def get_token_account_balance(self, token_account_pubkey: str) -> Optional[Dict[str, Any]]:
        """Fetch token balance for a specific token account."""
        try:
            return await self._call_rpc("getTokenAccountBalance", [token_account_pubkey, {"commitment": self.commitment}])
        except Exception as e:
            logger.debug("Failed to get token account balance %s: %s", token_account_pubkey, e)
            return None

    # --- WebSocket Streaming with Bounded Backoff ---

    async def start_logs_subscription(
        self,
        mentions: List[str],
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Start managed WebSocket log subscription with automatic reconnection."""
        self._ws_running = True
        self._ws_task = asyncio.create_task(self._ws_subscription_loop(mentions, callback))

    async def _ws_subscription_loop(
        self,
        mentions: List[str],
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        backoff = 1.0
        while self._ws_running:
            try:
                session = await self._get_session()
                logger.info("Connecting to Solana WebSocket: %s", self.ws_url)
                async with session.ws_connect(self.ws_url, heartbeat=20.0) as ws:
                    self._is_connected = True
                    self._reconnect_count = 0
                    backoff = 1.0
                    logger.info("Solana WebSocket connected.")

                    # Subscribe to logs for each monitored mention
                    for mention in mentions:
                        sub_req = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "logsSubscribe",
                            "params": [
                                {"mentions": [mention]},
                                {"commitment": self.commitment},
                            ],
                        }
                        await ws.send_json(sub_req)

                    async for msg in ws:
                        if not self._ws_running:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            self._last_heartbeat = time.time()
                            if "params" in data and "result" in data["params"]:
                                log_result = data["params"]["result"]
                                await callback(log_result)
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            logger.warning("Solana WebSocket closed or error: %s", msg.data)
                            break
            except Exception as e:
                self._is_connected = False
                self._reconnect_count += 1
                logger.warning(
                    "Solana WebSocket connection failed (reconnect #%d): %s. Retrying in %.1fs",
                    self._reconnect_count,
                    e,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, settings.RPC_RECONNECT_MAX_BACKOFF)

    # --- Health & Diagnostic Inspection ---

    def get_health_status(self) -> Dict[str, Any]:
        now = time.time()
        age = now - self._last_heartbeat if self._last_heartbeat > 0 else -1.0
        return {
            "is_connected": self._is_connected,
            "last_slot": self._last_slot,
            "reconnect_count": self._reconnect_count,
            "heartbeat_age_sec": round(age, 2),
            "http_endpoint": self.http_url,
            "ws_endpoint": self.ws_url,
            "commitment": self.commitment,
        }
