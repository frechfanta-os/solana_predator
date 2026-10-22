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
        token_mint: Optional[str] = None,
        data_timestamp: Optional[float] = None,
        sources_used: Optional[List[str]] = None,
        favorable_signals: Optional[List[str]] = None,
        unfavorable_signals: Optional[List[str]] = None,
        confidence_method: str = "RULE_BASED_HEURISTIC",
        invalidation_conditions: Optional[List[str]] = None,
        identified_risks: Optional[List[str]] = None,
        strategy_version: str = "v1.0.0",
        expected_outcome: str = "NEUTRAL",
        evaluation_horizon_sec: int = 900,
        target_price_usd: Optional[float] = None,
        invalidation_price_usd: Optional[float] = None,
        entry_price_usd: Optional[float] = None,
    ) -> AgentResult:
        """Helper to build validated AgentResult with monotonic clock latency and decision metadata."""
        latency_ms = (time.perf_counter() - start_time_monotonic) * 1000.0
        return AgentResult(
            agent_name=self.name,
            input_event_identifiers=input_event_ids,
            timestamp=time.time(),
            decision=decision,
            strategic_decision=decision,
            reason_codes=reason_codes,
            score=score,
            confidence=max(0.0, min(1.0, confidence)),
            confidence_interpretation=confidence_interpretation,
            data_quality=data_quality,
            processing_latency_ms=round(latency_ms, 3),
            details=details or {},
            token_mint=token_mint,
            data_timestamp=data_timestamp,
            sources_used=sources_used or [],
            favorable_signals=favorable_signals or [],
            unfavorable_signals=unfavorable_signals or [],
            confidence_method=confidence_method,
            invalidation_conditions=invalidation_conditions or [],
            identified_risks=identified_risks or [],
            strategy_version=strategy_version,
            expected_outcome=expected_outcome,
            evaluation_horizon_sec=evaluation_horizon_sec,
            target_price_usd=target_price_usd,
            invalidation_price_usd=invalidation_price_usd,
            entry_price_usd=entry_price_usd,
        )
