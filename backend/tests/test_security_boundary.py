"""Security boundary tests verifying the absolute absence of transaction signing or broadcast."""

import os
import re
import pytest
from backend.config import settings
from backend.market.solana_rpc import SolanaRpcClient
from backend.paper.broker import PaperBroker


def test_settings_security_invariants():
    """Verify security settings are strictly disabled."""
    assert settings.ALLOW_TRANSACTION_SIGNING is False
    assert settings.ALLOW_TRANSACTION_SUBMISSION is False
    assert settings.ALLOW_REAL_FUNDS is False
    assert "PAPER TRADING ONLY" in settings.SECURITY_NOTICE


def test_rpc_client_has_no_signing_or_broadcast_methods():
    """Verify SolanaRpcClient contains no write/sign methods."""
    rpc = SolanaRpcClient()
    forbidden_methods = [
        "send_transaction",
        "sign_transaction",
        "send_raw_transaction",
        "sign_and_send",
        "broadcast_transaction",
        "create_keypair",
    ]
    for method in forbidden_methods:
        assert not hasattr(rpc, method), f"SolanaRpcClient must not have {method}"


def test_paper_broker_has_no_network_or_key_access():
    """Verify PaperBroker is isolated and has no wallet key fields."""
    forbidden_attrs = ["private_key", "secret_key", "keypair", "mnemonic", "wallet_key"]
    for attr in forbidden_attrs:
        assert not hasattr(PaperBroker, attr), f"PaperBroker must not have {attr}"


def test_source_code_scan_for_forbidden_signing_tokens():
    """Scan all python files in backend/ for forbidden signing routines."""
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    # Prohibited patterns indicating live key management or signing
    forbidden_regexes = [
        r"\.sign_transaction\(",
        r"\.send_raw_transaction\(",
        r"Keypair\.from_secret_key",
        r"Keypair\.generate",
        r"create_account_with_seed",
    ]
    
    for root, _, files in os.walk(backend_dir):
        if "tests" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    for pattern in forbidden_regexes:
                        matches = re.findall(pattern, content)
                        assert not matches, f"Forbidden signing pattern '{pattern}' found in {path}"
