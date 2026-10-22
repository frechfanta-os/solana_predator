"""Unit tests for Market Data Providers, Base Interface, and Resilient Fallback Hierarchy.

Verifies:
1. Common BaseMarketDataProvider interface compliance.
2. Unconfigured GMGN handling (clean None, no network calls, zero deposit attempts).
3. GMGN 401/403 balance restriction failover.
4. GMGN 429 rate limit failover.
5. Seamless fallback to DEX Screener and Solana RPC.
6. Explicit distinction between GENUINELY_OBSERVED, STALE, and MISSING data.
7. Zero fabrication invariant (unobserved values remain None).
8. Reconfigurability of GMGN without touching agents.
"""

import time
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from backend.market.base import BaseMarketDataProvider
from backend.market.dex_screener_provider import DexScreenerProvider
from backend.market.solana_rpc_provider import SolanaRpcProvider
from backend.market.gmgn_provider import GmgnMarketProvider
from backend.market.composite_provider import CompositeMarketDataProvider
from backend.models.events import NormalizedMarketEvent, MarketSource, EventQuality


class MockAiohttpResponse:
    def __init__(self, status: int, text_data: str):
        self.status = status
        self._text_data = text_data

    async def text(self) -> str:
        return self._text_data

    async def json(self) -> Any:
        return json.loads(self._text_data)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# 1. Interface Compliance Test
def test_interface_compliance():
    providers = [
        DexScreenerProvider(),
        SolanaRpcProvider(),
        GmgnMarketProvider(),
        CompositeMarketDataProvider(),
    ]
    for p in providers:
        assert isinstance(p, BaseMarketDataProvider)
        assert hasattr(p, "name")
        assert hasattr(p, "source")
        assert hasattr(p, "is_configured")
        assert hasattr(p, "is_available")
        assert hasattr(p, "get_token_market_data")
        assert hasattr(p, "get_token_pairs")
        assert hasattr(p, "check_health")
        assert hasattr(p, "close")


# 2. GMGN Unconfigured / Zero-Deposit Safe State
@pytest.mark.asyncio
async def test_gmgn_unconfigured_safe_state():
    gmgn = GmgnMarketProvider(api_key="", enabled=False)
    assert gmgn.is_configured is False
    assert gmgn.is_available is False

    # Calling get_token_market_data returns None immediately without network requests
    res = await gmgn.get_token_market_data("TokenTest11111111111111111111111111111111111")
    assert res is None

    health = await gmgn.check_health()
    assert health["configured"] is False
    assert health["available"] is False
    assert health["reason"] == "DISABLED_BY_CONFIG"


# 3. GMGN 401/403 Balance Restriction Fallback
@pytest.mark.asyncio
async def test_gmgn_balance_restriction_fallback():
    session_mock = MagicMock()
    session_mock.closed = False
    # Simulate GMGN 403 response indicating balance requirement of $100
    err_body = '{"code": 403, "message": "Account balance below required 100 USD threshold for API key generation"}'
    session_mock.get.return_value = MockAiohttpResponse(403, err_body)

    gmgn = GmgnMarketProvider(
        base_url="https://openapi.gmgn.ai",
        api_key="sk-gmgn-testkey-insufficient-funds",
        enabled=True,
        session=session_mock,
    )
    assert gmgn.is_configured is True

    # Attempt fetch
    res = await gmgn.get_token_market_data("TokenTest11111111111111111111111111111111111")
    assert res is None
    assert gmgn.is_available is False  # Marked unavailable after failure
    assert gmgn._error_count == 1

    health = await gmgn.check_health()
    assert health["available"] is False
    assert "Balance check rejected" in health["reason"]


# 4. GMGN 429 Rate Limit Handling
@pytest.mark.asyncio
async def test_gmgn_429_rate_limit_handling():
    session_mock = MagicMock()
    session_mock.closed = False
    session_mock.get.return_value = MockAiohttpResponse(429, '{"code": 429, "message": "Rate limit exceeded"}')

    gmgn = GmgnMarketProvider(
        base_url="https://openapi.gmgn.ai",
        api_key="sk-gmgn-testkey-valid",
        enabled=True,
        session=session_mock,
    )
    res = await gmgn.get_token_market_data("TokenTest11111111111111111111111111111111111")
    assert res is None
    assert gmgn._error_count == 1


