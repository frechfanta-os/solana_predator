# Test Plan & Verification Matrix — SOLANA PREDATOR

## 1. Backend Verification Matrix (28 Tests)

| Test Module | Coverage Scope | Status |
|---|---|---|
| `test_security_boundary.py` | Verify hardcoded security settings, absence of signing methods, and regex source code scan. | **PASS** |
| `test_normalization.py` | Event normalization, deduplication cache LRU/TTL, non-fabrication of prices. | **PASS** |
| `test_event_bus.py` | Asynchronous pub/sub, bounded queue backpressure, high-water mark, overflow drop policy. | **PASS** |
| `test_token_radar.py` | Discovery lifecycle transitions (`DISCOVERED` -> `OBSERVED` -> `PAPER_CANDIDATE`), timestamps. | **PASS** |
| `test_whale_intelligence.py` | Classification of `SWAP`, `TRANSFER`, `UNKNOWN_AMBIGUOUS`, signature deduplication, convergence score. | **PASS** |
| `test_agents.py` | Output contract compliance for all 9 agents, monotonic clock latency measurements. | **PASS** |
| `test_risk_veto.py` | Enforce max drawdown veto, max concurrent positions veto, proof that CHIEF cannot override RISK. | **PASS** |
| `test_paper_broker.py` | Simulated buy/sell execution, 25 bps taker fee, depth impact slippage, partial fills on depth limits. | **PASS** |
| `test_accounting_reconciliation.py` | Audit reconciliation of cash balance and realized PnL across cold restarts. | **PASS** |
| `test_exit_monitor.py` | Stop loss, take profit, trailing stops, liquidity collapse emergency exit, whale dumps. | **PASS** |
| `test_database_recovery.py` | SQLite WAL mode verification, schema version tracking, unclean shutdown data recovery. | **PASS** |
| `test_api_and_websocket.py` | Health endpoint, state summary, admin key authentication guard, WebSocket ping/pong. | **PASS** |

---

## 2. Frontend Verification Matrix (Flutter)

| Test Case | Scope | Status |
|---|---|---|
| Startup & Safety Banner | Terminal boots and displays mandatory `LIVE MARKET DATA — PAPER TRADING ONLY`. | **PASS** |
| Live WebSocket Status | Banner updates to `LIVE WS` with equity summary. | **PASS** |
| Portfolio View Rendering | Virtual equity, cash balance, and metrics render responsively. | **PASS** |
| Flutter Analyze | Static analysis against all Dart lint rules. | **PASS (0 issues)** |
| Flutter Web Build | Production web compilation to `build/web/`. | **PASS** |
