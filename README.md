# SOLANA PREDATOR — Multi-Desk Market-Intelligence Terminal

> **MANDATORY SECURITY NOTICE:**
> `LIVE MARKET DATA — PAPER TRADING ONLY (DEFAULT OPERATIONAL MODE)`
> By default, this software operates strictly in **Paper Trading** mode (`ALLOW_TRANSACTION_SIGNING=False`, `ALLOW_TRANSACTION_SUBMISSION=False`, `ALLOW_REAL_FUNDS=False`). The backend contains **NO private keys**, **NO seed phrases**, and **NO autonomous transaction signing capabilities**. A non-custodial Live Trading scaffolding (`backend/live/`) is included for trade proposal preparation and 13-point independent risk auditing, explicitly labeled **`DRY-RUN / NOT OPERATIONAL FOR MAINNET`** and hard-gated behind `ALLOW_TRANSACTION_SUBMISSION=False`.

SOLANA PREDATOR is an independent, low-latency **Multi-Desk Market-Intelligence Terminal**, multi-agent decision engine, measurable learning framework, and paper trading workstation designed for the Solana ecosystem. It runs as an autonomous Python/FastAPI backend paired with a reactive 10-destination Flutter dark workstation UI.

---

## Six Operational Desks (`backend/desks/` & `frontend/lib/views/`)

| Desk ID | Workstation Name | Assigned Agents | Primary Responsibility |
|---|---|---|---|
| **`DESK_MARKET`** | **Market Intelligence Desk** | `SCOUT` (`SCAN`), `VET` | Solana token discovery radar, pool liquidity/volume metrics, freshness age, and `GENUINELY_OBSERVED` / `STALE` / `MISSING` classification. |
| **`DESK_WHALE`** | **Whale Intelligence Desk** | `WHALE`, `CONVERGENCE` | Smart-money wallet flow tracking (`SWAP_INFLOW`, `SWAP_OUTFLOW`, `LP_CHANGE`, `FAILED`), convergence scoring, and wallet history sample guard ($\ge 10$ txs). |
| **`DESK_INVESTIGATION`** | **Token Investigation Desk** | `VET`, `FORENSICS` | On-demand token mint forensics, authority/holder inspection, composite market provider fallback trail, and single-token agent investigation (`POST /api/desks/DESK_INVESTIGATION/run`). |
| **`DESK_QUANT`** | **Quant Research Desk** | `QUANT`, `BACKTEST` | Momentum/turnover scoring, strict temporal split (`TRAIN`/`VALIDATION`/`TEST`) out-of-sample evaluation, and candidate strategy simulation. |
| **`DESK_RISK`** | **Risk & Skeptic Desk** | `RISK`, `SKEPTIC`, `SIZE` | **Authoritative non-overridable `RISK` veto**, contrarian `SKEPTIC` anomaly/honeypot detection, dynamic position sizing, 13-point server risk guard, and persistent SQLite Emergency Kill-Switch. |
| **`DESK_COMMAND`** | **Command Center Desk** | `CHIEF`, `AUDIT` | Central multi-desk supervision, cross-desk consensus synthesis, pause/resume/run desk controls, cross-desk watchlist, and structured event stream (`/ws/live`). |

---

## Operational Status Classification

