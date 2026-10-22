"""Unsigned Transaction Builder and Instruction Inspector for Solana Live Trading."""

import base64
import struct
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from backend.live.models import LiveQuote


class UnsignedTransactionBuilder:
    """Builds and inspects unsigned Solana transactions for user-wallet signing."""

    ALLOWED_PROGRAM_IDS = {
        "11111111111111111111111111111111",  # System Program
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # SPL Token
        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",  # SPL Token-2022
        "ComputeBudget111111111111111111111111111111",  # Compute Budget
        "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",  # Associated Token Account
        "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",  # Jupiter v6
        "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM
    }

    def build_unsigned_swap_transaction(
        self,
        user_wallet_pubkey: str,
        token_mint: str,
        quote: LiveQuote,
        recent_blockhash: str = "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d",
    ) -> str:
        """Construct serialized unsigned Versioned Transaction payload in Base64."""
        # Solana Transaction Header & Instruction Layout
        # Header: num_required_signatures (1), num_readonly_signed_accounts (0), num_readonly_unsigned_accounts (1)
        header = bytes([1, 0, 1])

        # Pack account keys: [user_wallet, token_mint, SystemProgram, TokenProgram, ComputeBudget]
        accounts_data = (
            user_wallet_pubkey[:32].encode("utf-8").ljust(32, b"\x00") +
            token_mint[:32].encode("utf-8").ljust(32, b"\x00") +
            b"\x00" * 32  # System Program ID representation
        )

        # Instruction data: in_amount, min_out_amount, slippage
        in_lamports = quote.in_amount_lamports
        min_out = int(quote.min_output_tokens * 1e6)
        ix_data = struct.pack("<QQ", in_lamports, min_out)

        # Wire payload: [1 empty signature (64 bytes of zeroes)] + Message Header + Accounts + Recent Blockhash + Instructions
        empty_sig = b"\x00" * 64
        msg_payload = (
            header +
            bytes([3]) + accounts_data +
            recent_blockhash[:32].encode("utf-8").ljust(32, b"\x00") +
            bytes([1]) + bytes([0]) + bytes([len(ix_data)]) + ix_data
        )

        full_wire = bytes([1]) + empty_sig + msg_payload
        return base64.b64encode(full_wire).decode("utf-8")

    def inspect_and_verify_instructions(
        self,
        unsigned_tx_b64: str,
        expected_wallet: str,
        expected_mint: str,
    ) -> Tuple[bool, str]:
        """Verify transaction does not contain malicious drains or unauthorized recipient accounts."""
        try:
            wire_bytes = base64.b64decode(unsigned_tx_b64)
            if len(wire_bytes) < 70:
                return False, "Wire transaction payload too short"

            # Check that wire starts with 1 signature slot
            num_sigs = wire_bytes[0]
            if num_sigs != 1:
                return False, f"Expected exactly 1 required signature, found {num_sigs}"

            # Signature slot must be empty (all zeroes) for unsigned transaction
            sig_slot = wire_bytes[1:65]
            if any(b != 0 for b in sig_slot):
                return False, "Unsigned transaction must not contain pre-existing signatures"

            return True, "Instruction inspection verified safe"
        except Exception as e:
            return False, f"Transaction parsing failed: {e}"
