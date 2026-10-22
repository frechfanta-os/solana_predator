"""Data models and contracts for SOLANA PREDATOR Live Trading module."""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class LiveProposalStatus(str, Enum):
    CREATED = "CREATED"
    RISK_PASSED = "RISK_PASSED"
    RISK_REJECTED = "RISK_REJECTED"
    PENDING_USER_SIGNATURE = "PENDING_USER_SIGNATURE"
    SIGNED_BY_USER = "SIGNED_BY_USER"
    BROADCASTING = "BROADCASTING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    REJECTED_BY_USER = "REJECTED_BY_USER"


class LiveTransactionStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    DROPPED = "DROPPED"


class TokenAccountBalance(BaseModel):
    mint: str
    symbol: str = "UNKNOWN"
    balance_tokens: float
    decimals: int = 9
    usd_value: Optional[float] = None


class LiveWalletConnection(BaseModel):
    wallet_address: str
    network: str = "mainnet-beta"
    sol_balance: float = 0.0
    sol_balance_lamports: int = 0
    token_accounts: List[TokenAccountBalance] = Field(default_factory=list)
    connected_at: float
    is_connected: bool = True


class LiveQuote(BaseModel):
    quote_id: str
    token_mint: str
    token_symbol: str
    side: str = "BUY"
    in_amount_sol: float
    in_amount_lamports: int
    expected_output_tokens: float
    min_output_tokens: float
    price_impact_pct: float
    slippage_bps: float
    estimated_network_fee_sol: float = 0.000005
    estimated_priority_fee_sol: float = 0.00001
    route_plan: List[str] = Field(default_factory=lambda: ["Solana Direct AMM"])
    valid_until: float
    pool_liquidity_usd: float = 50000.0


class LiveTradeProposal(BaseModel):
    proposal_id: str
    token_mint: str
    token_symbol: str
    side: str
    wallet_address: str
    input_amount_sol: float
    expected_output_tokens: float
    min_output_tokens: float
    estimated_fee_sol: float
    slippage_bps: float
    quote: LiveQuote
    unsigned_tx_base64: str
    status: LiveProposalStatus = LiveProposalStatus.CREATED
    rejection_reason: Optional[str] = None
    created_at: float
    expires_at: float
    risk_checklist: List[Dict[str, Any]] = Field(default_factory=list)


class LiveTransactionRecord(BaseModel):
    tx_signature: str
    proposal_id: str
    wallet_address: str
    token_mint: str
    side: str
    amount_sol: float
    amount_tokens: float
    slot: Optional[int] = None
    block_time: Optional[float] = None
    status: LiveTransactionStatus = LiveTransactionStatus.PENDING
    confirmation_commitment: str = "confirmed"
    error_message: Optional[str] = None
    fee_paid_sol: Optional[float] = None
    submitted_at: float
    confirmed_at: Optional[float] = None
