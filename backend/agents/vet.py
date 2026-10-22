"""VET Agent: Evaluates contract integrity, metadata consistency, and data quality."""

import time
from typing import Dict, Any, List
from backend.models import (
    AgentName,
    AgentDecision,
    AgentResult,
    NormalizedMarketEvent,
    EventQuality,
)
from backend.agents.base import BaseAgent


class VetAgent(BaseAgent):
    """Validates data fidelity and screens for token safety flags."""

    def __init__(self):
        super().__init__(AgentName.VET)

    async def evaluate(self, event: NormalizedMarketEvent, context: Dict[str, Any]) -> AgentResult:
        start_t = time.perf_counter()
        reasons: List[str] = []

        # Check event quality
        if event.quality in (EventQuality.STALE, EventQuality.UNVERIFIED):
            reasons.append(f"VET_REJECTED_{event.quality.value}_DATA")
            return self.build_result(
                [event.event_id],
                start_t,
                AgentDecision.VETO,
                reasons,
                score=0.0,
                confidence=0.99,
                confidence_interpretation="Data feed fails freshness or verification check",
                data_quality=event.quality.value,
            )

        # Check token mint and pair existence
        if not event.token_mint or len(event.token_mint) < 32:
            reasons.append("VET_INVALID_TOKEN_MINT")
            return self.build_result(
                [event.event_id],
                start_t,
                AgentDecision.VETO,
                reasons,
                score=0.0,
                confidence=1.0,
                confidence_interpretation="Invalid Solana mint pubkey length",
                data_quality="DEGRADED",
            )

        # Check known malicious flags from metadata if present
        meta = event.metadata or {}
        if meta.get("freeze_authority_present") is True:
            reasons.append("VET_FREEZE_AUTHORITY_ACTIVE")
            return self.build_result(
                [event.event_id],
                start_t,
                AgentDecision.VETO,
                reasons,
                score=0.0,
                confidence=0.95,
                confidence_interpretation="Token contains freeze authority risk",
                data_quality="GOOD",
            )

        reasons.append("VET_INTEGRITY_VERIFIED")
        return self.build_result(
            [event.event_id],
            start_t,
            AgentDecision.PASS,
            reasons,
            score=0.90,
            confidence=0.95,
            confidence_interpretation="Data structure clean, no freeze authority detected",
            data_quality="GOOD",
        )
