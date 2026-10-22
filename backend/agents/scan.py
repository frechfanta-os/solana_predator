"""SCAN Agent: Evaluates market discovery signals and basic liquidity filters."""

import time
from typing import Dict, Any, List
from backend.models import (
    AgentName,
    AgentDecision,
    AgentResult,
    NormalizedMarketEvent,
)
from backend.agents.base import BaseAgent


class ScanAgent(BaseAgent):
    """Evaluates initial discovery indicators: minimum liquidity, 24h volume presence."""

    def __init__(self, min_liquidity_usd: float = 5000.0):
        super().__init__(AgentName.SCAN)
        self.min_liquidity_usd = min_liquidity_usd

    async def evaluate(self, event: NormalizedMarketEvent, context: Dict[str, Any]) -> AgentResult:
        start_t = time.perf_counter()
        reasons: List[str] = []
        score = 0.5
        decision = AgentDecision.PASS

        liquidity = event.liquidity_usd
        if liquidity is None:
            reasons.append("SCAN_NO_LIQUIDITY_DATA")
            return self.build_result([event.event_id], start_t, AgentDecision.PASS, reasons, score=0.0, confidence=0.5, data_quality="DEGRADED")

        if liquidity < self.min_liquidity_usd:
            reasons.append(f"SCAN_LIQUIDITY_BELOW_THRESHOLD_{int(liquidity)}<{int(self.min_liquidity_usd)}")
            return self.build_result([event.event_id], start_t, AgentDecision.PASS, reasons, score=0.2, confidence=0.9, data_quality="ACCEPTABLE")

        reasons.append("SCAN_LIQUIDITY_MET")
        score = 0.70

        if event.volume_24h_usd and event.volume_24h_usd > 1000.0:
            reasons.append("SCAN_VOLUME_OBSERVED")
            score = 0.85
            decision = AgentDecision.BUY_CANDIDATE

        return self.build_result(
            [event.event_id],
            start_t,
            decision,
            reasons,
            score=score,
            confidence=0.90,
            confidence_interpretation="Market parameters parsed from verified feed",
            data_quality="GOOD",
            details={"liquidity_usd": liquidity, "volume_24h_usd": event.volume_24h_usd},
        )
