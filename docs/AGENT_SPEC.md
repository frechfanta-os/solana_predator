# Multi-Agent Specification — SOLANA PREDATOR

SOLANA PREDATOR employs a coordinated 9-agent consensus architecture to evaluate incoming market telemetry with microsecond latency.

## Agent Directory & Responsibilities

| Agent Name | Primary Responsibility | Input Context | Decision Capability |
|---|---|---|---|
| **SCAN** | Discovery validation, minimum liquidity filters, volume presence. | Pair data, liquidity, 24h volume. | `BUY_CANDIDATE`, `PASS` |
| **WHALE** | Wallet accumulation, convergence score, outflow triggers. | Deduplicated transactions, net flow. | `BUY_CANDIDATE`, `PASS`, `EXIT` |
| **VET** | Token risk screening, mint authority, freeze authority checks. | Token metadata, program logs. | `PASS`, `VETO` |
| **QUANT** | Statistical metrics, volume/liquidity ratio, uncertainty bands. | Price momentum, pool depth. | `BUY_CANDIDATE`, `PASS` |
| **SKEPTIC** | Contrarian flags, wash trading detection, single-wallet dominance. | 5m buy/sell ratios, volume anomalies. | `BUY_CANDIDATE`, `PASS`, `VETO` |
| **SIZE** | Theoretical simulated sizing based on equity & pool depth limits. | Virtual portfolio cash, pool depth. | `BUY_CANDIDATE`, `PASS` |
| **RISK** | Hard deterministic invariants, drawdown circuit breaker. | Portfolio drawdown, open positions. | `PASS`, `VETO` (Unconditional) |
| **CHIEF** | Consensus synthesizer and final binding decision record. | Outputs from all prior agents. | Final Binding Decision |
| **AUDIT** | Post-decision calibration, processing time SLA compliance. | Monitored latencies, consensus record. | Audit Metric Record |

---

## Decision Synthesis Hierarchy

1. **RISK Check**: If `RISK` emits `VETO` (e.g., drawdown > 15%, max 5 positions full, duplicate token held), `CHIEF` **MUST** record `VETO`. No agent can override `RISK`.
2. **VET Check**: If `VET` emits `VETO` (e.g. freeze authority present or invalid mint), `CHIEF` emits `VETO`.
3. **SKEPTIC Check**: If `SKEPTIC` detects honeypot behavior (zero sells despite active buys), `CHIEF` emits `VETO`.
4. **Whale Exit**: If `WHALE` emits `EXIT`, `CHIEF` emits `EXIT` to trigger position liquidation.
5. **Buy Approval**: Requires `RISK = PASS`, `VET = PASS`, `SKEPTIC != VETO`, at least two affirmative signals (`SCAN`, `WHALE`, or `QUANT`), and `SIZE > $25.00`.

---

## LLM Integration Rules
- Optional and strictly isolated from the critical latency path.
- Enforced timeout: maximum 3.0 seconds.
- **Fail-Safe Invariant**: An LLM timeout NEVER converts an incomplete analysis into an approved trade. Upon timeout, rule-based consensus executes immediately without delay.
