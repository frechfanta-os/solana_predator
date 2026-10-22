"""Typed exception hierarchy for SOLANA PREDATOR LLM Integration."""

from typing import Optional


class LLMError(Exception):
    """Base exception for all LLM client errors."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class LLMConfigurationError(LLMError):
    """Raised when provider configuration is missing, incomplete, or invalid."""
    pass


class LLMAuthenticationError(LLMError):
    """Raised on HTTP 401/403 unauthorized or invalid API key (never retried)."""
    pass


class LLMRateLimitError(LLMError):
    """Raised on HTTP 429 Too Many Requests (retryable with backoff)."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when the LLM provider call exceeds the configured timeout."""
    pass


class LLMServerError(LLMError):
    """Raised on HTTP 500/502/503/504 remote provider errors (retryable)."""
    pass


class LLMResponseFormatError(LLMError):
    """Raised when the LLM response is empty, malformed, or unparseable JSON."""
    pass


class LLMUnavailableError(LLMError):
    """Raised when the provider is unreachable, offline, or circuit-broken."""
    pass
