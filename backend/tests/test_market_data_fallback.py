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
from backend.market.mobula_provider import MobulaMarketProvider
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
        MobulaMarketProvider(),
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
    assert "AUTH_OR_BALANCE_RESTRICTED" in health["reason"]
    assert "Balance check rejected" in health["last_error"]


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

    # A. Genuinely Observed: Fresh price and liquidity with verified observation timestamp
    fresh_pair = {
        "chainId": "solana",
        "pairAddress": "PairFresh1",
        "baseToken": {"address": "TokenFresh", "symbol": "FRESH"},
        "priceUsd": "1.50",
        "liquidity": {"usd": 50000.0},
        "volume": {"h24": 100000.0},
        "pairCreatedAt": int((time.time() - 4.0) * 1000),  # 4s ago
    }
    dex_client.get_tokens_pairs = AsyncMock(return_value=[fresh_pair])
    ev1 = await provider.get_token_market_data("TokenFresh")
    assert ev1.observation_state == "GENUINELY_OBSERVED"
    assert ev1.quality in (EventQuality.EXCELLENT, EventQuality.ACCEPTABLE)
    assert ev1.metadata["freshness_verified"] is True

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

    # C. Stale Data: Source observation timestamp is 50s old (> 30s threshold)
    stale_pair = {
        "chainId": "solana",
        "pairAddress": "PairStale1",
        "baseToken": {"address": "TokenStale", "symbol": "STALE"},
        "priceUsd": "1.00",
        "liquidity": {"usd": 10000.0},
        "pairCreatedAt": int((time.time() - 50.0) * 1000),  # 50s ago
    }
    dex_client.get_tokens_pairs = AsyncMock(return_value=[stale_pair])
    ev3 = await provider.get_token_market_data("TokenStale")
    assert ev3 is not None
    assert ev3.observation_state == "STALE"
    assert ev3.quality == EventQuality.STALE
    assert ev3.freshness_seconds >= 50.0


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
    assert health["providers"]["mobula"]["configured"] is False
    assert health["providers"]["dex_screener"]["configured"] is True
    assert health["providers"]["solana_rpc"]["configured"] is True
    assert "last_checked" in health["providers"]["dex_screener"]
    assert "last_checked" in health["providers"]["solana_rpc"]
    assert "last_checked" in health["providers"]["mobula"]


# 11. Strict Staleness Invariant: Old Observation Does NOT Become Fresh on Arrival
@pytest.mark.asyncio
async def test_observation_timestamp_staleness_not_reset_by_fresh_receipt():
    dex_client = MagicMock()
    dex_client.base_url = "https://api.dexscreener.com"
    provider = DexScreenerProvider(client=dex_client)

    now = time.time()
    # Observation is from 10 minutes (600s) ago
    ancient_pair = {
        "chainId": "solana",
        "pairAddress": "PairAncient1",
        "baseToken": {"address": "TokenAncient", "symbol": "OLD"},
        "priceUsd": "0.50",
        "liquidity": {"usd": 20000.0},
        "volume": {"h24": 50000.0},
        "pairCreatedAt": int((now - 600.0) * 1000),
    }
    dex_client.get_tokens_pairs = AsyncMock(return_value=[ancient_pair])

    event = await provider.get_token_market_data("TokenAncient")
    assert event is not None
    # Crucial assertion: Fresh HTTP receipt timestamp does NOT make the data fresh
    assert event.local_receive_timestamp >= now - 1.0
    assert event.source_timestamp <= now - 590.0
    assert event.freshness_seconds >= 590.0
    assert event.observation_state == "STALE"
    assert event.quality == EventQuality.STALE


# 12. GMGN Availability Recalculation & Cooldown Probing Policy
@pytest.mark.asyncio
async def test_gmgn_cooldown_availability_recalculation():
    gmgn = GmgnMarketProvider(
        base_url="https://openapi.gmgn.ai",
        api_key="sk-gmgn-test-cooldown-key",
        enabled=True,
    )
    assert gmgn.is_available is True

    # Simulate restriction
    gmgn._auth_restricted = True
    gmgn._last_failure_timestamp = time.time()
    assert gmgn.is_available is False  # In cooldown

    # Simulate cooldown expiration (> 60.0s)
    gmgn._last_failure_timestamp = time.time() - 65.0
    # Policy: After cooldown elapses, availability is restored for a probe
    assert gmgn.is_available is True


