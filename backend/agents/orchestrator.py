"""Agent Orchestrator executing the multi-agent decision pipeline."""

import time
import asyncio
import logging
from typing import Dict, Any, Optional
from backend.models import (
    NormalizedMarketEvent,
    ChiefConsensusRecord,
    AgentResult,
    AgentName,
)
from backend.agents.scan import ScanAgent
from backend.agents.whale_agent import WhaleAgent
from backend.agents.vet import VetAgent
from backend.agents.quant import QuantAgent
from backend.agents.skeptic import SkepticAgent
from backend.agents.size import SizeAgent
from backend.agents.risk import RiskAgent
from backend.agents.chief import ChiefAgent
from backend.agents.audit import AuditAgent
from backend.database.repository import Repository
from backend.llm.client import LLMClient
from backend.llm.models import AgentLLMAdvisory
from backend.llm.prompt_templates import CHIEF_SYNTHESIS_SYSTEM_PROMPT, format_agent_user_prompt
from backend.config import settings

logger = logging.getLogger("predator.agents.orchestrator")


class AgentOrchestrator:
    """Manages parallel evaluation of specialized analysis agents and synthesizes decisions."""

    def __init__(self, repository: Repository, llm_client: Optional[LLMClient] = None):
        self.repository = repository
        self.llm_client = llm_client or LLMClient()
        self.scan = ScanAgent()
        self.whale = WhaleAgent()
        self.vet = VetAgent()
        self.quant = QuantAgent()
        self.skeptic = SkepticAgent()
        self.size = SizeAgent()
        self.risk = RiskAgent()
        self.chief = ChiefAgent()
        self.audit = AuditAgent()

    async def run_pipeline(
        self,
        event: NormalizedMarketEvent,
        context: Dict[str, Any],
    ) -> ChiefConsensusRecord:
        """Run all analysis agents, synthesize final consensus, and persist results."""
        start_mono = time.perf_counter()
        results: Dict[str, AgentResult] = {}

        # 1. Parallel execution of feature/evaluation agents
        eval_tasks = [
            self.vet.evaluate(event, context),
            self.scan.evaluate(event, context),
            self.whale.evaluate(event, context),
            self.quant.evaluate(event, context),
            self.skeptic.evaluate(event, context),
            self.size.evaluate(event, context),
            self.risk.evaluate(event, context),
        ]

        agent_outputs = await asyncio.gather(*eval_tasks, return_exceptions=True)

        latencies: Dict[str, float] = {}
        for res in agent_outputs:
            if isinstance(res, AgentResult):
                results[res.agent_name.value] = res
                latencies[res.agent_name.value] = res.processing_latency_ms
            elif isinstance(res, Exception):
                logger.error("Agent execution failed with exception: %s", res)

        # 2. Optional LLM advisory invocation (outside critical path with bounded timeout)
        llm_advisory: Optional[AgentLLMAdvisory] = None
        if self.llm_client and self.llm_client.enabled:
            try:
                llm_advisory = await asyncio.wait_for(
                    self._query_llm_advisory(event, results, context),
                    timeout=self.llm_client.timeout_seconds,
                )
            except asyncio.TimeoutError:
                logger.warning("LLM advisory timed out after %.1fs. Falling back safely.", self.llm_client.timeout_seconds)
            except Exception as e:
                logger.debug("LLM advisory skipped: %s", e)

        # 3. Chief consensus synthesis (incorporates LLM insights if available)
        consensus = self.chief.synthesize(event, results, start_mono, llm_advisory=llm_advisory)

        # 4. Audit execution
        audit_context = {
            "preliminary_decision": consensus.final_decision,
            "agent_latencies": latencies,
            "llm_advisory_active": llm_advisory is not None,
        }
        audit_res = await self.audit.evaluate(event, audit_context)
        results[AgentName.AUDIT.value] = audit_res
        consensus.contributing_agents[AgentName.AUDIT.value] = audit_res

        # 5. Persist each agent decision to SQLite repository
        for ag_name, res in results.items():
            try:
                await self.repository.save_agent_decision(consensus.consensus_id, event.token_mint, res)
            except Exception as e:
                logger.error("Failed to persist agent decision for %s: %s", ag_name, e)

        # 6. Persist structured chief consensus record
        try:
            await self.repository.save_chief_decision(consensus)
        except Exception as e:
            logger.error("Failed to persist chief decision: %s", e)

        return consensus

    async def _query_llm_advisory(
        self,
        event: NormalizedMarketEvent,
        results: Dict[str, AgentResult],
        context: Dict[str, Any],
    ) -> Optional[AgentLLMAdvisory]:
        """Query LLM for qualitative synthesis of multi-agent observations."""
        signals_summary = {
            ag: {
                "decision": res.decision.value if hasattr(res.decision, "value") else str(res.decision),
                "reasons": res.reason_codes,
                "confidence": res.confidence,
                "score": res.score,
            }
            for ag, res in results.items()
        }
        user_prompt = format_agent_user_prompt(
            token_mint=event.token_mint,
            event_data=event.model_dump(),
            context=context,
            contributing_agent_signals=signals_summary,
        )
        return await self.llm_client.query_structured_advisory(
            agent_name=AgentName.CHIEF.value,
            token_mint=event.token_mint,
            system_prompt=CHIEF_SYNTHESIS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

    async def _call_optional_llm(self, event: NormalizedMarketEvent) -> None:
        """Advisory LLM call stub (non-critical path)."""
        await asyncio.sleep(0.01)
