"""Data models and validated contracts for LLM Chat Completions and Agent Advisories."""

import time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from backend.models.agent import AgentDecision


class ChatMessage(BaseModel):
    """OpenAI-compatible chat message."""
    role: str = Field(..., description="Role of the message sender: system, user, or assistant")
    content: str = Field(..., description="Content payload of the message")


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request payload."""
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=1024, ge=1)
    stream: bool = False
    response_format: Optional[Dict[str, str]] = None


class ChatCompletionChoice(BaseModel):
    """Single completion choice returned by provider."""
    index: int = 0
    message: ChatMessage
    finish_reason: Optional[str] = "stop"


class ChatCompletionUsage(BaseModel):
    """Token usage metrics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""
    id: str = "chatcmpl-default"
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionChoice]
    usage: Optional[ChatCompletionUsage] = None
    latency_ms: float = 0.0


class AgentLLMAdvisory(BaseModel):
    """Validated structured advisory output from LLM for a multi-agent role."""
    agent: str = Field(..., description="Name of the calling agent (e.g. CHIEF, SCAN, WHALE)")
    token_mint: str = Field(..., description="Solana base58 token mint address")
    decision: AgentDecision = Field(default=AgentDecision.PASS, description="Recommended advisory action")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Heuristic qualitative confidence score")
    evidence: List[str] = Field(default_factory=list, description="Observed factual market observations")
    risks: List[str] = Field(default_factory=list, description="Identified warning signs or anomalies")
    invalidation_conditions: List[str] = Field(default_factory=list, description="Conditions that falsify this thesis")
    summary: str = Field(..., description="Concise qualitative synthesis rationale")
    strategy_version: str = Field(default="v1.2.0-llm-glm5", description="Strategy/prompt revision")
    created_at: float = Field(default_factory=time.time)
    latency_ms: float = 0.0
    provider: str = "space_z"
    model: str = "glm-5.3-flash"
    raw_tokens_used: int = 0
