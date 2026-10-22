"""RISK Agent: Enforces absolute risk bounds, drawdown limits, and veto power.

MANDATORY INTEGRITY:
- DETERMINISTIC LIMITS AND HARD VETOES.
- NO AGENT CAN OVERRIDE RISK.
"""

import time
from typing import Dict, Any, List, Optional
from backend.models import (
    AgentName,
    AgentDecision,
    AgentResult,
    NormalizedMarketEvent,
)
from backend.agents.base import BaseAgent
from backend.config import settings


class RiskAgent(BaseAgent):
    """Absolute risk arbiter. Has unconditional veto power over all trade propositions."""

    def __init__(
        self,
        max_open_positions: Optional[int] = None,
        max_drawdown_pct: Optional[float] = None,
    ):
        super().__init__(AgentName.RISK)
        self.max_open_positions = max_open_positions or settings.PAPER_MAX_OPEN_POSITIONS
        self.max_drawdown_pct = max_drawdown_pct or settings.PAPER_MAX_DRAWDOWN_VETO_PCT

    async def evaluate(self, event: NormalizedMarketEvent, context: Dict[str, Any]) -> AgentResult:
        start_t = time.perf_counter()
        reasons: List[str] = []

        open_positions = context.get("open_positions_count", 0)
        current_drawdown = context.get("current_drawdown_pct", 0.0)
        has_existing_position = context.get("has_existing_position", False)
        cash_balance = context.get("cash_balance", 0.0)

        # 1. Hard Veto: Portfolio Max Drawdown Exceeded
        if current_drawdown >= self.max_drawdown_pct:
            reasons.append(f"RISK_VETO_MAX_DRAWDOWN_EXCEEDED_{current_drawdown*100:.1f}%")
            return self.build_result(
                [event.event_id],
                start_t,
                AgentDecision.VETO,
                reasons,
                score=0.0,
                confidence=1.0,
                confidence_interpretation="Circuit breaker tripped: portfolio drawdown veto",
                data_quality="GOOD",
                details={"current_drawdown": current_drawdown, "limit": self.max_drawdown_pct},
            )

        # 2. Hard Veto: Max Open Positions Reached
        if open_positions >= self.max_open_positions:
            reasons.append(f"RISK_VETO_MAX_CONCURRENT_POSITIONS_{open_positions}>={self.max_open_positions}")
            return self.build_result(
                [event.event_id],
                start_t,
                AgentDecision.VETO,
                reasons,
                score=0.0,
                confidence=1.0,
                confidence_interpretation="Simulated position slots fully occupied",
                data_quality="GOOD",
                details={"open_positions": open_positions, "limit": self.max_open_positions},
            )

        # 3. Hard Veto: Already holding this token
        if has_existing_position:
            reasons.append("RISK_VETO_DUPLICATE_TOKEN_EXPOSURE")
            return self.build_result(
                [event.event_id],
                start_t,
                AgentDecision.VETO,
                reasons,
                score=0.0,
                confidence=1.0,
                confidence_interpretation="Token is already actively held in paper portfolio",
                data_quality="GOOD",
            )

        # 4. Hard Veto: Insufficient cash balance
        if cash_balance < 50.0:
            reasons.append("RISK_VETO_INSUFFICIENT_CASH")
            return self.build_result(
                [event.event_id],
                start_t,
                AgentDecision.VETO,
                reasons,
                score=0.0,
                confidence=1.0,
                confidence_interpretation="Available cash balance insufficient for minimal allocation",
                data_quality="GOOD",
                details={"cash_balance": cash_balance},
            )

        reasons.append("RISK_CHECKS_PASSED")
        return self.build_result(
            [event.event_id],
            start_t,
            AgentDecision.PASS,
            reasons,
            score=1.0,
            confidence=1.0,
            confidence_interpretation="All deterministic portfolio risk boundaries satisfied",
            data_quality="GOOD",
        )
