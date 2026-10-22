"""Comprehensive whale intelligence validation tests for all transaction types and invariants."""

import pytest
from backend.models import WhaleActivityType
from backend.whale.whale_intelligence import WhaleIntelligenceEngine


@pytest.mark.asyncio
async def test_whale_all_five_classifications(whale_engine):
    mint = "TokenMintWhaleClassifyAudit1111111111111111"
    wallet = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"

    # 1. Swap Inflow (BUY)
    act_inflow = whale_engine.classify_raw_transaction(
        signature="sig_swap_inflow_01",
        wallet_address=wallet,
        token_mint=mint,
        event_metadata={"swap_type": "BUY", "amount_usd": 15000.0, "amount_tokens": 300000.0},
    )
    assert act_inflow.activity_type == WhaleActivityType.SWAP_INFLOW
    assert act_inflow.amount_usd == 15000.0
    assert act_inflow.confidence >= 0.90

    # 2. Swap Outflow (SELL)
    act_outflow = whale_engine.classify_raw_transaction(
        signature="sig_swap_outflow_01",
        wallet_address=wallet,
        token_mint=mint,
        event_metadata={"swap_type": "SELL", "amount_usd": 8000.0, "amount_tokens": 160000.0},
    )
    assert act_outflow.activity_type == WhaleActivityType.SWAP_OUTFLOW
    assert act_outflow.amount_usd == 8000.0

    # 3. Transfer
    parsed_transfer_tx = {
        "slot": 320000010,
        "transaction": {
            "message": {
                "instructions": [
                    {
                        "program": "spl-token",
                        "parsed": {
                            "type": "transferChecked",
                            "info": {
                                "source": "WalletSource",
                                "destination": "WalletDest",
                                "tokenAmount": {"uiAmount": 50000.0},
                            },
                        },
                    }
                ]
            }
        },
    }
    act_transfer = whale_engine.classify_raw_transaction(
        signature="sig_transfer_01",
        wallet_address=wallet,
        token_mint=mint,
        parsed_tx=parsed_transfer_tx,
    )
    assert act_transfer.activity_type == WhaleActivityType.TRANSFER
    assert act_transfer.amount_tokens == 50000.0

    # 4. Failed Transaction (has error code)
    parsed_failed_tx = {
        "slot": 320000015,
        "meta": {"err": {"InstructionError": [0, "Custom"]}},
        "transaction": {"message": {"instructions": []}},
    }
    act_failed = whale_engine.classify_raw_transaction(
        signature="sig_failed_01",
        wallet_address=wallet,
        token_mint=mint,
        parsed_tx=parsed_failed_tx,
    )
    assert act_failed.activity_type == WhaleActivityType.FAILED
    assert act_failed.confidence == 0.0

    # 5. Ambiguous / Unknown Transaction
    parsed_unknown_tx = {
        "slot": 320000020,
        "meta": {"err": None},
        "transaction": {"message": {"instructions": [{"program": "custom-unknown-program"}]}},
    }
    act_ambiguous = whale_engine.classify_raw_transaction(
        signature="sig_ambiguous_01",
        wallet_address=wallet,
        token_mint=mint,
        parsed_tx=parsed_unknown_tx,
    )
    assert act_ambiguous.activity_type == WhaleActivityType.UNKNOWN_AMBIGUOUS
    assert act_ambiguous.confidence <= 0.50


@pytest.mark.asyncio
async def test_transfers_and_failed_never_count_as_buys(whale_engine):
    """Verify that transfers and failed transactions NEVER generate buy flow in convergence."""
    mint = "TokenMintTransferNotBuy11111111111111111"
    wallet = "wha1e8sF3G5wK8eA9Z8oA2V4dE6mB1nC7xY9uL0kP3r"

    # Record 1 Transfer of $50,000 USD
    act_transfer = whale_engine.classify_raw_transaction(
        signature="sig_trans_large",
        wallet_address=wallet,
        token_mint=mint,
        event_metadata={"amount_usd": 50000.0},
        parsed_tx={
            "transaction": {
                "message": {
                    "instructions": [
                        {
                            "program": "spl-token",
                            "parsed": {"type": "transfer", "info": {"amount": 50000000000}},
                        }
                    ]
                }
            }
        },
    )
    await whale_engine.record_activity(act_transfer)

    # Record 1 Failed Transaction of $10,000 USD
    act_failed = whale_engine.classify_raw_transaction(
        signature="sig_fail_large",
        wallet_address=wallet,
        token_mint=mint,
        event_metadata={"err": "TransactionSimulationFailed", "amount_usd": 10000.0},
    )
    await whale_engine.record_activity(act_failed)

    convergence = whale_engine.calculate_convergence(mint)
    # INVARIANT: Buy volume MUST be 0.0! Neither transfer nor failed tx is buy flow!
    assert convergence.buy_volume_usd == 0.0
    assert convergence.net_flow_usd == 0.0
    assert convergence.convergence_score == 0.0


@pytest.mark.asyncio
async def test_wallet_profitability_attribution_guard(whale_engine):
    """Verify that no wallet is rated profitable without sufficient verified sample size."""
    wallet = "wha_unrated_wallet_test_11111111111111"

    # Only 2 transactions observed
    for i in range(2):
        whale_engine.classify_raw_transaction(
            signature=f"sig_sample_{i}",
            wallet_address=wallet,
            token_mint="MintX",
            event_metadata={"swap_type": "BUY"},
        )

    rating_insufficient = whale_engine.get_wallet_profitability_rating(wallet, min_sample_size=10)
    assert rating_insufficient["is_rated"] is False
    assert rating_insufficient["rating"] == "UNVERIFIED_INSUFFICIENT_DATA"

    # Add remaining to reach sample size >= 10
    for i in range(2, 10):
        whale_engine.classify_raw_transaction(
            signature=f"sig_sample_{i}",
            wallet_address=wallet,
            token_mint="MintX",
            event_metadata={"swap_type": "BUY"},
        )

    rating_valid = whale_engine.get_wallet_profitability_rating(wallet, min_sample_size=10)
    assert rating_valid["is_rated"] is True
    assert rating_valid["sample_size"] == 10