# 13. GMGN Bounded TTL Cache Hit Prevents Redundant Requests
@pytest.mark.asyncio
async def test_gmgn_cache_hit_prevents_duplicate_calls():
    session_mock = MagicMock()
    session_mock.closed = False
    gmgn_data = {
        "code": 0,
        "data": {
            "symbol": "CACHED",
            "name": "Cached Token",
            "price": "3.14",
            "liquidity": 120000.0,
            "volume_24h": 500000.0,
            "updated_at": int(time.time()),
        }
    }
    session_mock.get.return_value = MockAiohttpResponse(200, json.dumps(gmgn_data))

    gmgn = GmgnMarketProvider(
        api_key="sk-gmgn-cache-test",
        enabled=True,
        session=session_mock,
    )

    ev1 = await gmgn.get_token_market_data("TokenCache11111111111111111111111111111111")
    assert ev1 is not None
    assert gmgn._call_count == 1

    # Second call for identical mint within TTL window should hit cache
    ev2 = await gmgn.get_token_market_data("TokenCache11111111111111111111111111111111")
    assert ev2 is not None
    assert ev2.price_usd == 3.14
    assert gmgn._call_count == 1  # No additional network request executed


# 14. Solana RPC Distinguishes Chain Truth from Market Pricing
@pytest.mark.asyncio
async def test_solana_rpc_distinguishes_chain_from_market_metrics():
    rpc_client = MagicMock()
    rpc_client.http_url = "https://api.mainnet-beta.solana.com"
    rpc_client._is_connected = True
    rpc_client.get_slot = AsyncMock(return_value=290888777)
    now = time.time()
    rpc_client.get_signatures_for_address = AsyncMock(return_value=[
        {"signature": "SigChainOnly1111111111111111111111111111111111", "blockTime": now - 10.0}
    ])
    rpc_provider = SolanaRpcProvider(client=rpc_client)

    ev = await rpc_provider.get_token_market_data("TokenChainOnly111111111111111111111111111")
    assert ev is not None
    assert ev.slot == 290888777
    assert ev.signature == "SigChainOnly1111111111111111111111111111111111"
    # Pricing is NOT fabricated
    assert ev.price_usd is None
    assert ev.liquidity_usd is None
    assert ev.volume_24h_usd is None
    # Observation state for market metrics is MISSING
    assert ev.observation_state == "MISSING"
    assert ev.metadata["on_chain_observed"] is True
    assert ev.metadata["on_chain_slot"] == 290888777


# 15. REST Endpoint Token Mint Validation & Status Code Distinction
@pytest.mark.asyncio
async def test_market_token_endpoint_validation_and_status_codes():
    from fastapi import HTTPException
    from backend.api.routes import get_token_market_data_endpoint

    composite_mock = MagicMock()
    composite_mock.is_available = True

    # A. Invalid base58 address raises HTTP 400
    with pytest.raises(HTTPException) as exc_info:
        await get_token_market_data_endpoint(token_mint="invalid!mint#", provider=composite_mock)
    assert exc_info.value.status_code == 400
    assert "Invalid Solana token mint" in exc_info.value.detail

    # B. All providers unavailable raises HTTP 503
    composite_down = MagicMock()
    composite_down.is_available = False
    valid_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    with pytest.raises(HTTPException) as exc_info:
        await get_token_market_data_endpoint(
            token_mint=valid_mint,
            provider=composite_down,
        )
    assert exc_info.value.status_code == 503
    assert "unavailable" in exc_info.value.detail

    # C. Token not found raises HTTP 404
    composite_mock.get_token_market_data = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc_info:
        await get_token_market_data_endpoint(
            token_mint=valid_mint,
            provider=composite_mock,
        )
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail


