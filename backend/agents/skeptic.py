"""SKEPTIC Agent: Evaluates conflicting signals, wash trading, and contrarian risks."""

import time
from typing import Dict, Any, List
from backend.models import (
    AgentName,
    AgentDecision,
    AgentResult,
    NormalizedMarketEvent,
)
from backend.agents.base import BaseAgent


class SkepticAgent(BaseAgent):
    """Contrarian agent seeking reasons NOT to enter a position."""

    def __init__(self):
        super().__init__(AgentName.SKEPTIC)

    async def evaluate(self, event: NormalizedMarketEvent, context: Dict[str, Any]) -> AgentResult:
        start_t = time.perf_counter()
        reasons: List[str] = []
        score = 0.8  # 1.0 means no skepticism, 0.0 means extreme skepticism

        meta = event.metadata or {}
        txns_5m = meta.get("txns_5m") or {}
        buys = txns_5m.get("buys", 0)
        sells = txns_5m.get("sells", 0)

        # High buy-to-sell ratio could indicate wash trading or honeypot (nobody can sell)
        if buys > 20 and sells == 0:
            reasons.append("SKEPTIC_ZERO_SELLS_HONEYPOT_RISK")
            return self.build_result(
                [event.event_id],
                start_t,
                AgentDecision.VETO,
                reasons,
                score=0.1,
                confidence=0.88,
                confidence_interpretation="Complete absence of sells despite active buys hints at honeypot",
                data_quality="GOOD",
                details={"buys_5m": buys, "sells_5m": sells},
            )

        # Disproportionate price spike with tiny liquidity
        liq = event.liquidity_usd or 0.0
        vol = event.volume_24h_usd or 0.0
        if liq > 0 and (vol / liq) > 20.0:
            reasons.append("SKEPTIC_EXTREME_ROTATION_WASH_RISK")
            score = 0.40

        reasons.append("SKEPTIC_CLEARED_COUNTER_SIGNALS")
        return self.build_result(
            [event.event_id],
            start_t,
            AgentDecision.PASS if score < 0.6 else AgentDecision.BUY_CANDIDATE,
            reasons,
            score=score,
            confidence=0.85,
            confidence_interpretation="Contrarian signals within acceptable variance",
            data_quality="GOOD",
            details={"buys_5m": buys, "sells_5m": sells},
        )
