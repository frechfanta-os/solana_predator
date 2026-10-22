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

        token_symbol = (event.metadata or {}).get("symbol", "TOKEN")
        data_ts = event.source_timestamp or event.local_receive_timestamp
        sources = [event.source.value]

        # 1. Absolute Inviolable Veto: RISK
        if risk_res and risk_res.decision == AgentDecision.VETO:
            reason = f"VETOED BY RISK: {', '.join(risk_res.reason_codes)}"
            logger.info("Token %s: %s", event.token_mint, reason)
            return ChiefConsensusRecord(
                consensus_id=consensus_id,
                token_mint=event.token_mint,
                token_symbol=token_symbol,
                timestamp=now,
                data_timestamp=data_ts,
                final_decision=AgentDecision.VETO,
                strategic_decision=AgentDecision.VETO,
                is_risk_vetoed=True,
                risk_veto_reasons=risk_res.reason_codes,
                chief_reason=reason,
                contributing_agents=agent_results,
                recommended_position_usd=None,
                processing_total_latency_ms=round(total_latency_ms, 3),
                sources_used=sources,
                unfavorable_signals=risk_res.reason_codes,
                identified_risks=risk_res.reason_codes,
                confidence_score=1.0,
                confidence_method="RISK_DETERMINISTIC_VETO",
                invalidation_conditions=["risk_boundary_breached"],
                strategy_version="v1.2.0-consensus",
                expected_outcome="ABSOLUTE_CAPITAL_PRESERVATION",
                evaluation_horizon_sec=900,
                entry_price_usd=event.price_usd,
            )

        # 2. Safety Veto: VET
        if vet_res and vet_res.decision == AgentDecision.VETO:
            reason = f"VETOED BY VET: {', '.join(vet_res.reason_codes)}"
            return ChiefConsensusRecord(
                consensus_id=consensus_id,
                token_mint=event.token_mint,
                token_symbol=token_symbol,
                timestamp=now,
                data_timestamp=data_ts,
                final_decision=AgentDecision.VETO,
                strategic_decision=AgentDecision.VETO,
                is_risk_vetoed=False,
                chief_reason=reason,
                contributing_agents=agent_results,
                recommended_position_usd=None,
                processing_total_latency_ms=round(total_latency_ms, 3),
                sources_used=sources,
                unfavorable_signals=vet_res.reason_codes,
                identified_risks=vet_res.reason_codes,
                confidence_score=0.95,
                confidence_method="SECURITY_AUDIT_VETO",
                invalidation_conditions=["contract_safety_check_failed"],
                strategy_version="v1.2.0-consensus",
                expected_outcome="AVOID_MALICIOUS_OR_UNSAFE_CONTRACT",
                evaluation_horizon_sec=900,
                entry_price_usd=event.price_usd,
            )

        # 3. Contrarian Veto: SKEPTIC
        if skeptic_res and skeptic_res.decision == AgentDecision.VETO:
            reason = f"VETOED BY SKEPTIC: {', '.join(skeptic_res.reason_codes)}"
            return ChiefConsensusRecord(
                consensus_id=consensus_id,
                token_mint=event.token_mint,
                token_symbol=token_symbol,
                timestamp=now,
                data_timestamp=data_ts,
                final_decision=AgentDecision.VETO,
                strategic_decision=AgentDecision.VETO,
                is_risk_vetoed=False,
                chief_reason=reason,
                contributing_agents=agent_results,
                recommended_position_usd=None,
                processing_total_latency_ms=round(total_latency_ms, 3),
                sources_used=sources,
                unfavorable_signals=skeptic_res.reason_codes,
                identified_risks=skeptic_res.reason_codes,
                confidence_score=0.90,
                confidence_method="CONTRARIAN_CONTRADICTION_ANALYSIS",
                invalidation_conditions=["conflicting_market_microstructure"],
                strategy_version="v1.2.0-consensus",
                expected_outcome="AVOID_HONEYPOT_OR_WASH_PUMP",
                evaluation_horizon_sec=900,
                entry_price_usd=event.price_usd,
            )

        # 4. Check Exit Signal (e.g. Whale outflow)
        if whale_res and whale_res.decision == AgentDecision.EXIT:
            reason = f"EXIT SIGNAL BY WHALE: {', '.join(whale_res.reason_codes)}"
            return ChiefConsensusRecord(
                consensus_id=consensus_id,
                token_mint=event.token_mint,
                token_symbol=token_symbol,
                timestamp=now,
                data_timestamp=data_ts,
                final_decision=AgentDecision.EXIT,
                strategic_decision=AgentDecision.EXIT,
                is_risk_vetoed=False,
                chief_reason=reason,
                contributing_agents=agent_results,
                recommended_position_usd=None,
                processing_total_latency_ms=round(total_latency_ms, 3),
                sources_used=sources,
                unfavorable_signals=whale_res.reason_codes,
                identified_risks=whale_res.reason_codes,
                confidence_score=0.92,
                confidence_method="WHALE_OUTFLOW_THRESHOLD",
                invalidation_conditions=["whale_cluster_dumping"],
                strategy_version="v1.2.0-consensus",
                expected_outcome="POSITION_EXIT_CAPITAL_PRESERVATION",
                evaluation_horizon_sec=900,
                entry_price_usd=event.price_usd,
            )

        # 5. Opportunity Consensus Evaluation
        buy_votes = 0
        scores: List[float] = []
        favorable_signals: List[str] = []
        unfavorable_signals: List[str] = []
        sources: List[str] = [event.source.value]
        identified_risks: List[str] = []

        for name, res in agent_results.items():
            if res.token_mint and res.sources_used:
                sources.extend(res.sources_used)
            if res.decision == AgentDecision.BUY_CANDIDATE:
                favorable_signals.extend(res.reason_codes)
            elif res.decision in (AgentDecision.VETO, AgentDecision.EXIT):
                unfavorable_signals.extend(res.reason_codes)
                identified_risks.extend(res.reason_codes)
            else:
                for r in res.reason_codes:
                    if "OK" in r or "MET" in r or "CLEARED" in r:
                        favorable_signals.append(r)
                    else:
                        unfavorable_signals.append(r)

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
        
        token_symbol = (event.metadata or {}).get("symbol", "TOKEN")
        current_px = event.price_usd
        data_ts = event.source_timestamp or event.local_receive_timestamp

        if is_buy_candidate and recommended_usd and recommended_usd >= 25.0:
            final_decision = AgentDecision.BUY_CANDIDATE
            reason = f"APPROVED PAPER BUY: {buy_votes} buy signals, consensus score {avg_score:.2f}, allocation ${recommended_usd:.2f}"
            expected_outcome = "+12.5% price advance within 900s horizon"
            target_px = round(current_px * 1.125, 8) if current_px else None
            inval_px = round(current_px * 0.955, 8) if current_px else None
        else:
            final_decision = AgentDecision.PASS
            reason = f"PASS: Insufficient signal strength (votes={buy_votes}, score={avg_score:.2f})"
            expected_outcome = "CAPITAL_PRESERVATION"
            target_px = None
            inval_px = None

        unique_sources = sorted(list(set(sources)))
        invalidation_conds = [
            "price_drop_exceeds_4.5%",
            "liquidity_collapse_below_5000_usd",
            "honeypot_or_freeze_authority_detected",
            "whale_rapid_distribution_detected",
            "evaluation_horizon_900s_elapsed",
        ]

        # Explicit confidence calculation: weighted combination of scan, whale, quant, skeptic
        conf_weights = {"SCAN": 0.20, "WHALE": 0.35, "QUANT": 0.25, "SKEPTIC": 0.20}
        weighted_conf = sum(
            agent_results[ag].confidence * conf_weights.get(ag, 0.1)
            for ag in conf_weights if ag in agent_results
        )
        norm_conf = max(0.1, min(1.0, weighted_conf if weighted_conf > 0 else 0.75))

        return ChiefConsensusRecord(
            consensus_id=consensus_id,
            token_mint=event.token_mint,
            token_symbol=token_symbol,
            timestamp=now,
            data_timestamp=data_ts,
            final_decision=final_decision,
            strategic_decision=final_decision,
            is_risk_vetoed=False,
            chief_reason=reason,
            contributing_agents=agent_results,
            recommended_position_usd=recommended_usd if final_decision == AgentDecision.BUY_CANDIDATE else None,
            processing_total_latency_ms=round(total_latency_ms, 3),
            sources_used=unique_sources,
            favorable_signals=favorable_signals,
            unfavorable_signals=unfavorable_signals,
            confidence_score=round(norm_conf, 4),
            confidence_method="MULTI_AGENT_WEIGHTED_HARMONIC",
            invalidation_conditions=invalidation_conds,
            identified_risks=identified_risks,
            strategy_version="v1.2.0-consensus",
            expected_outcome=expected_outcome,
            evaluation_horizon_sec=900,
            target_price_usd=target_px,
            invalidation_price_usd=inval_px,
            entry_price_usd=current_px,
        )
