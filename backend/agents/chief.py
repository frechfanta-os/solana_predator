"""CHIEF Agent: Orchestrates consensus and synthesizes final decision records.

MANDATORY RULES:
- RISK VETO IS ABSOLUTE AND INVIOLABLE.
- LLM IS OPTIONAL AND OUTSIDE CRITICAL PATH.
- TIMEOUT NEVER APPROVES AN INCOMPLETE DECISION.
"""

import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from backend.models import (
    AgentName,
    AgentDecision,
    AgentResult,
    ChiefConsensusRecord,
    NormalizedMarketEvent,
)
from backend.agents.base import BaseAgent
from backend.config import settings

logger = logging.getLogger("predator.agents.chief")


class ChiefAgent(BaseAgent):
    """Consensus synthesizer enforcing strict priority: RISK > VET > SKEPTIC > OPPORTUNITY."""

    def __init__(self):
        super().__init__(AgentName.CHIEF)

    async def evaluate(self, event: NormalizedMarketEvent, context: Dict[str, Any]) -> AgentResult:
        # Standard evaluate signature if invoked directly
        start_t = time.perf_counter()
        return self.build_result(
            [event.event_id],
            start_t,
            AgentDecision.PASS,
            ["CHIEF_DIRECT_INVOCATION"],
            confidence=1.0,
        )

    def synthesize(
        self,
        event: NormalizedMarketEvent,
        agent_results: Dict[str, AgentResult],
        start_time_monotonic: float,
    ) -> ChiefConsensusRecord:
        """Synthesize all agent results into a binding consensus record."""
        consensus_id = f"chief_{uuid.uuid4().hex[:12]}"
        now = time.time()
        
        risk_res = agent_results.get(AgentName.RISK.value)
        vet_res = agent_results.get(AgentName.VET.value)
        skeptic_res = agent_results.get(AgentName.SKEPTIC.value)
        whale_res = agent_results.get(AgentName.WHALE.value)
        scan_res = agent_results.get(AgentName.SCAN.value)
        quant_res = agent_results.get(AgentName.QUANT.value)
        size_res = agent_results.get(AgentName.SIZE.value)

        total_latency_ms = (time.perf_counter() - start_time_monotonic) * 1000.0

        # 1. Absolute Inviolable Veto: RISK
        if risk_res and risk_res.decision == AgentDecision.VETO:
            reason = f"VETOED BY RISK: {', '.join(risk_res.reason_codes)}"
            logger.info("Token %s: %s", event.token_mint, reason)
            return ChiefConsensusRecord(
                consensus_id=consensus_id,
                token_mint=event.token_mint,
                timestamp=now,
                final_decision=AgentDecision.VETO,
                is_risk_vetoed=True,
                chief_reason=reason,
                contributing_agents=agent_results,
                recommended_position_usd=None,
                processing_total_latency_ms=round(total_latency_ms, 3),
            )

        # 2. Safety Veto: VET
        if vet_res and vet_res.decision == AgentDecision.VETO:
            reason = f"VETOED BY VET: {', '.join(vet_res.reason_codes)}"
            return ChiefConsensusRecord(
                consensus_id=consensus_id,
                token_mint=event.token_mint,
                timestamp=now,
                final_decision=AgentDecision.VETO,
                is_risk_vetoed=False,
                chief_reason=reason,
                contributing_agents=agent_results,
                recommended_position_usd=None,
                processing_total_latency_ms=round(total_latency_ms, 3),
            )

        # 3. Contrarian Veto: SKEPTIC
        if skeptic_res and skeptic_res.decision == AgentDecision.VETO:
            reason = f"VETOED BY SKEPTIC: {', '.join(skeptic_res.reason_codes)}"
            return ChiefConsensusRecord(
                consensus_id=consensus_id,
                token_mint=event.token_mint,
                timestamp=now,
                final_decision=AgentDecision.VETO,
                is_risk_vetoed=False,
                chief_reason=reason,
                contributing_agents=agent_results,
                recommended_position_usd=None,
                processing_total_latency_ms=round(total_latency_ms, 3),
            )

        # 4. Check Exit Signal (e.g. Whale outflow)
        if whale_res and whale_res.decision == AgentDecision.EXIT:
            reason = f"EXIT SIGNAL BY WHALE: {', '.join(whale_res.reason_codes)}"
            return ChiefConsensusRecord(
                consensus_id=consensus_id,
                token_mint=event.token_mint,
                timestamp=now,
                final_decision=AgentDecision.EXIT,
                is_risk_vetoed=False,
                chief_reason=reason,
                contributing_agents=agent_results,
                recommended_position_usd=None,
                processing_total_latency_ms=round(total_latency_ms, 3),
            )

        # 5. Opportunity Consensus Evaluation
        buy_votes = 0
        scores: List[float] = []

        for res in (scan_res, whale_res, quant_res):
            if res:
                if res.decision == AgentDecision.BUY_CANDIDATE:
                    buy_votes += 1
                if res.score is not None:
                    scores.append(res.score)

        avg_score = sum(scores) / len(scores) if scores else 0.0
        recommended_usd = None
        if size_res and size_res.details.get("recommended_usd"):
            recommended_usd = float(size_res.details["recommended_usd"])

        # Require at least 2 buy votes OR strong whale convergence + scan passing
        is_buy_candidate = (buy_votes >= 2 or (whale_res and whale_res.decision == AgentDecision.BUY_CANDIDATE and scan_res and scan_res.decision == AgentDecision.BUY_CANDIDATE))
        
        if is_buy_candidate and recommended_usd and recommended_usd >= 25.0:
            final_decision = AgentDecision.BUY_CANDIDATE
            reason = f"APPROVED PAPER BUY: {buy_votes} buy signals, consensus score {avg_score:.2f}, allocation ${recommended_usd:.2f}"
        else:
            final_decision = AgentDecision.PASS
            reason = f"PASS: Insufficient signal strength (votes={buy_votes}, score={avg_score:.2f})"

        return ChiefConsensusRecord(
            consensus_id=consensus_id,
            token_mint=event.token_mint,
            timestamp=now,
            final_decision=final_decision,
            is_risk_vetoed=False,
            chief_reason=reason,
            contributing_agents=agent_results,
            recommended_position_usd=recommended_usd if final_decision == AgentDecision.BUY_CANDIDATE else None,
            processing_total_latency_ms=round(total_latency_ms, 3),
        )
