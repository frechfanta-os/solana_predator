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

---

## 2. Data Freshness and Quality Policy

- **No Data Fabrication**: The normalizer strictly assigns `None` to missing prices, liquidity, or volume values. The system never substitutes artificial baseline values for missing telemetry.
- **Quality Classifications**:
  - `EXCELLENT`: Source timestamp verified, verified price & liquidity, freshness < 5s.
  - `ACCEPTABLE`: Verified feed data, freshness < 30s.
  - `DEGRADED`: Missing liquidity or volume, but valid mint structure.
  - `STALE`: Data age exceeds `DATA_STALENESS_THRESHOLD_SEC` (30s).
  - `UNVERIFIED`: Unconfirmed logs or raw traces without confirmation.
