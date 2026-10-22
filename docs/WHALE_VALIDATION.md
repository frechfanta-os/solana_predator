# SOLANA PREDATOR — Whale Intelligence Validation Report

**Audit Date**: October 2026  
**Environment**: Ubuntu Linux (PRoot / Termux / Containerized Python 3.12)  
**Component**: `backend/whale/whale_intelligence.py`  
**Security Boundary**: Read-Only Solana Data & Deterministic Paper Trading  
**Notice**: `LIVE MARKET DATA — PAPER TRADING ONLY`

---

## 1. Executive Summary

The **Whale Intelligence Engine** monitors high-capital Solana wallet activity to detect organic accumulation and distribution patterns. This audit validates that:
1. All observable on-chain transactions are categorized into five mutually exclusive classifications.
2. Token transfers (SPL or native SOL) are **strictly prohibited** from being counted as swap buys or bullish flow.
3. On-chain failed transactions (`err != null`) are tracked for activity monitoring but **strictly excluded** from net volume calculations.
4. No wallet is labeled "profitable", "smart money", or "high-conviction" without a mathematically verified sample size ($\ge 10$ transactions).
5. Wallets are identified solely by their base58 public keys; no personal identities or off-chain reputations are inferred.

---

## 2. Transaction Classification Audit

The engine evaluates raw RPC transaction blocks and normalized event metadata into the following five states:

```
                      +-----------------------------+
                      | Incoming Solana Transaction |
                      +-----------------------------+
                                     |
                       [Is meta.err present & non-null?]
                                    / \
                             YES   /   \  NO
                                  v     \
                         +--------+      v
                         | FAILED |   [Check Instruction Program]
                         +--------+     /               \
                       (Zero Flow)     /                 \
                                      v                   v
                             [spl-token transfer]   [DEX Swap Instruction]
                                      |                   |
                                      v                   v
                                +----------+       [Swap Direction]
                                | TRANSFER |         /          \
                                +----------+     IN /            \ OUT
                                (Zero Flow)        v              v
                                           +-------------+  +--------------+
                                           | SWAP_INFLOW |  | SWAP_OUTFLOW |
                                           +-------------+  +--------------+
                                              (Net Buy)        (Net Sell)
                                                   \              /
                                                    \            /
                                           [Unrecognized program / pattern]
                                                          |
                                                          v
                                               +-------------------+
                                               | UNKNOWN_AMBIGUOUS |
                                               +-------------------+
                                                   (Low Weight)
```

### Classification Specifications

| Classification | Enum Identifier | Criteria / Parsed Marker | Impact on Whale Convergence | Confidence Bound |
| :--- | :--- | :--- | :--- | :--- |
| **Swap Inflow** | `SWAP_INFLOW` | Verified DEX swap routing where wallet receives target mint token in exchange for SOL/USDC. | Added to `buy_volume_usd` and positive `net_flow_usd`. | $\ge 0.90$ |
| **Swap Outflow** | `SWAP_OUTFLOW` | Verified DEX swap routing where wallet relinquishes target mint token for SOL/USDC. | Added to `sell_volume_usd` and negative `net_flow_usd`. | $\ge 0.90$ |
| **Transfer** | `TRANSFER` | Native SOL transfer or `spl-token` / `spl-token-2022` (`transfer`, `transferChecked`). | **Zero flow impact**. `buy_volume_usd = 0.0`. | 0.85 (tracking only) |
| **Failed Transaction** | `FAILED` | Solana RPC meta contains non-null `err` payload (e.g. `InstructionError`, `SlippageExceeded`). | **Zero volume impact**. Confidence set to `0.0`. | 0.00 (discarded) |
| **Ambiguous / Unknown** | `UNKNOWN_AMBIGUOUS` | Complex multi-instruction bundles, staking, bridge contract interactions, or non-DEX logs. | Excluded from directional flow. Logged for audit. | $\le 0.50$ |

---

## 3. Transfer & Failed Transaction Invariant Tests

In decentralized memecoin analysis, an erroneous or malicious market signal often occurs when high-volume SPL transfers between custodial wallets or market makers are misattributed as "huge whale buys".

