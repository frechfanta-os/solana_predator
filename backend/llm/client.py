"""Centralized, resilient LLM Provider Client supporting OpenAI Chat Completions protocol."""

import time
import json
import random
import asyncio
import logging
from typing import Dict, Any, List, Optional
import aiohttp

from backend.llm.models import (
    ChatMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatCompletionUsage,
    AgentLLMAdvisory,
    LLMAdvisoryResult,
)
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
from backend.models.agent import AgentDecision
from backend.config import settings

logger = logging.getLogger("predator.llm.client")


class LLMClient:
    """Centralized asynchronous client for OpenAI-compatible LLM Chat Completions.
    
    Invariants:
    - Zero private key or seed phrase exposure (never logged or transmitted).
    - Monotonic latency tracking.
    - Concurrency limited via asyncio Semaphore.
    - Exponential backoff with random jitter for 429 and 5xx errors.
    - Instant non-retry failure on 401/403 authentication errors.
    - Graceful fallback when disabled or unavailable.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        max_concurrency: Optional[int] = None,
        auth_header_style: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
        enabled: Optional[bool] = None,
    ):
        self.base_url = (base_url or settings.LLM_API_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL
        self.timeout_seconds = timeout_seconds or settings.LLM_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.LLM_MAX_RETRIES
        self.max_concurrency = max_concurrency or settings.LLM_MAX_CONCURRENCY
        self.auth_header_style = (auth_header_style or settings.LLM_AUTH_HEADER_STYLE).lower()
        self.enabled = enabled if enabled is not None else settings.LLM_ENABLED
        self.provider_name = settings.LLM_PROVIDER

        self._session = session
        self._owns_session = session is None
        self._semaphore = asyncio.Semaphore(self.max_concurrency)

        # Operational metrics and counters
        self.call_count = 0
        self.error_count = 0
        self.total_latency_ms = 0.0
        self.consecutive_failures = 0
        self.last_error: Optional[str] = None
        self.last_connectivity_check: Optional[Dict[str, Any]] = None

    def get_endpoint_url(self) -> str:
        """Construct standard chat completions endpoint URL."""
        return f"{self.base_url}/chat/completions"

    def get_request_headers(self) -> Dict[str, str]:
        """Construct HTTP headers based on configured auth style."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            if self.auth_header_style in ("bearer", "both"):
                headers["Authorization"] = f"Bearer {self.api_key}"
            if self.auth_header_style in ("x-api-key", "both"):
                headers["X-Api-Key"] = self.api_key
        return headers

    @staticmethod
    def mask_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """Return headers with secrets securely masked for safe logging."""
        masked = {}
        for k, v in headers.items():
            k_lower = k.lower()
            if "authorization" in k_lower or "api-key" in k_lower or "token" in k_lower:
                if len(v) > 12:
                    masked[k] = f"{v[:6]}...{v[-4:]}"
                else:
                    masked[k] = "***MASKED***"
            else:
                masked[k] = v
        return masked

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close managed client session."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Execute chat completion request with retry, backoff, and concurrency bounding."""
        if not self.base_url:
            raise LLMConfigurationError("LLM base URL is not configured")

        url = self.get_endpoint_url()
        headers = self.get_request_headers()
        payload = request.model_dump(exclude_none=True)

        logger.debug(
            "Dispatching LLM request to %s (model: %s, headers: %s)",
            url,
            request.model,
            self.mask_headers(headers),
        )

        attempt = 0
        last_exception: Optional[Exception] = None

        while attempt <= self.max_retries:
            start_mono = time.perf_counter()
            try:
                async with self._semaphore:
                    session = await self._get_session()
                    timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
                    
                    async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
                        status = resp.status
                        body_text = await resp.text()

                        latency_ms = (time.perf_counter() - start_mono) * 1000.0

                        # 1. Authentication / Permission Errors (Never retry)
                        if status in (401, 403):
                            msg = f"LLM Authentication failed (HTTP {status}): {body_text[:200]}"
                            self._record_failure(msg)
                            raise LLMAuthenticationError(msg, status_code=status)

                        # 2. Rate Limit (429) -> Retryable
                        if status == 429:
                            msg = f"LLM Rate limit reached (HTTP 429): {body_text[:200]}"
                            last_exception = LLMRateLimitError(msg, status_code=429)
                            attempt += 1
                            if attempt <= self.max_retries:
                                delay = min(4.0, (2 ** attempt) * 0.5) * random.uniform(0.8, 1.2)
                                logger.warning("Rate limit on %s. Retrying in %.2fs (attempt %d/%d)...", self.model, delay, attempt, self.max_retries)
                                await asyncio.sleep(delay)
                                continue
                            self._record_failure(msg)
                            raise last_exception

                        # 3. Server Errors (500, 502, 503, 504) -> Retryable
                        if status >= 500:
                            msg = f"LLM Server error (HTTP {status}): {body_text[:200]}"
                            last_exception = LLMServerError(msg, status_code=status)
                            attempt += 1
                            if attempt <= self.max_retries:
                                delay = min(4.0, (2 ** attempt) * 0.5) * random.uniform(0.8, 1.2)
                                logger.warning("Server error %d on %s. Retrying in %.2fs (attempt %d/%d)...", status, self.model, delay, attempt, self.max_retries)
                                await asyncio.sleep(delay)
                                continue
                            self._record_failure(msg)
                            raise last_exception

                        # 4. Client Request Errors (400, 404, 422) -> Non-retryable
                        if status >= 400:
                            msg = f"LLM Client error (HTTP {status}): {body_text[:200]}"
                            self._record_failure(msg)
                            raise LLMError(msg, status_code=status)

                        # 5. Success Validation
                        if not body_text or not body_text.strip():
                            msg = "LLM returned empty response body"
                            self._record_failure(msg)
                            raise LLMResponseFormatError(msg, status_code=status)

                        try:
                            data = json.loads(body_text)
                        except json.JSONDecodeError as e:
                            msg = f"Malformed JSON from LLM: {e}"
                            self._record_failure(msg)
                            raise LLMResponseFormatError(msg, status_code=status)

                        choices_raw = data.get("choices", [])
                        if not choices_raw or not isinstance(choices_raw, list):
                            msg = "LLM response missing 'choices' array"
                            self._record_failure(msg)
                            raise LLMResponseFormatError(msg, status_code=status)

                        parsed_choices = []
                        for c in choices_raw:
                            msg_dict = c.get("message", {})
                            content = msg_dict.get("content", "")
                            parsed_choices.append(
                                ChatCompletionChoice(
                                    index=c.get("index", 0),
                                    message=ChatMessage(
                                        role=msg_dict.get("role", "assistant"),
                                        content=content if content is not None else "",
                                    ),
                                    finish_reason=c.get("finish_reason", "stop"),
                                )
                            )

                        usage_raw = data.get("usage")
                        usage = None
                        if usage_raw and isinstance(usage_raw, dict):
                            usage = ChatCompletionUsage(
                                prompt_tokens=usage_raw.get("prompt_tokens", 0),
                                completion_tokens=usage_raw.get("completion_tokens", 0),
                                total_tokens=usage_raw.get("total_tokens", 0),
                            )

                        response = ChatCompletionResponse(
                            id=data.get("id", f"chatcmpl_{int(time.time()*1000)}"),
                            object=data.get("object", "chat.completion"),
                            created=data.get("created", int(time.time())),
                            model=data.get("model", request.model),
                            choices=parsed_choices,
                            usage=usage,
                            latency_ms=round(latency_ms, 2),
                        )

                        self._record_success(latency_ms)
                        return response

            except asyncio.CancelledError:
                logger.info("LLM completion request cancelled")
                raise
            except asyncio.TimeoutError:
                attempt += 1
                msg = f"LLM request timed out after {self.timeout_seconds:.1f}s"
                last_exception = LLMTimeoutError(msg)
                if attempt <= self.max_retries:
                    delay = min(4.0, (2 ** attempt) * 0.5) * random.uniform(0.8, 1.2)
                    logger.warning("Timeout on %s. Retrying in %.2fs (attempt %d/%d)...", self.model, delay, attempt, self.max_retries)
                    await asyncio.sleep(delay)
                    continue
                self._record_failure(msg)
                raise last_exception
            except aiohttp.ClientError as e:
                attempt += 1
                msg = f"LLM connection error: {e}"
                last_exception = LLMUnavailableError(msg)
                if attempt <= self.max_retries:
                    delay = min(4.0, (2 ** attempt) * 0.5) * random.uniform(0.8, 1.2)
                    logger.warning("Connection failure on %s. Retrying in %.2fs (attempt %d/%d)...", self.model, delay, attempt, self.max_retries)
                    await asyncio.sleep(delay)
                    continue
                self._record_failure(msg)
                raise last_exception

        if last_exception:
            raise last_exception
        raise LLMUnavailableError("LLM call failed after retries")

    def _record_success(self, latency_ms: float) -> None:
        self.call_count += 1
        self.total_latency_ms += latency_ms
        self.consecutive_failures = 0
        self.last_error = None

    def _record_failure(self, error_msg: str) -> None:
        self.error_count += 1
        self.consecutive_failures += 1
        self.last_error = error_msg

    def get_status(self) -> Dict[str, Any]:
        """Return operational telemetry without exposing credentials."""
        avg_lat = round(self.total_latency_ms / max(1, self.call_count), 2)
        has_key = bool(self.api_key and len(self.api_key.strip()) > 5)

        if not (self.base_url and has_key):
            config_state = "NOT_CONFIGURED"
        else:
            config_state = "CONFIGURED"

        if not self.enabled:
            avail_state = "DISABLED"
        elif config_state == "NOT_CONFIGURED":
            avail_state = "NOT_CONFIGURED"
        elif self.consecutive_failures > 0:
            avail_state = "UNAVAILABLE"
        elif self.call_count > 0:
            avail_state = "AVAILABLE"
        else:
            avail_state = "STANDBY"

        status_data = {
            "enabled": self.enabled,
            "configuration_state": config_state,
            "availability_state": avail_state,
            "configured": bool(self.base_url and has_key),
            "available": avail_state == "AVAILABLE",
            "provider": self.provider_name,
            "model": self.model,
            "base_url": self.base_url,
            "api_key_configured": has_key,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "max_concurrency": self.max_concurrency,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "consecutive_failures": self.consecutive_failures,
            "avg_latency_ms": avg_lat,
            "last_error": self.last_error,
        }
        if self.last_connectivity_check:
            status_data["last_connectivity_check"] = self.last_connectivity_check
        return status_data

    async def check_connectivity(self) -> Dict[str, Any]:
        """Probe provider connectivity with a minimal bounded ping.
        
        Does NOT expose credentials or leak secrets.
        Returns explicit status distinguishing NOT_CONFIGURED, AUTHENTICATION_FAILED, UNAVAILABLE, AVAILABLE.
        """
        if not self.base_url:
            res = {
                "connectivity_status": "NOT_CONFIGURED",
                "configured": False,
                "available": False,
                "message": "Base URL not configured",
                "timestamp": time.time(),
            }
            self.last_connectivity_check = res
            return res

        if not self.api_key:
            res = {
                "connectivity_status": "NOT_CONFIGURED",
                "configured": False,
                "available": False,
                "message": "API key not configured",
                "timestamp": time.time(),
            }
            self.last_connectivity_check = res
            return res

        start_mono = time.perf_counter()
        req = ChatCompletionRequest(
            model=self.model,
            messages=[ChatMessage(role="user", content="ping")],
            max_tokens=5,
        )
        try:
            resp = await self.complete(req)
            latency = (time.perf_counter() - start_mono) * 1000.0
            res = {
                "connectivity_status": "AVAILABLE",
                "configured": True,
                "available": True,
                "http_status": 200,
                "latency_ms": round(latency, 2),
                "model": resp.model,
                "timestamp": time.time(),
            }
            self.last_connectivity_check = res
            return res
        except LLMAuthenticationError as e:
            res = {
                "connectivity_status": "AUTHENTICATION_FAILED",
                "configured": True,
                "available": False,
                "http_status": e.status_code or 401,
                "error": "Authentication refused by provider",
                "timestamp": time.time(),
            }
            self.last_connectivity_check = res
            return res
        except (LLMUnavailableError, LLMTimeoutError, LLMServerError) as e:
            res = {
                "connectivity_status": "UNAVAILABLE",
                "configured": True,
                "available": False,
                "http_status": getattr(e, "status_code", 503),
                "error": str(e),
                "timestamp": time.time(),
            }
            self.last_connectivity_check = res
            return res
        except Exception as e:
            res = {
                "connectivity_status": "ERROR",
                "configured": True,
                "available": False,
                "error": str(e),
                "timestamp": time.time(),
            }
            self.last_connectivity_check = res
            return res

    async def request_advisory(
        self,
        agent_name: str,
        token_mint: str,
        system_prompt: str,
        user_prompt: str,
        prompt_version: str = "v1.0-chief-synthesis",
    ) -> LLMAdvisoryResult:
        """Query LLM for qualitative advisory analysis and return typed LLMAdvisoryResult."""
        if not self.enabled:
            return LLMAdvisoryResult(
                status="LLM_NOT_CONFIGURED",
                message="LLM provider is disabled. Operating in deterministic fallback mode.",
                advisory=None,
            )

        if not self.api_key:
            return LLMAdvisoryResult(
                status="LLM_NOT_CONFIGURED",
                message="LLM API key is missing. Operating in deterministic fallback mode.",
                advisory=None,
            )

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]

        req = ChatCompletionRequest(
            model=self.model,
            messages=messages,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )

        try:
            resp = await self.complete(req)
            if not resp.choices:
                return LLMAdvisoryResult(
                    status="LLM_INVALID_RESPONSE",
                    message="LLM returned response with empty choices array.",
                    advisory=None,
                    latency_ms=resp.latency_ms,
                )
            raw_text = resp.choices[0].message.content.strip()

            if "```" in raw_text:
                parts = raw_text.split("```")
                for part in parts:
                    clean = part.strip()
                    if clean.startswith("json"):
                        clean = clean[4:].strip()
                    if clean.startswith("{") and clean.endswith("}"):
                        raw_text = clean
                        break

            try:
                parsed_data = json.loads(raw_text)
            except json.JSONDecodeError as e:
                return LLMAdvisoryResult(
                    status="LLM_INVALID_RESPONSE",
                    message=f"LLM content is not valid JSON: {e}",
                    advisory=None,
                    latency_ms=resp.latency_ms,
                )

            dec_str = parsed_data.get("decision", "PASS").upper()
            if dec_str in ("BUY", "BUY_CANDIDATE"):
                enum_dec = AgentDecision.BUY_CANDIDATE
            elif dec_str == "VETO":
                enum_dec = AgentDecision.VETO
            elif dec_str == "EXIT":
                enum_dec = AgentDecision.EXIT
            elif dec_str == "HOLD":
                enum_dec = AgentDecision.HOLD
            else:
                enum_dec = AgentDecision.PASS

            tokens_used = resp.usage.total_tokens if resp.usage else 0

            advisory = AgentLLMAdvisory(
                agent=agent_name,
                token_mint=token_mint,
                decision=enum_dec,
                confidence=float(min(1.0, max(0.0, parsed_data.get("confidence", 0.5)))),
                evidence=list(parsed_data.get("evidence", [])),
                risks=list(parsed_data.get("risks", [])),
                invalidation_conditions=list(parsed_data.get("invalidation_conditions", [])),
                summary=str(parsed_data.get("summary", "Analysis completed")),
                strategy_version=f"glm5-{self.model}",
                prompt_version=prompt_version,
                created_at=time.time(),
                latency_ms=resp.latency_ms,
                provider=self.provider_name,
                model=self.model,
                raw_tokens_used=tokens_used,
            )
            return LLMAdvisoryResult(
                status="SUCCESS",
                message="Advisory synthesized successfully",
                advisory=advisory,
                http_status=200,
                latency_ms=resp.latency_ms,
            )

        except LLMAuthenticationError as e:
            return LLMAdvisoryResult(
                status="LLM_AUTH_FAILED",
                message=f"LLM authentication refused (HTTP {e.status_code})",
                advisory=None,
                http_status=e.status_code,
            )
        except (LLMUnavailableError, LLMTimeoutError, LLMServerError) as e:
            return LLMAdvisoryResult(
                status="LLM_UNAVAILABLE",
                message=f"LLM provider unavailable: {e}",
                advisory=None,
                http_status=getattr(e, "status_code", 503),
            )
        except LLMResponseFormatError as e:
            return LLMAdvisoryResult(
                status="LLM_INVALID_RESPONSE",
                message=f"LLM response format error: {e}",
                advisory=None,
                http_status=getattr(e, "status_code", 422),
            )
        except Exception as e:
            return LLMAdvisoryResult(
                status="LLM_UNAVAILABLE",
                message=f"LLM query unexpected error: {e}",
                advisory=None,
            )

    async def query_structured_advisory(
        self,
        agent_name: str,
        token_mint: str,
        system_prompt: str,
        user_prompt: str,
        prompt_version: str = "v1.0-chief-synthesis",
    ) -> Optional[AgentLLMAdvisory]:
        """Query LLM for qualitative advisory analysis and parse structured output.
        
        Returns None gracefully if LLM is disabled or fails, allowing immediate fallback.
        """
        res = await self.request_advisory(
            agent_name=agent_name,
            token_mint=token_mint,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_version=prompt_version,
        )
        return res.advisory
