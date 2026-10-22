"""
Technical validation tests for Live Trading and Independent Risk Guard (Steps 4, 5, 7.3).
Tests read-only wallet connection, unsigned transaction building, 13 risk checks,
kill switch, strict refusal of backend signing, and risk audit logging.
"""
import pytest
import time
import base64
from backend.live.models import (
    LiveWalletConnection,
    LiveQuote,
    LiveTradeProposal,
    LiveTransactionRecord,
    LiveProposalStatus,
    LiveTransactionStatus,
)
from backend.live.wallet import WalletService
from backend.live.tx_builder import UnsignedTransactionBuilder
from backend.live.independent_risk import IndependentRiskGuard
from backend.live.quote_service import LiveQuoteService
from backend.live.broadcast_service import LiveBroadcastService
from backend.live.order_manager import LiveOrderManager
from backend.market.solana_rpc import SolanaRpcClient


@pytest.fixture
def mock_rpc():
    return SolanaRpcClient()


@pytest.fixture
def risk_guard():
    return IndependentRiskGuard(
        max_trade_amount_sol=1.5,
        max_slippage_bps=250.0,
        min_pool_liquidity_usd=5000.0,
        quote_expiry_seconds=15.0,
        data_freshness_seconds=30.0,
    )


@pytest.fixture
def valid_wallet():
    return LiveWalletConnection(
        wallet_address="5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
        network="mainnet-beta",
        sol_balance=5.0,
        sol_balance_lamports=5000000000,
        token_accounts=[],
        connected_at=time.time(),
        is_connected=True,
    )


@pytest.fixture
def valid_quote():
    now = time.time()
    return LiveQuote(
        quote_id="quote_test_01",
        token_mint="4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
        token_symbol="RAY",
        side="BUY",
        in_amount_sol=0.5,
        in_amount_lamports=500000000,
        expected_output_tokens=100.0,
        min_output_tokens=99.0,
        price_impact_pct=0.25,
        slippage_bps=100.0,
        estimated_network_fee_sol=0.000005,
        estimated_priority_fee_sol=0.00001,
        route_plan=["Raydium AMM"],
        valid_until=now + 15.0,
        pool_liquidity_usd=50000.0,
    )


@pytest.mark.asyncio
async def test_wallet_connection_read_only_public_key(mock_rpc):
    svc = WalletService(rpc_client=mock_rpc)
    
    # Valid base58 Solana public key
    conn = await svc.connect_wallet("5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1")
    assert conn.is_connected
    assert conn.wallet_address == "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
    assert conn.sol_balance >= 0.0

    # Ensure backend stores NO private key or seed phrase
    assert not hasattr(conn, "private_key")
    assert not hasattr(conn, "seed_phrase")
    assert not hasattr(svc, "private_key")

    # Invalid public key rejection
    with pytest.raises(ValueError):
        await svc.connect_wallet("InvalidKeyWithBadChars00000!!!")


def test_unsigned_transaction_building_and_inspection(valid_wallet, valid_quote):
    builder = UnsignedTransactionBuilder()
    unsigned_b64 = builder.build_unsigned_swap_transaction(
        user_wallet_pubkey=valid_wallet.wallet_address,
        token_mint=valid_quote.token_mint,
        quote=valid_quote,
    )

    assert isinstance(unsigned_b64, str)
    assert len(unsigned_b64) > 50

    # Inspect transaction: must have empty signature slot and safe instructions
    is_safe, msg = builder.inspect_and_verify_instructions(
        unsigned_tx_b64=unsigned_b64,
        expected_wallet=valid_wallet.wallet_address,
        expected_mint=valid_quote.token_mint,
    )
    assert is_safe is True
    assert "verified safe" in msg.lower()


def test_independent_risk_guard_accepts_compliant_proposal(risk_guard, valid_wallet, valid_quote):
    proposal = LiveTradeProposal(
        proposal_id="prop_ok_01",
        token_mint=valid_quote.token_mint,
        token_symbol="RAY",
        side="BUY",
        wallet_address=valid_wallet.wallet_address,
        input_amount_sol=0.5,
        expected_output_tokens=valid_quote.expected_output_tokens,
        min_output_tokens=valid_quote.min_output_tokens,
        estimated_fee_sol=0.000015,
        slippage_bps=100.0,
        quote=valid_quote,
        unsigned_tx_base64="AQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAEDB55n",
        created_at=time.time(),
        expires_at=valid_quote.valid_until,
    )

    passed, reason, checklist = risk_guard.audit_trade_proposal(
        proposal=proposal,
        wallet_sol_balance=valid_wallet.sol_balance,
        network=valid_wallet.network,
        data_freshness_sec=1.0,
    )
    assert passed is True
    assert len(checklist) == 13
    assert all(item["passed"] for item in checklist)


def test_independent_risk_guard_blocks_excessive_size(risk_guard, valid_wallet, valid_quote):
    proposal = LiveTradeProposal(
        proposal_id="prop_fail_size",
        token_mint=valid_quote.token_mint,
        token_symbol="RAY",
        side="BUY",
        wallet_address=valid_wallet.wallet_address,
        input_amount_sol=2.5,  # Exceeds max 1.5 SOL
        expected_output_tokens=valid_quote.expected_output_tokens,
        min_output_tokens=valid_quote.min_output_tokens,
        estimated_fee_sol=0.000015,
        slippage_bps=100.0,
        quote=valid_quote,
        unsigned_tx_base64="AQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAEDB55n",
        created_at=time.time(),
        expires_at=valid_quote.valid_until,
    )

    passed, reason, checklist = risk_guard.audit_trade_proposal(
        proposal=proposal,
        wallet_sol_balance=valid_wallet.sol_balance,
        network=valid_wallet.network,
        data_freshness_sec=1.0,
    )
    assert passed is False
    assert "exceeds limit" in reason.lower()
    size_check = next(c for c in checklist if c["check"] == "MAX_TRADE_AMOUNT")
    assert size_check["passed"] is False


