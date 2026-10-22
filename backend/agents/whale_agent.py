"""WHALE Agent: Evaluates observed on-chain wallet accumulation and convergence."""

import time
from typing import Dict, Any, List
from backend.models import (
    AgentName,
    AgentDecision,
    AgentResult,
    NormalizedMarketEvent,
    WhaleConvergenceMetrics,
)
from backend.agents.base import BaseAgent


class WhaleAgent(BaseAgent):
    """Evaluates whale convergence metrics without speculative identity assumptions."""

    def __init__(self, min_convergence_threshold: float = 0.40):
        super().__init__(AgentName.WHALE)
        self.min_convergence = min_convergence_threshold

    async def evaluate(self, event: NormalizedMarketEvent, context: Dict[str, Any]) -> AgentResult:
        start_t = time.perf_counter()
        reasons: List[str] = []
        
        convergence: Optional[WhaleConvergenceMetrics] = context.get("whale_convergence")
        if not convergence or convergence.sample_size == 0:
            reasons.append("WHALE_NO_TRACKED_ACTIVITY")
            return self.build_result(
                [event.event_id],
                start_t,
                AgentDecision.PASS,
                reasons,
                score=0.5,
                confidence=0.5,
                confidence_interpretation="No recent tracked wallet activity",
                data_quality="GOOD",
            )

        if convergence.is_correlated_cluster:
            reasons.append("WHALE_CORRELATED_CLUSTER_DETECTED")

        score = convergence.convergence_score
        details = {
            "unique_whales": convergence.unique_whales_active,
            "net_flow_usd": convergence.net_flow_usd,
            "buy_volume_usd": convergence.buy_volume_usd,
            "sell_volume_usd": convergence.sell_volume_usd,
            "score": score,
        }

        if convergence.sell_volume_usd > convergence.buy_volume_usd:
            reasons.append("WHALE_NET_OUTFLOW_OBSERVED")
            return self.build_result(
                [event.event_id],
                start_t,
                AgentDecision.EXIT,
                reasons,
                score=score,
                confidence=0.85,
                confidence_interpretation="Observed selling pressure exceeds accumulation",
                data_quality="GOOD",
                details=details,
            )

        if score >= self.min_convergence and convergence.unique_whales_active >= 1:
            reasons.append(f"WHALE_CONVERGENCE_CONFIRMED_{score:.2f}")
            return self.build_result(
                [event.event_id],
                start_t,
                AgentDecision.BUY_CANDIDATE,
                reasons,
                score=score,
                confidence=0.90,
                confidence_interpretation="Deduplicated net whale accumulation detected",
                data_quality="GOOD",
                details=details,
            )

        reasons.append("WHALE_BELOW_ACCUMULATION_THRESHOLD")
        return self.build_result(
            [event.event_id],
            start_t,
            AgentDecision.PASS,
            reasons,
            score=score,
            confidence=0.75,
            confidence_interpretation="Activity within normal background volatility",
            data_quality="GOOD",
            details=details,
        )
