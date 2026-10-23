# SOLANA PREDATOR

> **MANDATORY SECURITY NOTICE:**
> `LIVE MARKET DATA — PAPER TRADING ONLY (DEFAULT OPERATIONAL MODE)`
> By default, this software operates strictly in **Paper Trading** mode (`ALLOW_TRANSACTION_SIGNING=False`, `ALLOW_TRANSACTION_SUBMISSION=False`, `ALLOW_REAL_FUNDS=False`). The backend contains **NO private keys**, **NO seed phrases**, and **NO autonomous transaction signing capabilities**. A non-custodial Live Trading scaffolding (`backend/live/`) is included for trade proposal preparation and 13-point independent risk auditing, operating in dry-run mode unless explicitly connected to an external user signer.

SOLANA PREDATOR is an independent, low-latency market intelligence terminal, multi-agent decision engine, measurable learning framework, and paper trading simulator designed for the Solana ecosystem. It runs as an autonomous Python/FastAPI backend paired with a reactive Flutter Web and Android user interface.

---

## Operational Status Classification

| Component / Subsystem | Classification | Details & Verification Status |
|---|---|---|
| **Multi-Agent Decision Engine (9 Agents)** | **Opérationnel et testé** | `CHIEF`, `SCAN`, `WHALE`, `VET`, `QUANT`, `SKEPTIC`, `SIZE`, `RISK`, `AUDIT`. Absolute `RISK` veto enforced and verified. |
| **Paper Trading Engine & Accounting** | **Opérationnel et testé** | Virtual order book, fee/slippage impact model, stop-loss/take-profit exit monitor, double-entry SQLite reconciliation on startup. |
| **Market Data: DEX Screener & Solana RPC** | **Opérationnel et testé** | Live read-only quotes, pool liquidity, slot/signature tracking, strict 30s staleness threshold, zero data fabrication (`None` preserved). |
| **Composite Market Provider & Failover** | **Opérationnel et testé** | Prioritized chain (`GMGN -> Mobula -> DEX Screener -> Solana RPC`) with automatic zero-downtime failover. |
| **Measurable Learning Engine** | **Opérationnel et testé** | Strict temporal split (`TRAIN`, `VALIDATION`, `TEST`), zero-lookahead evaluation, candidate strategy simulation. |
| **LLM Advisory Client (OpenRouter Pool)** | **Opérationnel et testé** | OpenAI-compatible client with multi-model quota rotation and deterministic mathematical fallback if unavailable. |
| **Flutter Terminal UI (12 Views)** | **Opérationnel et testé** | 12 views passing `flutter analyze` (0 issues) and widget test suite (5/5 passed). |
| **Live Trading Module (`backend/live/`)** | **Implémenté mais mode Dry-Run / Non validé Mainnet** | Read-only public key connection, 13-point `IndependentRiskGuard`, persistent SQLite `emergency_kill_switch`. Locked in dry-run (`ALLOW_TRANSACTION_SUBMISSION=False`); local constant-product quote model; Flutter UI uses mock signature payload pending native Wallet Adapter SDK. |
| **GMGN Market Provider** | **Désactivé / Soumis à restriction** | Disabled by default (`GMGN_ENABLED=false`). Requires $\ge \$100$ account balance on GMGN to generate an API key. |
| **Mobula Market Provider** | **Désactivé / Soumis à restriction** | Disabled by default (`MOBULA_ENABLED=false`). Blocked on Free plan (`HTTP 403 Forbidden`); requires paid Start-up plan ($50/mo). |
| **Server-Side Autonomous Signing** | **Non implémenté (Interdit)** | Intentionally excluded by security architecture. No private keys or signing routines exist in the backend. |

---

## Key Features

1. **Deterministic Multi-Agent Engine**:
   - Coordinated evaluation by 9 specialized agents: `CHIEF`, `SCAN`, `WHALE`, `VET`, `QUANT`, `SKEPTIC`, `SIZE`, `RISK`, and `AUDIT`.
   - **Absolute Risk Veto Power**: The `RISK` agent enforces inviolable drawdown circuit breakers and position limits. No agent, consensus mechanism, or LLM advisory can override a risk veto.
   - Optional LLM qualitative advisory hook outside the critical path with strict timeout and mathematical fallback.

2. **Pluggable Market Data & Strict Quality Invariants**:
   - Common `BaseMarketDataProvider` contract across `GmgnMarketProvider`, `MobulaMarketProvider`, `DexScreenerProvider`, and `SolanaRpcProvider`.
   - Explicit classification into `GENUINELY_OBSERVED`, `STALE` (>30s observation age), `MISSING`, and `UNVERIFIED`.
   - Zero fabrication invariant: missing prices or liquidity remain `None` and are tracked in `missing_fields`.

3. **Whale Intelligence & Convergence**:
   - Tracks public Solana wallet addresses and classifies transactions into `SWAP`, `TRANSFER`, `DEPOSIT_WITHDRAW`, `LP_CHANGE`, and `UNKNOWN_AMBIGUOUS`.
   - Computes Whale Convergence scores factoring in cluster correlations and independent wallet activity.

4. **Paper Trading Simulator & Exit Monitor**:
   - Isolated virtual broker executing orders against observed pool liquidity with base slippage + depth impact + 25 bps taker fee.
   - Continuous exit monitoring: Stop Loss (-15%), Take Profit (+50%), Trailing Stop (-20%), and Liquidity Collapse emergency exit.
   - Note: *Simulated paper trading performance does not predict or guarantee future real-market performance.*

