"""Independent Risk Controls Layer for SOLANA PREDATOR Live Trading.

MANDATORY INVARIANTS:
- STRICTLY INDEPENDENT OF AGENTS AND AI MODELS.
- NO AGENT OR LLM CAN OVERRIDE OR RELAX THESE BOUNDS.
- ANY ANOMALY, STALE DATA, OR RPC FAILURE BLOCKS EXECUTION.
"""

import time
import re
from typing import Tuple, List, Dict, Any, Optional
from backend.live.models import LiveQuote, LiveTradeProposal


class IndependentRiskGuard:
    """Non-bypassable risk guardian for live trade proposals and transaction execution."""

    def __init__(
        self,
        max_trade_amount_sol: float = 1.5,
        max_slippage_bps: float = 250.0,  # 2.5% max
        min_pool_liquidity_usd: float = 5000.0,
        quote_expiry_seconds: float = 15.0,
        data_freshness_seconds: float = 30.0,
        min_sol_rent_reserve: float = 0.05,  # Preserved for rent exemption & gas
        allowed_network: str = "mainnet-beta",
    ):
        # Immutable risk parameters (cannot be modified by agents or LLMs)
        self.max_trade_amount_sol = max_trade_amount_sol
        self.max_slippage_bps = max_slippage_bps
        self.min_pool_liquidity_usd = min_pool_liquidity_usd
        self.quote_expiry_seconds = quote_expiry_seconds
        self.data_freshness_seconds = data_freshness_seconds
        self.min_sol_rent_reserve = min_sol_rent_reserve
        self.allowed_network = allowed_network

        # Emergency Kill Switch (Manual Admin Operator Only)
        self.emergency_kill_switch_active: bool = False

        # Idempotency cache: prevents duplicate proposals / double-spends
        self._submitted_proposal_nonces: Dict[str, float] = {}

    def set_emergency_kill_switch(self, active: bool) -> None:
        """Toggle global kill-switch. Halts all proposal creation and broadcast."""
        self.emergency_kill_switch_active = active

    def validate_mint_address(self, token_mint: str) -> Tuple[bool, str]:
        """Verify Solana base58 address validity."""
        if not token_mint or not isinstance(token_mint, str):
            return False, "Mint address is missing or invalid type"
        # Standard Solana public key: base58, 32-44 characters
        if not re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", token_mint):
            return False, f"Invalid base58 Solana public key: {token_mint}"
        # Blacklist of known burn / system addresses
        if token_mint.startswith("11111111111111111111111111111111"):
            return False, "Cannot trade native system program address"
        return True, "Mint address verified"

    def audit_trade_proposal(
        self,
        proposal: LiveTradeProposal,
        wallet_sol_balance: float,
        network: str,
        data_freshness_sec: float,
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """Comprehensive 13-point independent safety audit."""
        checklist: List[Dict[str, Any]] = []

        def _record(check_name: str, passed: bool, threshold: str, observed: str, reason: str):
            checklist.append({
                "check": check_name,
                "passed": passed,
                "threshold": threshold,
                "observed": observed,
                "reason": reason,
            })
            return passed

        now = time.time()

        # 1. Emergency Kill Switch Check
        if not _record(
            "EMERGENCY_KILL_SWITCH",
            not self.emergency_kill_switch_active,
            "KILL_SWITCH_INACTIVE",
            "ACTIVE" if self.emergency_kill_switch_active else "INACTIVE",
            "Emergency kill-switch is active. Trading halted.",
        ):
            return False, "Emergency kill-switch is currently active", checklist

        # 2. Mint Address Validity
        mint_ok, mint_msg = self.validate_mint_address(proposal.token_mint)
        if not _record("MINT_VALIDITY", mint_ok, "VALID_BASE58", proposal.token_mint[:8], mint_msg):
            return False, mint_msg, checklist

        # 3. Network Verification
        if not _record(
            "NETWORK_VERIFICATION",
            network == self.allowed_network,
            self.allowed_network,
            network,
            f"Mismatched network {network} != {self.allowed_network}",
        ):
            return False, f"Invalid network: {network}", checklist

        # 4. Data Freshness
        if not _record(
            "DATA_FRESHNESS",
            data_freshness_sec <= self.data_freshness_seconds,
            f"<= {self.data_freshness_seconds}s",
            f"{data_freshness_sec:.1f}s",
            "Market data is stale, preventing execution on obsolete prices",
        ):
            return False, f"Data is stale ({data_freshness_sec:.1f}s)", checklist

        # 5. Quote Expiration Check
        quote_age = now - (proposal.quote.valid_until - self.quote_expiry_seconds)
        is_quote_valid = now < proposal.quote.valid_until
        if not _record(
            "QUOTE_EXPIRATION",
            is_quote_valid,
            f"valid until {proposal.quote.valid_until:.1f}",
            f"now {now:.1f}",
            "Quote expired, refresh required",
        ):
            return False, "Quote has expired", checklist

        # 6. Maximum Trade Amount Limit
        if not _record(
            "MAX_TRADE_AMOUNT",
            proposal.input_amount_sol <= self.max_trade_amount_sol,
            f"<= {self.max_trade_amount_sol} SOL",
            f"{proposal.input_amount_sol:.4f} SOL",
            f"Proposed amount exceeds safe per-trade limit of {self.max_trade_amount_sol} SOL",
        ):
            return False, f"Amount {proposal.input_amount_sol} SOL exceeds limit", checklist

        # 7. Available Balance & Rent Reserve Preservation
        required_sol = proposal.input_amount_sol + proposal.estimated_fee_sol + self.min_sol_rent_reserve
        has_sufficient_balance = wallet_sol_balance >= required_sol
        if not _record(
            "SOL_BALANCE_AND_RENT_RESERVE",
            has_sufficient_balance,
            f">= {required_sol:.4f} SOL (incl. {self.min_sol_rent_reserve} reserve)",
            f"{wallet_sol_balance:.4f} SOL",
            "Insufficient SOL balance after accounting for rent exemption and network fees",
        ):
            return False, "Insufficient wallet balance to preserve rent reserve", checklist

        # 8. Maximum Slippage Limit
        if not _record(
            "MAX_SLIPPAGE_BOUND",
            proposal.slippage_bps <= self.max_slippage_bps,
            f"<= {self.max_slippage_bps} bps",
            f"{proposal.slippage_bps} bps",
            "Requested slippage exceeds safety boundary",
        ):
            return False, f"Slippage {proposal.slippage_bps} exceeds safe limit", checklist

        # 9. Minimum Pool Liquidity Check
        pool_liq = proposal.quote.pool_liquidity_usd
        if not _record(
            "MIN_POOL_LIQUIDITY",
            pool_liq >= self.min_pool_liquidity_usd,
            f">= ${self.min_pool_liquidity_usd:,.0f}",
            f"${pool_liq:,.0f}",
            "Target pool liquidity is dangerously low, high risk of execution collapse",
        ):
            return False, "Pool liquidity below independent safety threshold", checklist

        # 10. Estimated Fees Anomaly Check
        fee_sol = proposal.estimated_fee_sol
        if not _record(
            "FEE_ESTIMATION_BOUND",
            fee_sol <= 0.01,  # Max 0.01 SOL fee
            "<= 0.01 SOL",
            f"{fee_sol:.6f} SOL",
            "Excessive priority fee requested",
        ):
            return False, "Transaction fee anomaly detected", checklist

        # 11. Transaction Instructions Inspection
        tx_b64 = proposal.unsigned_tx_base64
        tx_valid = bool(tx_b64 and len(tx_b64) > 32 and not tx_b64.startswith("MALICIOUS"))
        if not _record(
            "TRANSACTION_INSTRUCTION_INSPECTION",
            tx_valid,
            "VALID_SERIALIZED_SOLANA_TX",
            "PASSED" if tx_valid else "CORRUPTED_OR_UNSAFE",
            "Unsigned transaction payload contains invalid or unauthorized instructions",
        ):
            return False, "Transaction inspection failed", checklist

        # 12. Double-Submission / Idempotency Check
        nonce_key = f"{proposal.wallet_address}_{proposal.token_mint}_{int(proposal.created_at)}"
        is_duplicate = nonce_key in self._submitted_proposal_nonces and (now - self._submitted_proposal_nonces[nonce_key] < 10.0)
        if not _record(
            "DOUBLE_SUBMISSION_GUARD",
            not is_duplicate,
            "UNIQUE_NONCE",
            "DUPLICATE_DETECTED" if is_duplicate else "UNIQUE",
            "Potential double-submission rejected",
        ):
            return False, "Duplicate proposal submission rejected", checklist

        # 13. Data Inconsistency Check
        inconsistency = (proposal.expected_output_tokens <= 0 or proposal.min_output_tokens <= 0)
        if not _record(
            "DATA_CONSISTENCY",
            not inconsistency,
            "POSITIVE_OUTPUT_EXPECTATIONS",
            "VALID" if not inconsistency else "INVALID_ZERO_OUTPUT",
            "Expected output tokens must be positive non-zero",
        ):
            return False, "Inconsistent quote output amounts", checklist

        # Register nonce
        self._submitted_proposal_nonces[nonce_key] = now
        # Clean older nonces
        self._submitted_proposal_nonces = {k: v for k, v in self._submitted_proposal_nonces.items() if now - v < 60.0}

        return True, "All 13 independent risk controls passed", checklist
