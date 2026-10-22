"""Multi-agent engine package for SOLANA PREDATOR."""

from backend.agents.base import BaseAgent
from backend.agents.scan import ScanAgent
from backend.agents.whale_agent import WhaleAgent
from backend.agents.vet import VetAgent
from backend.agents.quant import QuantAgent
from backend.agents.skeptic import SkepticAgent
from backend.agents.size import SizeAgent
from backend.agents.risk import RiskAgent
from backend.agents.chief import ChiefAgent
from backend.agents.audit import AuditAgent
from backend.agents.orchestrator import AgentOrchestrator

__all__ = [
    "BaseAgent",
    "ScanAgent",
    "WhaleAgent",
    "VetAgent",
    "QuantAgent",
    "SkepticAgent",
    "SizeAgent",
    "RiskAgent",
    "ChiefAgent",
    "AuditAgent",
    "AgentOrchestrator",
]