| Component / Subsystem | Classification | Details & Verification Status |
|---|---|---|
| **Multi-Desk Coordinator & Scheduler (`backend/desks/`)** | **Opérationnel et testé** | 6 specialized desks, async task execution (`IDLE`, `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `DEGRADED`, `PAUSED`), SQLite Schema V4 persistence with 2,000-row retention pruning, and `/ws/live` envelopes. |
| **Multi-Agent Decision Engine (9 Agents)** | **Opérationnel et testé** | `CHIEF`, `SCAN`, `WHALE`, `VET`, `QUANT`, `SKEPTIC`, `SIZE`, `RISK`, `AUDIT`. Absolute `RISK` veto enforced and verified. |
| **Paper Trading Engine & Accounting** | **Opérationnel et testé** | Virtual order book, fee/slippage impact model, stop-loss/take-profit exit monitor, double-entry SQLite reconciliation on startup. |
| **Market Data: DEX Screener & Solana RPC** | **Opérationnel et testé** | Live read-only quotes, pool liquidity, slot/signature tracking, strict 30s staleness threshold, zero data fabrication (`None` preserved). |
| **Composite Market Provider & Failover** | **Opérationnel et testé** | Prioritized chain (`GMGN -> Mobula -> DEX Screener -> Solana RPC`) with automatic zero-downtime failover. |
| **Measurable Learning Engine** | **Opérationnel et testé** | Strict temporal split (`TRAIN`, `VALIDATION`, `TEST`), zero-lookahead evaluation, candidate strategy simulation. |
| **LLM Advisory Client (OpenRouter Pool)** | **Opérationnel et testé** | OpenAI-compatible client with multi-model quota rotation and deterministic mathematical fallback if unavailable. |
| **Flutter Multi-Desk Workstation UI (10 Destinations)** | **Opérationnel et testé** | 10-destination workstation navigation (`Command Center`, `Market Intelligence`, `Whale Intelligence`, `Token Investigation`, `Quant Research`, `Risk & Skeptic`, `Paper Portfolio`, `Agent Activity`, `Data Sources`, `Settings`) passing `flutter analyze` (0 issues) and widget test suite. |
| **Live Trading Module (`backend/live/`)** | **Implémenté mais mode Dry-Run / Non validé Mainnet** | Read-only public key connection, 13-point `IndependentRiskGuard`, persistent SQLite `emergency_kill_switch`. Explicitly marked `DRY-RUN / NOT OPERATIONAL FOR MAINNET` and locked (`ALLOW_TRANSACTION_SUBMISSION=False`). |
| **GMGN Market Provider** | **Désactivé / Soumis à restriction** | Disabled by default (`GMGN_ENABLED=false`). Requires $\ge \$100$ account balance on GMGN to generate an API key. |
| **Mobula Market Provider** | **Désactivé / Soumis à restriction** | Disabled by default (`MOBULA_ENABLED=false`). Blocked on Free plan (`HTTP 403 Forbidden`); requires paid Start-up plan ($50/mo). |
| **Server-Side Autonomous Signing** | **Non implémenté (Interdit)** | Intentionally excluded by security architecture. No private keys or signing routines exist in the backend. |

---

## Directory Structure

```
/root/solana_predator/
├── backend/
│   ├── api/             # FastAPI routes (routes.py), WebSocket manager (/ws & /ws/live), admin auth
│   ├── agents/          # 9-agent consensus engine (CHIEF, RISK, SKEPTIC, etc.)
│   ├── database/        # SQLite WAL schema (V1-V4), migrations, repository with retention pruning
│   ├── desks/           # MultiDeskCoordinator, 6-desk orchestration, watchlist, health transitions
│   ├── discovery/       # Token Radar and lifecycle state machine
│   ├── learning/        # Temporal split evaluator and strategy optimizer
│   ├── live/            # Non-custodial proposal manager, 13-point risk guard, dry-run broadcast
│   ├── llm/             # Multi-model OpenRouter/GLM client & prompt templates
│   ├── market/          # Composite provider, DexScreener, Solana RPC, GMGN, Mobula, normalizer
│   ├── models/          # Validated Pydantic contracts (events, agents, desk, portfolio)
│   ├── paper/           # Paper broker, positions, double-entry accounting, exit monitor
│   ├── pipeline/        # End-to-end engine orchestrator integrated with MultiDeskCoordinator
│   ├── scripts/         # Smoke test, latency benchmark, and soak test scripts
│   └── tests/           # 20 pytest test modules (116 automated tests)
├── frontend/
│   ├── lib/             # Flutter Multi-Desk workstation UI (10 navigation destinations + reusable desk components)
│   ├── test/            # Flutter widget tests (8 tests)
│   └── build/web/       # Compiled Web release
├── docs/                # Architecture (MULTI_DESK_ARCHITECTURE.md), security, and acceptance documentation
├── .github/workflows/   # CI workflows for backend and Flutter
└── worklog.md           # Complete engineering audit trail
```

---

## Quickstart & Verification Commands

### 1. Run the Backend API & Multi-Desk Pipeline
```bash
cd /root/solana_predator
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 2. Run Automated Test Suites
```bash
# Backend Pytest Suite (116 tests)
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
| `/api/system/health` | GET | Full workstation health snapshot (desks, providers, kill-switch, schema version) | No |
| `/api/desks` | GET | Status and telemetry of all 6 operational desks | No |
| `/api/desks/{desk_id}` | GET | Detailed status, tasks, and reports for a specific desk | No |
| `/api/desks/{desk_id}/agents` | GET | Agents assigned to a desk with execution metrics | No |
| `/api/desks/{desk_id}/tasks` | GET | Recent asynchronous task executions for a desk | No |
| `/api/desks/{desk_id}/reports` | GET | Structured agent reports emitted by a desk | No |
| `/api/desks/{desk_id}/pause` | POST | Pause scheduled task execution for a desk | `X-Admin-Key` |
| `/api/desks/{desk_id}/resume` | POST | Resume scheduled task execution for a desk | `X-Admin-Key` |
| `/api/desks/{desk_id}/run` | POST | Trigger immediate on-demand desk execution (e.g. token forensics) | No |
| `/api/agents` | GET | All 9 specialized agents with desk mappings and task statistics | No |
| `/api/agents/{agent_id}` | GET | Single agent profile, status, and recent reports | No |
| `/api/agents/{agent_id}/tasks` | GET | Task execution history for a specific agent | No |
| `/api/watchlist` | GET / POST | Cross-desk shared token watchlist | No |
| `/api/watchlist/{token_mint}` | DELETE | Remove token mint from shared watchlist | No |
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
| `/ws` & `/ws/live` | WebSocket | Streaming real-time updates and structured `TerminalWsEnvelope` events | No |
