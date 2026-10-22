# Data Sources Specification — SOLANA PREDATOR

## 1. Primary Data Providers

### Solana Read-Only RPC
- **Protocol**: HTTP JSON-RPC 2.0 and WebSocket Subscriptions.
- **Default Endpoints**:
  - HTTP: `https://api.mainnet-beta.solana.com`
  - WS: `wss://api.mainnet-beta.solana.com`
- **Supported Commitment**: `confirmed` (configurable to `finalized` or `processed`).
- **Methods Utilized**:
  - `getSlot`: Current slot monitoring and clock skew tracking.
  - `getLatestBlockhash`: Slot freshness verification.
  - `getSignaturesForAddress`: Confirmed transaction signatures for pool contracts or whale addresses.
  - `getTransaction`: Parsed transaction detail (`jsonParsed`) for on-chain instruction analysis.
  - `getTokenAccountBalance`: Token account balance inspection.
  - `logsSubscribe`: Managed WebSocket streaming with bounded exponential backoff reconnection.
- **Safety Invariant**: No transaction signing or submission methods exist in the client.

### DEX Screener Public REST API
- **Protocol**: HTTPS REST.
- **Base URL**: `https://api.dexscreener.com`.
- **Endpoints Utilized**:
  - `/token-profiles/latest/v1`: Newly promoted/active token profiles on Solana.
  - `/latest/dex/tokens/{tokenAddresses}`: Batch pair querying for up to 30 Solana token addresses.
  - `/latest/dex/search?q={query}`: Query pair lookups.
  - `/latest/dex/pairs/solana/{pairAddress}`: Specific market snapshot per pool.
- **Rate Limit Policy**:
  - Minimum request interval: 0.20s (max 300 requests/minute).
  - Exponential backoff upon receiving HTTP 429.
  - Response caching with configurable TTL (default: 15.0 seconds).
  - Explicit freshness computation: `freshness = receive_timestamp - source_timestamp`.

### Deterministic Replay Provider
- **Purpose**: Zero-network offline testing and deterministic verification.
- **Dataset**: Pre-constructed realistic Solana meme/defi event sequences containing token discovery, early whale accumulation, momentum expansion, and sudden whale exit sell events.
- **Mode of Operation**: Injects normalized events into the EventBus at variable replay speeds.

### GMGN OpenAPI Adapter (Optional & Pluggable)
- **Protocol**: HTTPS REST JSON (`https://openapi.gmgn.ai`).
- **Endpoints**: `/defi/quotation/v1/tokens/sol/{token_mint}`.
- **Account Balance Restriction**: GMGN currently requires an on-chain account balance of at least 100 USD to generate an active OpenAPI key.
- **Strict Invariant**: No funds are ever deposited to bypass restrictions. The provider is completely optional (`GMGN_ENABLED=False` by default).
- **Graceful Fallback**: If unconfigured, disabled, rate-limited (HTTP 429), or balance-restricted (HTTP 401/403), the adapter returns `None` immediately, allowing seamless and zero-downtime fallback to DEX Screener and Solana RPC.
- **Seamless Re-activation**: GMGN can be re-activated at any time simply by setting `GMGN_ENABLED=true` and `GMGN_API_KEY=...` in local environment variables, with no code or agent modifications required.

---

## 2. Common Market Data Provider Architecture

All market data ingestion is abstracted through the `BaseMarketDataProvider` interface (`backend/market/base.py`):
```python
class BaseMarketDataProvider(ABC):
    @property
    def name(self) -> str: ...
    @property
    def source(self) -> MarketSource: ...
    @property
    def is_configured(self) -> bool: ...
    @property
    def is_available(self) -> bool: ...
    async def get_token_market_data(self, token_mint: str) -> Optional[NormalizedMarketEvent]: ...
    async def get_token_pairs(self, token_addresses: List[str]) -> List[NormalizedMarketEvent]: ...
    async def check_health(self) -> Dict[str, Any]: ...
    async def close(self) -> None: ...
```

### Providers & Composite Failover
1. **`GmgnMarketProvider`**: Priority 1 when configured and available; marks itself unavailable upon 401/403 balance restriction.
2. **`DexScreenerProvider`**: Priority 2 primary source for free, public price, liquidity, volume, and pair quotes.
3. **`SolanaRpcProvider`**: Priority 3 on-chain fallback for verified slot, blockhash, and transaction activity.
4. **`CompositeMarketDataProvider`**: Orchestrates failover order (`GMGN -> DEX Screener -> Solana RPC`), tracks telemetry, latency, and assigns observation states.

---

## 3. Data Freshness and Quality Policy

- **No Data Fabrication**: The normalizer and providers strictly assign `None` to missing prices, liquidity, or volume values. The system never substitutes artificial baseline values for missing telemetry.
- **Observation States**:
  - `GENUINELY_OBSERVED`: Observed directly from active, fresh market feeds.
  - `STALE`: Data age exceeds `DATA_STALENESS_THRESHOLD_SEC` (30s).
  - `MISSING`: Data unavailable or incomplete across all providers; missing fields explicitly tracked in `missing_fields`.
- **Quality Classifications**:
  - `EXCELLENT`: Source timestamp verified, verified price & liquidity, freshness < 5s.
  - `ACCEPTABLE`: Verified feed data, freshness < 30s.
  - `DEGRADED`: Missing liquidity or volume, but valid mint structure.
  - `STALE`: Data age exceeds threshold.
  - `MISSING`: Critical fields unavailable without fallback.
  - `UNVERIFIED`: Unconfirmed logs or raw traces without confirmation.
