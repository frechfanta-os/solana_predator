# SOLANA PREDATOR

> **MANDATORY SECURITY NOTICE:**
> `LIVE MARKET DATA — PAPER TRADING ONLY`
> This software is strictly restricted to market intelligence gathering, multi-agent analysis, and simulated paper execution. It contains NO private keys, NO seed phrases, NO transaction signing logic, and NO blockchain broadcast capabilities.

SOLANA PREDATOR is an independent, low-latency market intelligence terminal and multi-agent paper trading simulator designed for the Solana ecosystem. It runs as an autonomous Python backend paired with a high-performance Flutter Web and Android reactive user interface.

---

## Key Features

1. **Deterministic Multi-Agent Engine**:
   - Coordinated evaluation by 9 specialized agents: `CHIEF`, `SCAN`, `WHALE`, `VET`, `QUANT`, `SKEPTIC`, `SIZE`, `RISK`, and `AUDIT`.
   - **Absolute Risk Veto Power**: The `RISK` agent enforces inviolable drawdown circuit breakers and position limits. No agent or consensus mechanism can override a risk veto.
   - LLM optional advisory hook outside the critical path with strict timeout fallback.

2. **Real-Time Data Normalization & Deduplication**:
   - Read-only Solana RPC client with slot tracking, commitment level management, and exponential backoff reconnection.
   - DEX Screener REST client with rate-limiting, batching (up to 30 tokens), and TTL caching.
   - Bounded LRU/TTL deduplication filter preventing duplicate signature and event processing.
   - Explicit separation of timestamps: Source Time, Receive Time, Processing Time, and Freshness.

3. **Whale Intelligence & Convergence**:
   - Tracks configurable public Solana wallet addresses without speculative owner identity inference.
   - Classifies on-chain transactions strictly into `SWAP`, `TRANSFER`, `DEPOSIT_WITHDRAW`, and `UNKNOWN_AMBIGUOUS`.
   - Calculates a non-speculative Whale Convergence indicator factoring in cluster correlations and independent wallet activity.

4. **Paper Trading Simulator & Exit Monitor**:
   - Completely isolated virtual broker executing orders against simulated liquidity pools.
   - Realistic market impact and slippage models: Base slippage + depth impact + 25 bps taker fee.
   - Partial and failed simulated fills when order sizes exceed 5% of available pool depth.
   - Continuous exit monitoring: Stop Loss (-15%), Take Profit (+50%), Trailing Stop (-20%), Liquidity Collapse warning, and Whale Outflow detection.
   - Startup reconciliation re-computing balances and realized PnL against persistent SQLite records.

5. **Flutter Reactive Terminal**:
   - 10 comprehensive terminal views: Market Overview, Token Radar, Whale Activity, Agent Decisions, Paper Portfolio, Positions, Exit Monitor, Event Log, Health & Latency, and Configuration & Risk Limits.
   - Responsive design supporting Desktop Web terminals and Android mobile navigation.
   - Configurable backend URL with automatic WebSocket reconnection.

---

## Directory Structure

```
/root/solana_predator/
├── backend/
│   ├── api/             # FastAPI routes, WebSocket manager, admin auth
│   ├── agents/          # Multi-agent engine (CHIEF, RISK, SCAN, etc.)
│   ├── database/        # SQLite WAL schema, migrations, repository
│   ├── discovery/       # Token Radar and lifecycle state machine
│   ├── market/          # Solana RPC, DexScreener, normalizer, event bus, replay
│   ├── models/          # Validated Pydantic contracts
│   ├── paper/           # Paper broker, positions, accounting, exit monitor
│   ├── pipeline/        # End-to-end engine orchestrator
│   ├── scripts/         # Live smoke test and utility scripts
│   └── tests/           # 28 comprehensive pytest test suites
├── frontend/
│   ├── lib/             # Flutter terminal UI (10 views, Riverpod state)
│   ├── test/            # Flutter widget and unit tests
│   └── build/web/       # Pre-compiled production Web release
├── docs/                # Comprehensive architectural and operational documentation
├── .github/workflows/   # CI workflows for backend and frontend
└── worklog.md           # Implementation audit trail
```

---

## Quickstart & Launch Commands

### 1. Run the Backend API & Pipeline
```bash
cd /root/solana_predator
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 2. Run Backend Tests
```bash
cd /root/solana_predator
pytest -v backend/tests/
```

### 3. Run Live Data Smoke Test
```bash
python3 /root/solana_predator/backend/scripts/live_smoke_test.py
```

### 4. Build or Serve Flutter Web Terminal
```bash
cd /root/solana_predator/frontend
flutter build web --release
# Serve with any static web server:
python3 -m http.server 8080 --directory build/web
```

---

## API Endpoints Summary

| Endpoint | Method | Description | Auth Required |
|---|---|---|---|
| `/api/health` | GET | System health, uptime, and sub-system status | No |
| `/api/state` | GET | Aggregate state of tokens, positions, and cash | No |
| `/api/market/tokens` | GET | Registry of discovered tokens and lifecycles | No |
| `/api/market/events` | GET | Recent normalized market events | No |
| `/api/whales` | GET | Classified whale activities and flows | No |
| `/api/agents/decisions`| GET | Multi-agent consensus records | No |
| `/api/paper/portfolio`| GET | Simulated portfolio, equity, and drawdown | No |
| `/api/paper/positions`| GET | Active and historical paper positions | No |
| `/api/paper/orders` | GET | Audit log of paper orders and fills | No |
| `/api/metrics` | GET | Percentile latencies (p50, p95, p99) and queues | No |
| `/api/simulation/start_replay` | POST | Trigger deterministic test replay | `X-Admin-Key` |
| `/api/paper/reset` | POST | Reset simulated capital to initial state | `X-Admin-Key` |
| `/ws` | WebSocket | Streaming real-time updates and signals | No |
