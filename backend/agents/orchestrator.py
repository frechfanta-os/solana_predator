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
from backend.config import settings

logger = logging.getLogger("predator.agents.orchestrator")


class AgentOrchestrator:
    """Manages parallel evaluation of specialized analysis agents and synthesizes decisions."""

    def __init__(self, repository: Repository):
        self.repository = repository
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

        # 2. Optional LLM invocation (outside critical path with bounded timeout)
        if settings.LLM_ENABLED:
            try:
                # Simulated or real LLM advisory check
                await asyncio.wait_for(self._call_optional_llm(event), timeout=settings.LLM_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                logger.warning("LLM advisory timed out after %.1fs. Falling back safely.", settings.LLM_TIMEOUT_SECONDS)
            except Exception as e:
                logger.debug("LLM advisory skipped: %s", e)

        # 3. Chief consensus synthesis
        consensus = self.chief.synthesize(event, results, start_mono)

        # 4. Audit execution
        audit_context = {
            "preliminary_decision": consensus.final_decision,
            "agent_latencies": latencies,
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

    async def _call_optional_llm(self, event: NormalizedMarketEvent) -> None:
        """Advisory LLM call stub (non-critical path)."""
        await asyncio.sleep(0.01)
