"""SOLANA PREDATOR LLM Integration Package (GLM-5.3-Flash / OpenAI Compatible)."""

from backend.llm.exceptions import (
    LLMError,
    LLMConfigurationError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMServerError,
    LLMResponseFormatError,
    LLMUnavailableError,
)
from backend.llm.models import (
    ChatMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatCompletionUsage,
    AgentLLMAdvisory,
)
from backend.llm.client import LLMClient
from backend.llm.prompt_templates import (
    CHIEF_SYNTHESIS_SYSTEM_PROMPT,
    SKEPTIC_SYSTEM_PROMPT,
    WHALE_SYSTEM_PROMPT,
    VET_SYSTEM_PROMPT,
    QUANT_SYSTEM_PROMPT,
    SIZE_SYSTEM_PROMPT,
    RISK_SYSTEM_PROMPT,
    AUDIT_SYSTEM_PROMPT,
    format_agent_user_prompt,
)

__all__ = [
    "LLMClient",
    "LLMError",
    "LLMConfigurationError",
    "LLMAuthenticationError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMServerError",
    "LLMResponseFormatError",
    "LLMUnavailableError",
    "ChatMessage",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "ChatCompletionChoice",
    "ChatCompletionUsage",
    "AgentLLMAdvisory",
    "CHIEF_SYNTHESIS_SYSTEM_PROMPT",
    "SKEPTIC_SYSTEM_PROMPT",
    "WHALE_SYSTEM_PROMPT",
    "VET_SYSTEM_PROMPT",
    "QUANT_SYSTEM_PROMPT",
    "SIZE_SYSTEM_PROMPT",
    "RISK_SYSTEM_PROMPT",
    "AUDIT_SYSTEM_PROMPT",
    "format_agent_user_prompt",
]