def test_independent_risk_guard_blocks_insufficient_sol_balance(risk_guard, valid_wallet, valid_quote):
    proposal = LiveTradeProposal(
        proposal_id="prop_fail_bal",
        token_mint=valid_quote.token_mint,
        token_symbol="RAY",
        side="BUY",
        wallet_address=valid_wallet.wallet_address,
        input_amount_sol=0.5,
        expected_output_tokens=valid_quote.expected_output_tokens,
        min_output_tokens=valid_quote.min_output_tokens,
        estimated_fee_sol=0.000015,
        slippage_bps=100.0,
        quote=valid_quote,
        unsigned_tx_base64="AQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAEDB55n",
        created_at=time.time(),
        expires_at=valid_quote.valid_until,
    )

    # Wallet has only 0.1 SOL, cannot cover 0.5 + 0.05 rent reserve
    passed, reason, checklist = risk_guard.audit_trade_proposal(
        proposal=proposal,
        wallet_sol_balance=0.1,
        network=valid_wallet.network,
        data_freshness_sec=1.0,
    )
    assert passed is False
    bal_check = next(c for c in checklist if c["check"] == "SOL_BALANCE_AND_RENT_RESERVE")
    assert bal_check["passed"] is False


def test_emergency_kill_switch_blocks_all_proposals(risk_guard, valid_wallet, valid_quote):
    proposal = LiveTradeProposal(
        proposal_id="prop_fail_kill",
        token_mint=valid_quote.token_mint,
        token_symbol="RAY",
        side="BUY",
        wallet_address=valid_wallet.wallet_address,
        input_amount_sol=0.5,
        expected_output_tokens=valid_quote.expected_output_tokens,
        min_output_tokens=valid_quote.min_output_tokens,
        estimated_fee_sol=0.000015,
        slippage_bps=100.0,
        quote=valid_quote,
        unsigned_tx_base64="AQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAEDB55n",
        created_at=time.time(),
        expires_at=valid_quote.valid_until,
    )

    risk_guard.set_emergency_kill_switch(True)
    passed, reason, checklist = risk_guard.audit_trade_proposal(
        proposal=proposal,
        wallet_sol_balance=valid_wallet.sol_balance,
        network=valid_wallet.network,
        data_freshness_sec=1.0,
    )
    assert passed is False
    assert "kill-switch" in reason.lower()

    # Reset kill-switch
    risk_guard.set_emergency_kill_switch(False)
    passed2, _, _ = risk_guard.audit_trade_proposal(
        proposal=proposal,
        wallet_sol_balance=valid_wallet.sol_balance,
        network=valid_wallet.network,
        data_freshness_sec=1.0,
    )
    assert passed2 is True


@pytest.mark.asyncio
async def test_strict_refusal_to_execute_unsigned_transaction(mock_rpc, repo):
    broadcast_svc = LiveBroadcastService(rpc_client=mock_rpc, repository=repo)

    # 1. Wire payload with empty signature slot (all zeroes) -> Must be rejected!
    unsigned_wire = bytes([1]) + (b"\x00" * 64) + (b"\x01" * 30)
    unsigned_b64 = base64.b64encode(unsigned_wire).decode("utf-8")

    with pytest.raises(ValueError, match="not been signed"):
        await broadcast_svc.broadcast_signed_transaction(
            proposal_id="prop_unsigned",
            signed_tx_base64=unsigned_b64,
            wallet_address="5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
            token_mint="4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
            side="BUY",
            amount_sol=0.5,
            amount_tokens=100.0,
        )

    # 2. Wire payload with genuine signature bytes from wallet -> Processed
    signed_wire = bytes([1]) + (b"\xaa" * 64) + (b"\x01" * 30)
    signed_b64 = base64.b64encode(signed_wire).decode("utf-8")

    record = await broadcast_svc.broadcast_signed_transaction(
        proposal_id="prop_signed",
        signed_tx_base64=signed_b64,
        wallet_address="5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
        token_mint="4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
        side="BUY",
        amount_sol=0.5,
        amount_tokens=100.0,
    )
    assert record.status == LiveTransactionStatus.CONFIRMED
    assert record.tx_signature.startswith("sig_")


@pytest.mark.asyncio
async def test_risk_audit_logging_in_repository(repo):
    await repo.log_risk_audit(
        proposal_id="prop_audit_test",
        check_name="MAX_TRADE_AMOUNT",
        passed=True,
        threshold_val="<= 1.5 SOL",
        observed_val="0.5 SOL",
        details={"reason": "Well within bounds"},
    )

    logs = await repo.get_risk_audit_logs(proposal_id="prop_audit_test")
    assert len(logs) == 1
    assert logs[0]["proposal_id"] == "prop_audit_test"
    assert logs[0]["check_name"] == "MAX_TRADE_AMOUNT"
    assert logs[0]["passed"] == 1