# 5. Composite Fallback: GMGN Restricted -> DEX Screener Used
@pytest.mark.asyncio
async def test_composite_fallback_to_dex_screener():
    # GMGN fails with 403 (balance restricted)
    gmgn_session = MagicMock()
    gmgn_session.closed = False
    gmgn_session.get.return_value = MockAiohttpResponse(403, '{"message": "Balance required"}')
    gmgn = GmgnMarketProvider(
        api_key="sk-unfunded",
        enabled=True,
        session=gmgn_session,
    )

    # DEX Screener succeeds with standard Solana pair
    dex_client = MagicMock()
    dex_client.base_url = "https://api.dexscreener.com"
    dex_pair = {
        "chainId": "solana",
        "dexId": "raydium",
        "pairAddress": "PairSolana11111111111111111111111111111111",
        "baseToken": {"address": "TokenTest11111111111111111111111111111111111", "symbol": "TEST"},
        "quoteToken": {"symbol": "SOL"},
        "priceUsd": "2.45",
        "liquidity": {"usd": 150000.0},
        "volume": {"h24": 450000.0},
        "pairCreatedAt": int(time.time() * 1000) - 5000,
    }
    dex_client.get_tokens_pairs = AsyncMock(return_value=[dex_pair])
    dex_provider = DexScreenerProvider(client=dex_client)

    composite = CompositeMarketDataProvider(
        dex_screener=dex_provider,
        gmgn=gmgn,
    )

    # Request market data
    event = await composite.get_token_market_data("TokenTest11111111111111111111111111111111111")
    assert event is not None
    assert event.source == MarketSource.DEX_SCREENER
    assert event.price_usd == 2.45
    assert event.liquidity_usd == 150000.0
    assert event.observation_state == "GENUINELY_OBSERVED"
    assert event.quality == EventQuality.EXCELLENT


# 6. Composite Fallback: GMGN & DEX Down -> Solana RPC Truth Used
@pytest.mark.asyncio
async def test_composite_fallback_to_solana_rpc():
    gmgn = GmgnMarketProvider(enabled=False)
    
    # DEX Screener throws or returns nothing
    dex_client = MagicMock()
    dex_client.base_url = "https://api.dexscreener.com"
    dex_client.get_tokens_pairs = AsyncMock(return_value=[])
    dex_provider = DexScreenerProvider(client=dex_client)

    # Solana RPC returns on-chain slot and confirmed signatures
    rpc_client = MagicMock()
    rpc_client.http_url = "https://api.mainnet-beta.solana.com"
    rpc_client._is_connected = True
    rpc_client.get_slot = AsyncMock(return_value=250123456)
    rpc_client.get_signatures_for_address = AsyncMock(return_value=[
        {"signature": "5SigOnChain111111111111111111111111111111111111", "blockTime": time.time() - 2.0}
    ])
    rpc_provider = SolanaRpcProvider(client=rpc_client)

    composite = CompositeMarketDataProvider(
        dex_screener=dex_provider,
        solana_rpc=rpc_provider,
        gmgn=gmgn,
    )

    event = await composite.get_token_market_data("TokenTest11111111111111111111111111111111111")
    assert event is not None
    assert event.source == MarketSource.SOLANA_RPC
    assert event.slot == 250123456
    assert event.signature == "5SigOnChain111111111111111111111111111111111111"
    # Invariant: RPC does not fabricate price/liquidity
    assert event.price_usd is None
    assert event.liquidity_usd is None
    assert "price_usd" in event.missing_fields


