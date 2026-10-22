"""Database schema definitions and SQL scripts for SOLANA PREDATOR."""

SCHEMA_V1 = """
-- Schema migration tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at REAL NOT NULL
);

-- Market events normalized store
CREATE TABLE IF NOT EXISTS market_events (
    event_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    token_mint TEXT NOT NULL,
    pair_address TEXT,
    slot INTEGER,
    source_timestamp REAL,
    local_receive_timestamp REAL NOT NULL,
    processing_timestamp REAL NOT NULL,
    freshness_seconds REAL NOT NULL,
    price_usd REAL,
    volume_24h_usd REAL,
    liquidity_usd REAL,
    signature TEXT,
    raw_payload_hash TEXT,
    quality TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    metadata_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_market_events_token ON market_events(token_mint);
CREATE INDEX IF NOT EXISTS idx_market_events_sig ON market_events(signature);
CREATE INDEX IF NOT EXISTS idx_market_events_time ON market_events(local_receive_timestamp);

-- Token registry & lifecycle
CREATE TABLE IF NOT EXISTS token_registry (
    mint TEXT PRIMARY KEY,
    name TEXT,
    symbol TEXT,
    decimals INTEGER DEFAULT 9,
    first_observed_timestamp REAL NOT NULL,
    pool_created_timestamp REAL,
    pair_address TEXT,
    dex_id TEXT,
    initial_liquidity_usd REAL,
    current_lifecycle_state TEXT NOT NULL DEFAULT 'DISCOVERED'
);
CREATE INDEX IF NOT EXISTS idx_token_registry_state ON token_registry(current_lifecycle_state);

-- Token lifecycle transition log
CREATE TABLE IF NOT EXISTS token_lifecycle_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_mint TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    transition_timestamp REAL NOT NULL,
    reason TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_token_lifecycle_mint ON token_lifecycle_records(token_mint);

-- Token snapshots for historical tracking
CREATE TABLE IF NOT EXISTS token_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    token_mint TEXT NOT NULL,
    timestamp REAL NOT NULL,
    price_usd REAL,
    volume_24h_usd REAL,
    liquidity_usd REAL,
    fdv_usd REAL,
    buys_5m INTEGER DEFAULT 0,
    sells_5m INTEGER DEFAULT 0,
    lifecycle_state TEXT NOT NULL,
    lifecycle_reason TEXT NOT NULL,
    is_stale INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_token_snapshots_mint ON token_snapshots(token_mint, timestamp);

-- Wallet registry for whale monitoring
CREATE TABLE IF NOT EXISTS wallet_registry (
    wallet_address TEXT PRIMARY KEY,
    label TEXT,
    is_tracked INTEGER DEFAULT 1,
    first_seen REAL NOT NULL,
    last_seen REAL NOT NULL,
    total_tx_count INTEGER DEFAULT 0,
    swap_count INTEGER DEFAULT 0,
    transfer_count INTEGER DEFAULT 0
);

-- Whale activities classified
CREATE TABLE IF NOT EXISTS whale_activities (
    activity_id TEXT PRIMARY KEY,
    signature TEXT UNIQUE NOT NULL,
    wallet_address TEXT NOT NULL,
    token_mint TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    amount_tokens REAL NOT NULL,
    amount_usd REAL,
    timestamp REAL NOT NULL,
    slot INTEGER,
    confidence REAL NOT NULL,
    evidence_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_whale_activities_wallet ON whale_activities(wallet_address);
CREATE INDEX IF NOT EXISTS idx_whale_activities_mint ON whale_activities(token_mint);
CREATE INDEX IF NOT EXISTS idx_whale_activities_sig ON whale_activities(signature);

-- Agent decisions
CREATE TABLE IF NOT EXISTS agent_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    consensus_id TEXT NOT NULL,
    token_mint TEXT NOT NULL,
    timestamp REAL NOT NULL,
    agent_name TEXT NOT NULL,
    decision TEXT NOT NULL,
    score REAL,
    confidence REAL NOT NULL,
    latency_ms REAL NOT NULL,
    reason_codes_json TEXT NOT NULL,
    result_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_mint ON agent_decisions(token_mint);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_consensus ON agent_decisions(consensus_id);

-- Paper Orders
CREATE TABLE IF NOT EXISTS paper_orders (
    order_id TEXT PRIMARY KEY,
    token_mint TEXT NOT NULL,
    side TEXT NOT NULL,
    requested_amount_usd REAL NOT NULL,
    requested_qty REAL NOT NULL,
    limit_price_usd REAL,
    created_at REAL NOT NULL,
    status TEXT NOT NULL,
    rejection_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_paper_orders_mint ON paper_orders(token_mint);

-- Paper Fills
CREATE TABLE IF NOT EXISTS paper_fills (
    fill_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    token_mint TEXT NOT NULL,
    side TEXT NOT NULL,
    executed_qty REAL NOT NULL,
    executed_price_usd REAL NOT NULL,
    fee_usd REAL NOT NULL,
    slippage_bps REAL NOT NULL,
    fill_timestamp REAL NOT NULL,
    FOREIGN KEY(order_id) REFERENCES paper_orders(order_id)
);
CREATE INDEX IF NOT EXISTS idx_paper_fills_order ON paper_fills(order_id);

-- Paper Positions
CREATE TABLE IF NOT EXISTS paper_positions (
    position_id TEXT PRIMARY KEY,
    token_mint TEXT NOT NULL,
    token_symbol TEXT NOT NULL,
    qty REAL NOT NULL,
    average_entry_price_usd REAL NOT NULL,
    current_price_usd REAL NOT NULL,
    invested_capital_usd REAL NOT NULL,
    current_value_usd REAL NOT NULL,
    unrealized_pnl_usd REAL NOT NULL,
    unrealized_pnl_pct REAL NOT NULL,
    realized_pnl_usd REAL NOT NULL DEFAULT 0.0,
    total_fees_paid_usd REAL NOT NULL DEFAULT 0.0,
    is_open INTEGER NOT NULL DEFAULT 1,
    is_stale_price INTEGER NOT NULL DEFAULT 0,
    opened_at REAL NOT NULL,
    closed_at REAL,
    peak_price_usd REAL NOT NULL,
    exit_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_paper_positions_mint ON paper_positions(token_mint);
CREATE INDEX IF NOT EXISTS idx_paper_positions_open ON paper_positions(is_open);

-- Portfolio Snapshots
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    timestamp REAL NOT NULL,
    cash_balance_usd REAL NOT NULL,
    positions_value_usd REAL NOT NULL,
    total_equity_usd REAL NOT NULL,
    total_realized_pnl_usd REAL NOT NULL,
    total_unrealized_pnl_usd REAL NOT NULL,
    total_fees_paid_usd REAL NOT NULL,
    peak_equity_usd REAL NOT NULL,
    current_drawdown_pct REAL NOT NULL,
    max_drawdown_pct REAL NOT NULL,
    open_positions_count INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_portfolio_time ON portfolio_snapshots(timestamp);

-- System events & audits
CREATE TABLE IF NOT EXISTS system_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    timestamp REAL NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    details_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_system_events_type ON system_events(event_type);
"""


