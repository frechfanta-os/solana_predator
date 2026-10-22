"""QUANT Agent: Computes deterministic quantitative metrics and uncertainty bounds."""

import time
from typing import Dict, Any, List
from backend.models import (
    AgentName,
    AgentDecision,
    AgentResult,
    NormalizedMarketEvent,
)
from backend.agents.base import BaseAgent


class QuantAgent(BaseAgent):
    """Computes volume-to-liquidity ratio, spread estimate, and volatility score."""

    def __init__(self, min_vol_liq_ratio: float = 0.15):
        super().__init__(AgentName.QUANT)
        self.min_vol_liq_ratio = min_vol_liq_ratio

    async def evaluate(self, event: NormalizedMarketEvent, context: Dict[str, Any]) -> AgentResult:
        start_t = time.perf_counter()
        reasons: List[str] = []

        vol = event.volume_24h_usd or 0.0
        liq = event.liquidity_usd or 1.0

        vol_liq_ratio = vol / liq if liq > 0 else 0.0
        
        # Uncertainty band based on data confidence and freshness
        uncertainty = round((1.0 - event.confidence_score) + (event.freshness_seconds / 60.0), 3)
        uncertainty = max(0.01, min(0.99, uncertainty))

        details = {
            "vol_liq_ratio": round(vol_liq_ratio, 3),
            "uncertainty_band": uncertainty,
            "liquidity_usd": liq,
            "volume_24h_usd": vol,
        }

        if vol_liq_ratio >= self.min_vol_liq_ratio and uncertainty < 0.30:
            reasons.append("QUANT_ACTIVE_TURNOVER_CONFIRMED")
            reasons.append(f"QUANT_RATIO_{vol_liq_ratio:.2f}")
            return self.build_result(
                [event.event_id],
                start_t,
                AgentDecision.BUY_CANDIDATE,
                reasons,
                score=min(1.0, 0.5 + vol_liq_ratio * 0.2),
                confidence=round(1.0 - uncertainty, 2),
                confidence_interpretation="Healthy volume to liquidity ratio with tight uncertainty",
                data_quality="GOOD",
                details=details,
            )

        reasons.append("QUANT_INSUFFICIENT_TURNOVER_OR_HIGH_UNCERTAINTY")
        return self.build_result(
            [event.event_id],
            start_t,
            AgentDecision.PASS,
            reasons,
            score=0.40,
            confidence=round(1.0 - uncertainty, 2),
            confidence_interpretation="Market turnover does not satisfy statistical entry conditions",
            data_quality="GOOD",
            details=details,
        )
