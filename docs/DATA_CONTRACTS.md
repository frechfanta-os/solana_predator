# Data Contracts Specification — SOLANA PREDATOR

All inter-module and API communications conform to strictly validated Pydantic v2 data models.

## 1. Normalized Market Event (`NormalizedMarketEvent`)

```python
class NormalizedMarketEvent(BaseModel):
    source: MarketSource                      # SOLANA_RPC, DEX_SCREENER, REPLAY, SYNTHETIC
    event_id: str                            # Unique event identifier
    token_mint: str                          # Solana base mint public key
    pair_address: Optional[str]              # Liquidity pool address
    slot: Optional[int]                      # Solana ledger slot (if RPC)
    
    # Timestamps
    source_timestamp: Optional[float]        # Provider block/observation epoch (sec)
    local_receive_timestamp: float           # Ingestion arrival epoch (sec)
    processing_timestamp: float              # Normalization completion epoch (sec)
    freshness_seconds: float                 # Latency gap: processing - receive
    
    # Market Metrics (None if unverified, NEVER fabricated)
    price_usd: Optional[float]
    volume_24h_usd: Optional[float]
    liquidity_usd: Optional[float]
    
    # Hashes & Quality
    signature: Optional[str]
    raw_payload_hash: Optional[str]
    quality: EventQuality                    # EXCELLENT, ACCEPTABLE, DEGRADED, STALE, UNVERIFIED
    confidence_score: float                  # Bounded 0.0 - 1.0
    metadata: Dict[str, Any]
```

---

## 2. Token Lifecycle Model (`TokenMetadata`)

```python
class TokenLifecycleState(str, Enum):
    DISCOVERED = "DISCOVERED"
    OBSERVED = "OBSERVED"
    ANALYZED = "ANALYZED"
    REJECTED = "REJECTED"
    PAPER_CANDIDATE = "PAPER_CANDIDATE"

class TokenMetadata(BaseModel):
    mint: str
    name: Optional[str]
    symbol: Optional[str]
    decimals: int = 9
    first_observed_timestamp: float
    pool_created_timestamp: Optional[float]
    pair_address: Optional[str]
    dex_id: Optional[str]
    initial_liquidity_usd: Optional[float]
```

---

## 3. Whale Activity & Convergence (`WhaleActivity`)

```python
class WhaleActivityType(str, Enum):
    SWAP = "SWAP"
    TRANSFER = "TRANSFER"
    DEPOSIT_WITHDRAW = "DEPOSIT_WITHDRAW"
    UNKNOWN_AMBIGUOUS = "UNKNOWN_AMBIGUOUS"

class WhaleActivity(BaseModel):
    activity_id: str
    signature: str
    wallet_address: str
    token_mint: str
    activity_type: WhaleActivityType
    amount_tokens: float
    amount_usd: Optional[float]
    timestamp: float
    slot: Optional[int]
    confidence: float
    evidence_details: Dict[str, Any]

class WhaleConvergenceMetrics(BaseModel):
    token_mint: str
    unique_whales_active: int
    net_flow_usd: float
    buy_volume_usd: float
    sell_volume_usd: float
    convergence_score: float                 # Bounded 0.0 - 1.0
    is_correlated_cluster: bool
    sample_size: int
    calculated_at: float
```

---

## 4. Multi-Agent Result (`AgentResult`)

```python
class AgentDecision(str, Enum):
    BUY_CANDIDATE = "BUY_CANDIDATE"
    PASS = "PASS"
    VETO = "VETO"
    EXIT = "EXIT"
    HOLD = "HOLD"

class AgentResult(BaseModel):
    agent_name: AgentName
    input_event_identifiers: List[str]
    timestamp: float
    decision: AgentDecision
    reason_codes: List[str]
    score: Optional[float]                   # Bounded 0.0 - 1.0
    confidence: float                        # Bounded 0.0 - 1.0
    confidence_interpretation: str
    data_quality: str
    processing_latency_ms: float
    details: Dict[str, Any]
```