SCHEMA_V2 = """
-- Multi-agent structured consensus decisions
CREATE TABLE IF NOT EXISTS chief_decisions (
    consensus_id TEXT PRIMARY KEY,
    token_mint TEXT NOT NULL,
    token_symbol TEXT,
    data_timestamp REAL NOT NULL,
    decision_timestamp REAL NOT NULL,
    final_decision TEXT NOT NULL,
    strategic_decision TEXT,
    is_risk_vetoed INTEGER NOT NULL DEFAULT 0,
    chief_reason TEXT NOT NULL,
    sources_used_json TEXT NOT NULL,
    favorable_signals_json TEXT NOT NULL,
    unfavorable_signals_json TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    confidence_method TEXT NOT NULL,
    invalidation_conditions_json TEXT NOT NULL,
    identified_risks_json TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    expected_outcome TEXT NOT NULL,
    evaluation_horizon_sec INTEGER NOT NULL,
    target_price_usd REAL,
    invalidation_price_usd REAL,
    entry_price_usd REAL,
    recommended_position_usd REAL,
    processing_latency_ms REAL NOT NULL,
    details_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_chief_decisions_mint ON chief_decisions(token_mint);
CREATE INDEX IF NOT EXISTS idx_chief_decisions_time ON chief_decisions(decision_timestamp);
CREATE INDEX IF NOT EXISTS idx_chief_decisions_strat ON chief_decisions(strategy_version);

-- Measurable Learning: Decision outcome evaluations
CREATE TABLE IF NOT EXISTS decision_outcomes (
    outcome_id TEXT PRIMARY KEY,
    consensus_id TEXT NOT NULL,
    token_mint TEXT NOT NULL,
    evaluated_at REAL NOT NULL,
    horizon_sec INTEGER NOT NULL,
    entry_price_usd REAL NOT NULL,
    target_price_usd REAL,
    invalidation_price_usd REAL,
    peak_price_usd REAL NOT NULL,
    trough_price_usd REAL NOT NULL,
    final_price_usd REAL NOT NULL,
    is_correct INTEGER NOT NULL,
    is_false_positive INTEGER NOT NULL,
    is_true_negative INTEGER NOT NULL,
    simulated_net_return_pct REAL NOT NULL,
    max_drawdown_pct REAL NOT NULL,
    price_forecast_error_abs REAL NOT NULL,
    strategy_version TEXT NOT NULL,
    split_type TEXT NOT NULL DEFAULT 'TEST',
    FOREIGN KEY(consensus_id) REFERENCES chief_decisions(consensus_id)
);
CREATE INDEX IF NOT EXISTS idx_decision_outcomes_mint ON decision_outcomes(token_mint);
CREATE INDEX IF NOT EXISTS idx_decision_outcomes_strat ON decision_outcomes(strategy_version);
CREATE INDEX IF NOT EXISTS idx_decision_outcomes_split ON decision_outcomes(split_type);

-- Strategy version benchmarks
CREATE TABLE IF NOT EXISTS strategy_benchmarks (
    version TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    description TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    sample_size INTEGER NOT NULL DEFAULT 0,
    accuracy_rate REAL NOT NULL DEFAULT 0.0,
    false_positive_rate REAL NOT NULL DEFAULT 0.0,
    simulated_net_return_pct REAL NOT NULL DEFAULT 0.0,
    max_drawdown_pct REAL NOT NULL DEFAULT 0.0,
    benchmark_comparison_json TEXT
);

-- Live Trading: Trade proposals
CREATE TABLE IF NOT EXISTS live_proposals (
    proposal_id TEXT PRIMARY KEY,
    token_mint TEXT NOT NULL,
    token_symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    input_amount_sol REAL NOT NULL,
    expected_output_tokens REAL NOT NULL,
    min_output_tokens REAL NOT NULL,
    estimated_fee_sol REAL NOT NULL,
    slippage_bps REAL NOT NULL,
    quote_json TEXT NOT NULL,
    unsigned_tx_base64 TEXT NOT NULL,
    status TEXT NOT NULL,
    rejection_reason TEXT,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_live_proposals_wallet ON live_proposals(wallet_address);
CREATE INDEX IF NOT EXISTS idx_live_proposals_status ON live_proposals(status);

-- Live Trading: Broadcast transactions tracking
CREATE TABLE IF NOT EXISTS live_transactions (
    tx_signature TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    token_mint TEXT NOT NULL,
    side TEXT NOT NULL,
    amount_sol REAL NOT NULL,
    amount_tokens REAL NOT NULL,
    slot INTEGER,
    block_time REAL,
    status TEXT NOT NULL,
    confirmation_commitment TEXT NOT NULL,
    error_message TEXT,
    fee_paid_sol REAL,
    submitted_at REAL NOT NULL,
    confirmed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_live_tx_wallet ON live_transactions(wallet_address);
CREATE INDEX IF NOT EXISTS idx_live_tx_status ON live_transactions(status);

-- Independent Risk Audit Log
CREATE TABLE IF NOT EXISTS risk_audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT,
    check_name TEXT NOT NULL,
    passed INTEGER NOT NULL,
    threshold_val TEXT,
    observed_val TEXT,
    timestamp REAL NOT NULL,
    details_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_risk_audit_prop ON risk_audit_log(proposal_id);
"""