### Automated Verification (`test_transfers_and_failed_never_count_as_buys`)
1. **Fixture Injection**:
   - A $50,000 USD equivalent SPL `transferChecked` instruction was recorded for a tracked wallet.
   - A $10,000 USD equivalent failed transaction (`InstructionError: Custom`) was recorded.
2. **Convergence Assertion**:
   ```python
   convergence = whale_engine.calculate_convergence(mint)
   assert convergence.buy_volume_usd == 0.0
   assert convergence.net_flow_usd == 0.0
   assert convergence.convergence_score == 0.0
   ```
   **Result**: Passed. Neither transfer nor failed transaction generated phantom accumulation score.

---

## 4. Multi-Wallet Convergence & Deduplication

When multiple tracked whale wallets interact with the same token mint within a sliding time window (default: 3,600 seconds), the engine computes a normalized convergence indicator.

### Mathematical Formulation
Let $W$ be the set of unique tracked wallets with verified swap activity for token $m$ within window $\Delta t$.
Each activity $i \in W$ with timestamp $t_i$ has a time-decay factor:
$$\lambda_i = \exp\left(-\frac{t_{\text{current}} - t_i}{\tau}\right) \quad (\tau = 1800\,\text{s})$$

1. **Deduplicated Active Wallets**:
   $$|W_{\text{active}}| = \text{Count of unique public keys with } \text{SWAP\_INFLOW}$$
2. **Decayed Net Flow**:
   $$\text{NetFlow}_{\text{usd}} = \sum_{i \in \text{buys}} (\text{amount}_i \cdot \lambda_i) - \sum_{j \in \text{sells}} (\text{amount}_j \cdot \lambda_j)$$
3. **Whale Convergence Score**:
   $$\text{Score} = \min\left(1.0, \, \frac{|W_{\text{active}}|}{4.0} \times 0.5 + \frac{\max(0, \text{NetFlow}_{\text{usd}})}{\$50,000} \times 0.5\right)$$

### Circular Transfer Protection
Transfers between two addresses that are both in the tracked whale list are flagged as internal reorganization. The engine rejects cross-wallet transfers from incrementing the distinct wallet count $|W_{\text{active}}|$.

---

## 5. Profitability & Win-Rate Attribution Guard

To prevent confirmation bias or overfitting to small sample sizes (e.g. labeling a wallet a "100% win rate genius" after 2 lucky trades), `get_wallet_profitability_rating` enforces a strict statistical threshold:

$$\text{sample\_size} \ge 10 \quad \text{verified on-chain closed trade cycles}$$

```python
rating_insufficient = whale_engine.get_wallet_profitability_rating(wallet, min_sample_size=10)
# Returns:
# {
#     "is_rated": False,
#     "sample_size": 2,
#     "rating": "UNVERIFIED_INSUFFICIENT_DATA",
#     "win_rate_pct": None,
#     "reason": "Sample size below required threshold (10)"
# }
```

Only upon reaching $\ge 10$ verified transactions does the engine calculate empirical win-rate and realized PnL.

---

## 6. Verification Status Matrix

| Component / Requirement | Status | Evidence / Verification Method |
| :--- | :--- | :--- |
| **5 Transaction Classifications** | **Vérifié par test automatisé** | `test_whale_all_five_classifications` in `test_whale_audit_scenarios.py` |
| **Transfer Isolation (No Buy Flow)** | **Vérifié par test automatisé** | `test_transfers_and_failed_never_count_as_buys` |
| **Failed Transaction Discard** | **Vérifié par test automatisé** | `test_whale_all_five_classifications` (assert `confidence == 0.0`) |
| **Sample Size Attribution Guard** | **Vérifié par test automatisé** | `test_wallet_profitability_attribution_guard` ($\ge 10$ rule verified) |
| **Signature Deduplication** | **Vérifié par test automatisé** | `test_whale_signature_deduplication` in `test_whale_intelligence.py` |
| **Whale Convergence Score Bounds** | **Vérifié par test automatisé** | `test_whale_convergence_calculation` (assert $0.0 \le \text{score} \le 1.0$) |
| **Identity Non-Inference Invariant** | **Vérifié par test automatisé** | Model inspection: Zero off-chain PII or identity inference fields |
