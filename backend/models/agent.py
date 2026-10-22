"""Multi-agent engine models and validated decision contracts."""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AgentName(str, Enum):
    CHIEF = "CHIEF"
    SCAN = "SCAN"
    WHALE = "WHALE"
    VET = "VET"
    QUANT = "QUANT"
    SKEPTIC = "SKEPTIC"
    SIZE = "SIZE"
    RISK = "RISK"
    AUDIT = "AUDIT"


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
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence_interpretation: str
    data_quality: str
    processing_latency_ms: float
    details: Dict[str, Any] = Field(default_factory=dict)


class ChiefConsensusRecord(BaseModel):
    consensus_id: str
    token_mint: str
    timestamp: float
    final_decision: AgentDecision
    is_risk_vetoed: bool = False
    chief_reason: str
    contributing_agents: Dict[str, AgentResult]
    recommended_position_usd: Optional[float] = None
    processing_total_latency_ms: float