# 16. Telemetry Does NOT Leak Sensitive Secrets
@pytest.mark.asyncio
async def test_no_secret_leakage_in_health_telemetry():
    raw_secret = "secret-super-private-key-value-99999"
    gmgn = GmgnMarketProvider(
        base_url="https://openapi.gmgn.ai",
        api_key=raw_secret,
        enabled=True,
    )
    dex = DexScreenerProvider()
    rpc = SolanaRpcProvider()
    composite = CompositeMarketDataProvider(dex_screener=dex, solana_rpc=rpc, gmgn=gmgn)

    health = await composite.check_health()
    health_json = json.dumps(health)
    # Mandate: Zero secret leakage in API telemetry
    assert raw_secret not in health_json
    assert "Bearer" not in health_json


# 17. Paper Trading Continuity Under Market Provider Fallback
@pytest.mark.asyncio
async def test_paper_trading_continuity_under_provider_fallback():
    from backend.paper.positions import PositionManager
    from backend.models.paper import PaperPosition

    repo_mock = MagicMock()
    repo_mock.save_paper_position = AsyncMock()
    pm = PositionManager(repository=repo_mock)
    now = time.time()
    mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

    # Open simulated position on TokenX
    pos = PaperPosition(
        position_id="pos-fallback-1",
        token_mint=mint,
        token_symbol="SIMX",
        qty=100.0,
        average_entry_price_usd=1.0,
        current_price_usd=1.0,
        invested_capital_usd=100.0,
        current_value_usd=100.0,
        unrealized_pnl_usd=0.0,
        unrealized_pnl_pct=0.0,
        peak_price_usd=1.0,
        is_open=True,
        opened_at=now - 10.0,
    )
    await pm.add_position(pos)
    assert pos.is_open is True

    # GMGN is restricted, but Composite falls back to DEX Screener which returns $1.15
    dex_client = MagicMock()
    dex_client.base_url = "https://api.dexscreener.com"
    dex_pair = {
        "chainId": "solana",
        "pairAddress": "PairSim1",
        "baseToken": {"address": mint, "symbol": "SIMX"},
        "priceUsd": "1.15",
        "liquidity": {"usd": 80000.0},
        "volume": {"h24": 150000.0},
        "pairCreatedAt": int((now - 5.0) * 1000),
    }
    dex_client.get_tokens_pairs = AsyncMock(return_value=[dex_pair])
    dex_provider = DexScreenerProvider(client=dex_client)
    gmgn = GmgnMarketProvider(enabled=False)
    composite = CompositeMarketDataProvider(dex_screener=dex_provider, gmgn=gmgn)

    event = await composite.get_token_market_data(mint)
    assert event is not None
    assert event.source == MarketSource.DEX_SCREENER
    assert event.price_usd == 1.15

    # Mark to market with fallback price
    updated_pos = await pm.mark_to_market(
        token_mint=event.token_mint,
        current_price_usd=event.price_usd,
        freshness_seconds=event.freshness_seconds,
    )
    assert updated_pos is not None
    assert updated_pos.current_price_usd == 1.15
    assert updated_pos.unrealized_pnl_usd == pytest.approx(15.0, abs=0.01)
    assert updated_pos.unrealized_pnl_pct == pytest.approx(15.0, abs=0.01)


