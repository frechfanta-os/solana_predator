"""Live Order Manager orchestrating trade proposals, independent risk audits, and user approvals."""

import time
import uuid
from typing import Dict, Any, List, Optional
from backend.live.models import (
    LiveTradeProposal,
    LiveProposalStatus,
    LiveQuote,
    LiveTransactionRecord,
)
from backend.live.independent_risk import IndependentRiskGuard
from backend.live.quote_service import LiveQuoteService
from backend.live.tx_builder import UnsignedTransactionBuilder
from backend.live.broadcast_service import LiveBroadcastService
from backend.live.wallet import WalletService
from backend.database.repository import Repository


class LiveOrderManager:
    """Orchestrates live trade proposals ensuring explicit user consent and independent risk gating."""

    def __init__(
        self,
        repository: Repository,
        risk_guard: IndependentRiskGuard,
        quote_service: LiveQuoteService,
        tx_builder: UnsignedTransactionBuilder,
        broadcast_service: LiveBroadcastService,
        wallet_service: WalletService,
    ):
        self.repository = repository
        self.risk_guard = risk_guard
        self.quote_service = quote_service
        self.tx_builder = tx_builder
        self.broadcast_service = broadcast_service
        self.wallet_service = wallet_service

    async def create_trade_proposal(
        self,
        token_mint: str,
        token_symbol: str,
        amount_sol: float,
        slippage_bps: float = 100.0,
        current_token_price_usd: Optional[float] = None,
        data_freshness_sec: float = 1.0,
    ) -> LiveTradeProposal:
        """Construct, risk-audit, and prepare an unsigned trade proposal for user approval."""
        wallet = self.wallet_service.get_status()
        if not wallet or not wallet.is_connected:
            raise ValueError("No active Solana wallet connected. Cannot propose live trade.")

        # 1. Fetch swap quote
        quote = await self.quote_service.get_swap_quote(
            token_mint=token_mint,
            token_symbol=token_symbol,
            amount_sol=amount_sol,
            slippage_bps=slippage_bps,
            current_token_price_usd=current_token_price_usd,
        )

        # 2. Build unsigned transaction
        unsigned_tx_b64 = self.tx_builder.build_unsigned_swap_transaction(
            user_wallet_pubkey=wallet.wallet_address,
            token_mint=token_mint,
            quote=quote,
        )

        now = time.time()
        proposal_id = f"prop_{uuid.uuid4().hex[:12]}"

        proposal = LiveTradeProposal(
            proposal_id=proposal_id,
            token_mint=token_mint,
            token_symbol=token_symbol,
            side="BUY",
            wallet_address=wallet.wallet_address,
            input_amount_sol=amount_sol,
            expected_output_tokens=quote.expected_output_tokens,
            min_output_tokens=quote.min_output_tokens,
            estimated_fee_sol=quote.estimated_network_fee_sol + quote.estimated_priority_fee_sol,
            slippage_bps=slippage_bps,
            quote=quote,
            unsigned_tx_base64=unsigned_tx_b64,
            status=LiveProposalStatus.CREATED,
            created_at=now,
            expires_at=quote.valid_until,
        )

        # 3. Independent Risk Audit
        passed, reason, checklist = self.risk_guard.audit_trade_proposal(
            proposal=proposal,
            wallet_sol_balance=wallet.sol_balance,
            network=wallet.network,
            data_freshness_sec=data_freshness_sec,
        )
        proposal.risk_checklist = checklist

        for item in checklist:
            await self.repository.log_risk_audit(
                proposal_id=proposal_id,
                check_name=item["check"],
                passed=item["passed"],
                threshold_val=str(item["threshold"]),
                observed_val=str(item["observed"]),
                details={"reason": item["reason"]},
            )

        if not passed:
            proposal.status = LiveProposalStatus.RISK_REJECTED
            proposal.rejection_reason = reason
        else:
            proposal.status = LiveProposalStatus.PENDING_USER_SIGNATURE

        # 4. Persist proposal
        await self.repository.save_live_proposal(proposal.model_dump())
        return proposal

    async def submit_user_signature(
        self,
        proposal_id: str,
        signed_tx_base64: str,
    ) -> LiveTransactionRecord:
        """Receive explicitly signed transaction from user wallet and broadcast to Solana network."""
        proposals = await self.repository.get_live_proposals(limit=10, status=LiveProposalStatus.PENDING_USER_SIGNATURE.value)
        target = next((p for p in proposals if p["proposal_id"] == proposal_id), None)
        if not target:
            raise ValueError(f"Proposal {proposal_id} not found or not awaiting signature")

        # Check expiration
        if time.time() > target["expires_at"]:
            await self.repository.update_live_proposal_status(proposal_id, LiveProposalStatus.EXPIRED.value, "Quote expired before signing")
            raise ValueError("Proposal expired before user signature was submitted")

        # Broadcast via broadcast service
        tx_record = await self.broadcast_service.broadcast_signed_transaction(
            proposal_id=proposal_id,
            signed_tx_base64=signed_tx_base64,
            wallet_address=target["wallet_address"],
            token_mint=target["token_mint"],
            side=target["side"],
            amount_sol=target["input_amount_sol"],
            amount_tokens=target["expected_output_tokens"],
        )
        return tx_record

    async def reject_proposal_by_user(self, proposal_id: str, reason: str = "Rejected by user") -> None:
        """Mark proposal as explicitly rejected by user."""
        await self.repository.update_live_proposal_status(
            proposal_id,
            LiveProposalStatus.REJECTED_BY_USER.value,
            reason,
        )
