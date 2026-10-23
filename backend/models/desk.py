"""Multi-Desk Intelligence Terminal models: desks, task executions, structured reports, and WS envelopes."""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DeskId(str, Enum):
    DESK_MARKET = "DESK_MARKET"
    DESK_WHALE = "DESK_WHALE"
    DESK_INVESTIGATION = "DESK_INVESTIGATION"
    DESK_QUANT = "DESK_QUANT"
    DESK_RISK = "DESK_RISK"
    DESK_COMMAND = "DESK_COMMAND"


class ExecutionState(str, Enum):
    IDLE = "IDLE"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    PAUSED = "PAUSED"


class AgentTaskExecution(BaseModel):
    """Execution record for a real agent task within a specialized desk."""
    task_id: str
    event_id: str
    desk_id: DeskId
    agent_id: str
    started_at: float
    finished_at: Optional[float] = None
    duration_ms: float = 0.0
    status: ExecutionState = ExecutionState.IDLE
    source: str = "INTERNAL"
    source_timestamp: Optional[float] = None
    observation_quality: str = "ACCEPTABLE"
    input_summary: str = ""
    output_summary: str = ""
    missing_fields: List[str] = Field(default_factory=list)
    error_code: Optional[str] = None
    error_message_sanitized: Optional[str] = None
    confidence: Optional[float] = None
    prompt_version: Optional[str] = None
    model_id: Optional[str] = None


class StructuredAgentReport(BaseModel):
    """Structured report separating observed facts, inferred conclusions, and missing evidence."""
    report_id: str
    desk_id: DeskId
    supervisor: str
    agent_id: str
    token_mint: Optional[str] = None
    event_id: str
    task_id: str
    observed_at: float
    source_timestamp: Optional[float] = None
    created_at: float
    source: str
    observation_quality: str
    observed_facts: List[str] = Field(default_factory=list)
    inferred_conclusions: List[str] = Field(default_factory=list)
    unknown_or_missing: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    decision: str = "PASS"
    confidence: Optional[float] = None
    rationale: str = ""
    is_stale: bool = False
    is_veto: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DeskStatusRecord(BaseModel):
    """Operational state and telemetry summary for a specialized desk."""
    desk_id: DeskId
    name: str
    supervisor: str
    description: str
    status: ExecutionState = ExecutionState.IDLE
    is_paused: bool = False
    agents: List[str] = Field(default_factory=list)
    polling_interval_sec: float = 15.0
    active_tasks: int = 0
    queued_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    skipped_tasks: int = 0
    retry_count: int = 0
    last_execution_at: Optional[float] = None
    last_duration_ms: float = 0.0
    last_source: Optional[str] = None
    has_stale_data: bool = False
    has_missing_data: bool = False
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None


class WatchlistItem(BaseModel):
    """Watchlist entry for tokens (Desk 1) or public wallets (Desk 2)."""
    identifier: str
    item_type: str = "TOKEN"  # TOKEN or WALLET
    label: Optional[str] = None
    added_at: float
    notes: Optional[str] = None


class TerminalWsEnvelope(BaseModel):
    """Standardized WebSocket event envelope for the multi-desk terminal."""
    event_id: str
    event_type: str
    timestamp_utc: float
    desk_id: Optional[str] = None
    agent_id: Optional[str] = None
    correlation_id: Optional[str] = None
    payload_version: str = "1.0"
    payload: Dict[str, Any] = Field(default_factory=dict)