# 18. Mobula Unconfigured Safe State
@pytest.mark.asyncio
async def test_mobula_unconfigured_safe_state():
    mobula = MobulaMarketProvider(api_key="", enabled=False)
    assert mobula.is_configured is False
    assert mobula.is_available is False
    # Calling unconfigured provider returns None without any network request
    res = await mobula.get_token_market_data("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
    assert res is None
    health = await mobula.check_health()
    assert health["configured"] is False
    assert health["available"] is False
    assert health["reason"] == "DISABLED_BY_CONFIG"


# 19. Mobula Free Plan 403 Restriction Handling
@pytest.mark.asyncio
async def test_mobula_free_plan_403_restriction_handling():
    session_mock = MagicMock()
    session_mock.closed = False
    restriction_payload = {
        "message": "API access is unavailable on the Free plan",
        "error": "Forbidden",
        "statusCode": 403,
    }
    session_mock.get.return_value = MockAiohttpResponse(403, json.dumps(restriction_payload))

    mobula = MobulaMarketProvider(
        api_key="test-mobula-restricted-mock-key",
        enabled=True,
        session=session_mock,
    )
    assert mobula.is_configured is True
    assert mobula.is_available is True

    # Call should catch 403 and set _auth_restricted without raising
    res = await mobula.get_token_market_data("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
    assert res is None
    assert mobula.is_available is False
    assert mobula._auth_restricted is True

    health = await mobula.check_health()
    assert "AUTH_OR_PLAN_RESTRICTED" in health["reason"]
    # Ensure raw secret is not leaked in health reason or fields
    assert "test-mobula-restricted" not in json.dumps(health)


# 20. Mobula Valid Response Parsing Without Metric Fabrication
@pytest.mark.asyncio
async def test_mobula_valid_response_parsing_and_no_fabrication():
    session_mock = MagicMock()
    session_mock.closed = False
    now = time.time()
    mobula_data = {
        "data": {
            "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "symbol": "USDC",
            "name": "USD Coin",
            "price": "1.0001",
            "liquidity": "50000000.0",
            # volume24h is intentionally missing to verify zero-fabrication invariant
            "volume24h": None,
            "updated_at": int(now - 2.0),
        }
    }
    session_mock.get.return_value = MockAiohttpResponse(200, json.dumps(mobula_data))

    mobula = MobulaMarketProvider(
        api_key="test-mobula-valid-key",
        enabled=True,
        session=session_mock,
    )

    ev = await mobula.get_token_market_data("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
    assert ev is not None
    assert ev.source == MarketSource.MOBULA
    assert ev.price_usd == 1.0001
    assert ev.liquidity_usd == 50000000.0
    # Missing field is NOT fabricated
    assert ev.volume_24h_usd is None
    assert "volume_24h_usd" in ev.missing_fields
    assert ev.observation_state == "GENUINELY_OBSERVED"
    assert ev.quality == EventQuality.ACCEPTABLE


# 21. Composite Fallback: GMGN & Mobula Restricted -> DEX Screener
@pytest.mark.asyncio
async def test_composite_fallback_mobula_to_dex_screener():
    # GMGN disabled
    gmgn = GmgnMarketProvider(enabled=False)

    # Mobula restricted by 403
    mobula_session = MagicMock()
    mobula_session.closed = False
    mobula_payload = {"message": "API access is unavailable on the Free plan", "statusCode": 403}
    mobula_session.get.return_value = MockAiohttpResponse(403, json.dumps(mobula_payload))
    mobula = MobulaMarketProvider(
        api_key="test-mobula-restricted-mock-key",
        enabled=True,
        session=mobula_session,
    )

    # DEX Screener operational
    dex_client = MagicMock()
    dex_client.base_url = "https://api.dexscreener.com"
    mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    dex_pair = {
        "chainId": "solana",
        "pairAddress": "PairUSDC111",
        "baseToken": {"address": mint, "symbol": "USDC"},
        "priceUsd": "1.00",
        "liquidity": {"usd": 120000000.0},
        "volume": {"h24": 45000000.0},
        "pairCreatedAt": int((time.time() - 3600) * 1000),
    }
    dex_client.get_tokens_pairs = AsyncMock(return_value=[dex_pair])
    dex_provider = DexScreenerProvider(client=dex_client)

    composite = CompositeMarketDataProvider(
        gmgn=gmgn,
        mobula=mobula,
        dex_screener=dex_provider,
    )

    event = await composite.get_token_market_data(mint)
    assert event is not None
    assert event.source == MarketSource.DEX_SCREENER
    assert event.price_usd == 1.00
    assert event.liquidity_usd == 120000000.0
    assert "dex_screener" in event.metadata.get("fallback_path", [])
    assert event.metadata["provider_resolved"] == "dex_screener"


# 22. Mobula Cooldown Expiration Restores Availability for Probing
@pytest.mark.asyncio
async def test_mobula_cooldown_expiration_probing():
    mobula = MobulaMarketProvider(
        api_key="test-mobula-cooldown-key",
        enabled=True,
    )
    assert mobula.is_available is True

    # Simulate restriction
    mobula._auth_restricted = True
    mobula._last_failure_timestamp = time.time()
    assert mobula.is_available is False  # In cooldown

    # Simulate cooldown expiration (> 60s)
    mobula._last_failure_timestamp = time.time() - 65.0
    assert mobula.is_available is True  # Allowed to probe again