# 7. Distinction between Observed, Stale, and Missing Data
@pytest.mark.asyncio
async def test_distinction_observed_stale_missing():
    dex_client = MagicMock()
    dex_client.base_url = "https://api.dexscreener.com"
    provider = DexScreenerProvider(client=dex_client)

    # A. Genuinely Observed: Fresh price and liquidity
    fresh_pair = {
        "chainId": "solana",
        "pairAddress": "PairFresh1",
        "baseToken": {"address": "TokenFresh", "symbol": "FRESH"},
        "priceUsd": "1.50",
        "liquidity": {"usd": 50000.0},
        "volume": {"h24": 100000.0},
    }
    dex_client.get_tokens_pairs = AsyncMock(return_value=[fresh_pair])
    ev1 = await provider.get_token_market_data("TokenFresh")
    assert ev1.observation_state == "GENUINELY_OBSERVED"
    assert ev1.quality in (EventQuality.EXCELLENT, EventQuality.ACCEPTABLE)

    # B. Missing Data: Missing both price and liquidity (never hallucinate)
    missing_pair = {
        "chainId": "solana",
        "pairAddress": "PairMissing1",
        "baseToken": {"address": "TokenMissing", "symbol": "MISS"},
        "priceUsd": None,
        "liquidity": {"usd": None},
        "volume": {"h24": None},
    }
    dex_client.get_tokens_pairs = AsyncMock(return_value=[missing_pair])
    ev2 = await provider.get_token_market_data("TokenMissing")
    assert ev2.observation_state == "MISSING"
    assert ev2.quality == EventQuality.MISSING
    assert "price_usd" in ev2.missing_fields
    assert "liquidity_usd" in ev2.missing_fields

    # C. Stale Data: Timestamp older than 30s threshold
    stale_pair = {
        "chainId": "solana",
        "pairAddress": "PairStale1",
        "baseToken": {"address": "TokenStale", "symbol": "STALE"},
        "priceUsd": "1.00",
        "liquidity": {"usd": 10000.0},
    }
    dex_client.get_tokens_pairs = AsyncMock(return_value=[stale_pair])
    ev3 = await provider.get_token_market_data("TokenStale")
    assert ev3 is not None
    # Simulate aging past staleness threshold (e.g. 45s ago)
    ev3.local_receive_timestamp = time.time() - 45.0
    provider._tag_observation_quality(ev3)
    assert ev3.observation_state == "STALE"
    assert ev3.quality == EventQuality.STALE


# 8. Zero Fabrication Invariant
@pytest.mark.asyncio
async def test_zero_fabrication_invariant():
    rpc_client = MagicMock()
    rpc_client.http_url = "https://api.mainnet-beta.solana.com"
    rpc_client._is_connected = True
    rpc_client.get_slot = AsyncMock(return_value=123)
    rpc_client.get_signatures_for_address = AsyncMock(return_value=[])
    rpc_provider = SolanaRpcProvider(client=rpc_client)

    ev = await rpc_provider.get_token_market_data("TokenZeroFab")
    assert ev.price_usd is None
    assert ev.liquidity_usd is None
    assert ev.volume_24h_usd is None
    assert len(ev.missing_fields) == 3


# 9. Reconfigurability of GMGN Without Agent Modification
@pytest.mark.asyncio
async def test_gmgn_activation_when_configured():
    session_mock = MagicMock()
    session_mock.closed = False
    gmgn_data = {
        "code": 0,
        "data": {
            "symbol": "ALPHA",
            "name": "AlphaToken",
            "price": "5.60",
            "liquidity": 2500000.0,
            "volume_24h": 8900000.0,
            "pair_address": "PairAlpha11111111111111111111111111111",
            "holder_count": 1420,
        }
    }
    session_mock.get.return_value = MockAiohttpResponse(200, json.dumps(gmgn_data))

    # GMGN configured with active key
    gmgn = GmgnMarketProvider(
        base_url="https://openapi.gmgn.ai",
        api_key="sk-gmgn-active-funded-key",
        enabled=True,
        session=session_mock,
    )
    assert gmgn.is_configured is True

    dex_provider = DexScreenerProvider()
    composite = CompositeMarketDataProvider(dex_screener=dex_provider, gmgn=gmgn)

    # GMGN is prioritized when configured and available
    ev = await composite.get_token_market_data("TokenAlphaMint111111111111111111111111111")
    assert ev is not None
    assert ev.source == MarketSource.GMGN
    assert ev.price_usd == 5.60
    assert ev.liquidity_usd == 2500000.0
    assert ev.volume_24h_usd == 8900000.0
    assert ev.observation_state == "GENUINELY_OBSERVED"


# 10. Provider Health API Route Telemetry
@pytest.mark.asyncio
async def test_provider_health_api_route():
    from backend.api.routes import get_market_providers_health

    dex = DexScreenerProvider()
    rpc = SolanaRpcProvider()
    gmgn = GmgnMarketProvider(enabled=False)
    composite = CompositeMarketDataProvider(dex_screener=dex, solana_rpc=rpc, gmgn=gmgn)

    health = await get_market_providers_health(provider=composite)
    assert health["status"] == "OPERATIONAL"
    assert health["active_primary_provider"] == "dex_screener"
    assert health["providers"]["gmgn"]["configured"] is False
    assert health["providers"]["dex_screener"]["configured"] is True
    assert health["providers"]["solana_rpc"]["configured"] is True
