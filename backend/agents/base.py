"""Base abstract agent class enforcing structured validated output contracts."""

import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from backend.models import (
    AgentName,
    AgentDecision,
    AgentResult,
    NormalizedMarketEvent,
)


class BaseAgent(ABC):
    """Abstract base class for all SOLANA PREDATOR analysis agents."""

    def __init__(self, name: AgentName):
        self.name = name

    @abstractmethod
    async def evaluate(
        self,
        event: NormalizedMarketEvent,
        context: Dict[str, Any],
    ) -> AgentResult:
        """Execute agent analysis logic and return structured result."""
        pass

    def build_result(
        self,
        input_event_ids: List[str],
        start_time_monotonic: float,
        decision: AgentDecision,
        reason_codes: List[str],
        score: Optional[float] = None,
        confidence: float = 1.0,
        confidence_interpretation: str = "High confidence rule evaluation",
        data_quality: str = "GOOD",
        details: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """Helper to build validated AgentResult with monotonic clock latency."""
        latency_ms = (time.perf_counter() - start_time_monotonic) * 1000.0
        return AgentResult(
            agent_name=self.name,
            input_event_identifiers=input_event_ids,
            timestamp=time.time(),
            decision=decision,
            reason_codes=reason_codes,
            score=score,
            confidence=max(0.0, min(1.0, confidence)),
            confidence_interpretation=confidence_interpretation,
            data_quality=data_quality,
            processing_latency_ms=round(latency_ms, 3),
            details=details or {},
        )
