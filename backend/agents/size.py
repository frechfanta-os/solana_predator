"""SIZE Agent: Computes theoretical simulated position sizing."""

import time
from typing import Dict, Any, List
from backend.models import (
    AgentName,
    AgentDecision,
    AgentResult,
    NormalizedMarketEvent,
)
from backend.agents.base import BaseAgent
from backend.config import settings


class SizeAgent(BaseAgent):
    """Calculates simulated allocation based on available liquidity and portfolio equity."""

    def __init__(self, max_position_pct: Optional[float] = None):
        super().__init__(AgentName.SIZE)
        self.max_position_pct = max_position_pct or settings.PAPER_MAX_POSITION_PCT

    async def evaluate(self, event: NormalizedMarketEvent, context: Dict[str, Any]) -> AgentResult:
        start_t = time.perf_counter()
        reasons: List[str] = []

        portfolio_equity = context.get("portfolio_equity", settings.PAPER_INITIAL_CAPITAL)
        cash_balance = context.get("cash_balance", settings.PAPER_INITIAL_CAPITAL)
        liquidity = event.liquidity_usd or 1000.0

        # Maximum position cannot exceed max_position_pct of total equity
        max_by_equity = portfolio_equity * self.max_position_pct
        
        # Sizing cannot exceed 1% of pool liquidity to prevent unmodeled market impact
        max_by_liquidity = liquidity * 0.01

        recommended_usd = round(min(max_by_equity, max_by_liquidity, cash_balance), 2)

        if recommended_usd < 25.0:
            reasons.append("SIZE_INSUFFICIENT_RECOMMENDED_CAPITAL")
            return self.build_result(
                [event.event_id],
                start_t,
                AgentDecision.PASS,
                reasons,
                score=0.2,
                confidence=0.95,
                confidence_interpretation="Calculated size below minimum execution threshold",
                data_quality="GOOD",
                details={"recommended_usd": recommended_usd},
            )

        reasons.append(f"SIZE_CALCULATED_USD_{recommended_usd:.2f}")
        return self.build_result(
            [event.event_id],
            start_t,
            AgentDecision.BUY_CANDIDATE,
            reasons,
            score=0.90,
            confidence=0.95,
            confidence_interpretation="Sized conservatively relative to pool depth and virtual equity",
            data_quality="GOOD",
            details={
                "recommended_usd": recommended_usd,
                "max_by_equity": max_by_equity,
                "max_by_liquidity": max_by_liquidity,
            },
        )