5. **Non-Custodial Live Guardrails (`backend/live/`)**:
   - 13 independent server-side risk checks (`IndependentRiskGuard`) including persistent SQLite Emergency Kill-Switch, rent reserve preservation, max trade size, and slippage bounds.
   - Hard-gated by `ALLOW_TRANSACTION_SUBMISSION = False` to prevent unintended on-chain broadcast.

---

## Directory Structure

```
/root/solana_predator/
├── backend/
│   ├── api/             # FastAPI routes (routes.py), WebSocket manager, admin auth
│   ├── agents/          # 9-agent consensus engine (CHIEF, RISK, SKEPTIC, etc.)
│   ├── database/        # SQLite WAL schema (V1-V3), migrations, repository
│   ├── discovery/       # Token Radar and lifecycle state machine
│   ├── learning/        # Temporal split evaluator and strategy optimizer
│   ├── live/            # Non-custodial proposal manager, 13-point risk guard, dry-run broadcast
│   ├── llm/             # Multi-model OpenRouter/GLM client & prompt templates
│   ├── market/          # Composite provider, DexScreener, Solana RPC, GMGN, Mobula, normalizer
│   ├── models/          # Validated Pydantic data contracts
│   ├── paper/           # Paper broker, positions, double-entry accounting, exit monitor
│   ├── pipeline/        # End-to-end engine orchestrator
│   ├── scripts/         # Smoke test, latency benchmark, and soak test scripts
│   └── tests/           # 19 pytest test modules (111 automated tests)
├── frontend/
│   ├── lib/             # Flutter terminal UI (12 views, Riverpod state management)
│   ├── test/            # Flutter widget tests (5 tests)
│   └── build/web/       # Compiled Web release
├── docs/                # Architectural, security, and acceptance documentation
├── .github/workflows/   # CI workflows for backend and Flutter
└── worklog.md           # Complete engineering audit trail
```

---

## Quickstart & Verification Commands

### 1. Run the Backend API & Pipeline
```bash
cd /root/solana_predator
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 2. Run Automated Test Suites
```bash
# Backend Pytest Suite (111 tests)
cd /root/solana_predator
python3 -m pytest backend/tests/ -v

# Frontend Flutter Tests & Static Analysis
cd /root/solana_predator/frontend
flutter analyze
flutter test
```

---

## API Endpoints Summary (`backend/api/routes.py`)

| Endpoint | Method | Description | Auth Required |
|---|---|---|---|
| `/api/health` | GET | System health, uptime, and sub-system status | No |
| `/api/state` | GET | Aggregate state of tokens, positions, and cash | No |
| `/api/market/providers` | GET | Health, latency, and status of all market providers | No |
| `/api/market/token/{token_mint}` | GET | Normalized market data with automatic composite failover | No |
| `/api/market/tokens` | GET | Registry of discovered tokens and lifecycles | No |
| `/api/market/events` | GET | Recent normalized market events | No |
| `/api/whales` | GET | Classified whale activities and flows | No |
| `/api/agents/decisions` | GET | Multi-agent consensus records | No |
| `/api/paper/portfolio` | GET | Simulated portfolio, equity, and drawdown | No |
| `/api/paper/positions` | GET | Active and historical paper positions | No |
| `/api/paper/orders` | GET | Audit log of paper orders and fills | No |
| `/api/paper/reset` | POST | Reset simulated capital to initial state | `X-Admin-Key` |
| `/api/simulation/start_replay` | POST | Trigger deterministic test replay | `X-Admin-Key` |
| `/api/learning/metrics` | GET | Out-of-sample decision accuracy & temporal metrics | No |
| `/api/learning/evaluate` | POST | Trigger historical decision outcome evaluation | `X-Admin-Key` |
| `/api/learning/simulate` | POST | Simulate candidate strategy parameters | `X-Admin-Key` |
| `/api/llm/status` | GET | LLM provider configuration & connectivity telemetry | No |
| `/api/llm/analyze` | POST | Request structured qualitative agent advisory | No |
| `/api/live/wallet/connect` | POST | Connect read-only Solana public key | No |
| `/api/live/wallet/disconnect` | POST | Disconnect active public key | No |
| `/api/live/wallet/status` | GET | Active public key and observable balances | No |
| `/api/live/proposals` | GET | List trade proposals and 13-point risk checklists | No |
| `/api/live/proposals/create` | POST | Prepare unsigned proposal with server-side risk audit | No |
| `/api/live/proposals/{id}/broadcast` | POST | Submit signed tx (dry-run gated by `ALLOW_TRANSACTION_SUBMISSION`) | No |
| `/api/live/proposals/{id}/reject` | POST | Explicitly reject a trade proposal | No |
| `/api/live/transactions` | GET | List broadcast transaction records | No |
| `/api/live/kill-switch` | POST | Engage/disengage persistent SQLite Emergency Kill-Switch | `X-Admin-Key` |
| `/api/live/risk-audit` | GET | Audit log of independent risk verifications | No |
| `/api/metrics` | GET | Percentile latencies (p50, p95, p99) and queues | No |
| `/ws` | WebSocket | Streaming real-time updates and signals | No |

