"""
Unit tests for SOLANA PREDATOR LLM GLM-5.3-Flash integration.
Validates OpenAI-compatible completions, URL construction, secret masking,
error hierarchy, retry/backoff, concurrency bounding, fallback degraded mode,
RISK veto inviolability, and execution safety.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.llm.client import LLMClient
from backend.llm.models import (
    ChatMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    AgentLLMAdvisory,
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
from backend.models import (
    NormalizedMarketEvent,
    MarketSource,
    AgentDecision,
    AgentName,
)
from backend.agents.chief import ChiefAgent
from backend.agents.orchestrator import AgentOrchestrator
from backend.live.broadcast_service import LiveBroadcastService


class MockAiohttpResponse:
    """Mock aiohttp response context manager for unit testing."""
    def __init__(self, status: int, text_data: str):
        self.status = status
        self._text_data = text_data

    async def text(self) -> str:
        return self._text_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def dummy_request():
    return ChatCompletionRequest(
        model="glm-5.3-flash",
        messages=[
            ChatMessage(role="system", content="You are a market analyst."),
            ChatMessage(role="user", content="Analyze SOL volatility."),
        ],
        temperature=0.2,
        max_tokens=256,
    )


@pytest.fixture
def mock_rpc():
    from backend.market.solana_rpc import SolanaRpcClient
    return SolanaRpcClient()


# 1. URL Construction Test
def test_url_construction():
    client = LLMClient(
        base_url="https://preview-chat-5b88a64e-2cfd-4430-8a11-8a8190f3f6b2.space-z.ai/api/provider/v1",
        api_key="sk-testkey12345",
        model="glm-5.3-flash",
    )
    expected = "https://preview-chat-5b88a64e-2cfd-4430-8a11-8a8190f3f6b2.space-z.ai/api/provider/v1/chat/completions"
    assert client.get_endpoint_url() == expected


# 2. Selected Model Test
def test_selected_model_in_client():
    client = LLMClient(model="glm-5.3-flash")
    assert client.model == "glm-5.3-flash"

    custom_client = LLMClient(model="custom-flash-model")
    assert custom_client.model == "custom-flash-model"


# 3. Authentication & Header Secret Masking Test
def test_authentication_without_exposing_key():
    raw_key = "sk-dummy-mock-secret-key-for-test-999"
    client = LLMClient(
        base_url="https://api.space-z.ai/v1",
        api_key=raw_key,
        auth_header_style="both",
    )
    headers = client.get_request_headers()
    assert headers["Authorization"] == f"Bearer {raw_key}"
    assert headers["X-Api-Key"] == raw_key

    # Test masking
    masked = client.mask_headers(headers)
    assert raw_key not in masked["Authorization"]
    assert raw_key not in masked["X-Api-Key"]
    assert masked["Authorization"].startswith("Bearer")
    assert masked["X-Api-Key"].startswith("sk-dum...")


# 4. Message Formatting Test
def test_message_formatting(dummy_request):
    payload = dummy_request.model_dump(exclude_none=True)
    assert payload["model"] == "glm-5.3-flash"
    assert len(payload["messages"]) == 2
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][0]["content"] == "You are a market analyst."
    assert payload["messages"][1]["role"] == "user"
    assert payload["messages"][1]["content"] == "Analyze SOL volatility."
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 256


# 5. Valid Response Parsing Test
@pytest.mark.asyncio
async def test_valid_chat_completion_response(dummy_request):
    mock_resp_json = {
        "id": "chatcmpl-test-01",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "glm-5.3-flash",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Solana volatility is consolidating near support.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 15,
            "completion_tokens": 8,
            "total_tokens": 23,
        },
    }

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.return_value = MockAiohttpResponse(200, json.dumps(mock_resp_json))

    client = LLMClient(
        base_url="https://api.space-z.ai/v1",
        api_key="sk-test",
        session=mock_session,
    )

    resp = await client.complete(dummy_request)
    assert isinstance(resp, ChatCompletionResponse)
    assert resp.id == "chatcmpl-test-01"
    assert resp.model == "glm-5.3-flash"
    assert len(resp.choices) == 1
    assert resp.choices[0].message.content == "Solana volatility is consolidating near support."
    assert resp.usage.total_tokens == 23
    assert resp.latency_ms >= 0.0
    assert client.call_count == 1
    assert client.error_count == 0


# 6. Empty Response Body Test
@pytest.mark.asyncio
async def test_empty_response_raises_format_error(dummy_request):
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.return_value = MockAiohttpResponse(200, "   ")

    client = LLMClient(
        base_url="https://api.space-z.ai/v1",
        api_key="sk-test",
        session=mock_session,
        max_retries=0,
    )

    with pytest.raises(LLMResponseFormatError, match="empty response"):
        await client.complete(dummy_request)
    assert client.error_count == 1


# 7. Invalid Non-JSON Response Test
@pytest.mark.asyncio
async def test_invalid_json_raises_format_error(dummy_request):
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.return_value = MockAiohttpResponse(200, "<html><body>Gateway 502 Bad Gateway</body></html>")

    client = LLMClient(
        base_url="https://api.space-z.ai/v1",
        api_key="sk-test",
        session=mock_session,
        max_retries=0,
    )

    with pytest.raises(LLMResponseFormatError, match="Malformed JSON"):
        await client.complete(dummy_request)


# 8. Authentication Error Test (HTTP 401 - Never Retried)
@pytest.mark.asyncio
async def test_authentication_error_no_retries(dummy_request):
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.return_value = MockAiohttpResponse(401, '{"error": {"message": "Invalid API key"}}')

    client = LLMClient(
        base_url="https://api.space-z.ai/v1",
        api_key="sk-invalid",
        session=mock_session,
        max_retries=3,  # Must not retry even if max_retries > 0
    )

    with pytest.raises(LLMAuthenticationError) as exc_info:
        await client.complete(dummy_request)
    assert exc_info.value.status_code == 401
    assert mock_session.post.call_count == 1  # Verified exactly 1 call without wasteful retries


# 9. Rate Limit (HTTP 429) With Retry Backoff Test
@pytest.mark.asyncio
async def test_rate_limit_retry_backoff(dummy_request):
    mock_session = MagicMock()
    mock_session.closed = False
    
    # 429 on first try, then 200 on retry
    valid_resp = {
        "id": "c1",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Recovered"}}],
    }
    mock_session.post.side_effect = [
        MockAiohttpResponse(429, '{"error": "rate limited"}'),
        MockAiohttpResponse(200, json.dumps(valid_resp)),
    ]

    client = LLMClient(
        base_url="https://api.space-z.ai/v1",
        api_key="sk-test",
        session=mock_session,
        max_retries=2,
    )

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        resp = await client.complete(dummy_request)
        assert resp.choices[0].message.content == "Recovered"
        assert mock_session.post.call_count == 2
        mock_sleep.assert_called_once()


# 10. Server Error (HTTP 500) With Retry Test
@pytest.mark.asyncio
async def test_server_error_retry(dummy_request):
    mock_session = MagicMock()
    mock_session.closed = False
    valid_resp = {
        "id": "c2",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Server recovered"}}],
    }
    mock_session.post.side_effect = [
        MockAiohttpResponse(503, '{"error": "service unavailable"}'),
        MockAiohttpResponse(200, json.dumps(valid_resp)),
    ]

    client = LLMClient(
        base_url="https://api.space-z.ai/v1",
        api_key="sk-test",
        session=mock_session,
        max_retries=2,
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        resp = await client.complete(dummy_request)
        assert resp.choices[0].message.content == "Server recovered"
        assert mock_session.post.call_count == 2


# 11. Timeout Handling Test
@pytest.mark.asyncio
async def test_timeout_raises_llm_timeout_error(dummy_request):
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.side_effect = asyncio.TimeoutError()

    client = LLMClient(
        base_url="https://api.space-z.ai/v1",
        api_key="sk-test",
        session=mock_session,
        timeout_seconds=0.1,
        max_retries=1,
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(LLMTimeoutError):
            await client.complete(dummy_request)


# 12. Task Cancellation Test
@pytest.mark.asyncio
async def test_task_cancellation_propagates(dummy_request):
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.side_effect = asyncio.CancelledError()

    client = LLMClient(
        base_url="https://api.space-z.ai/v1",
        api_key="sk-test",
        session=mock_session,
    )

    with pytest.raises(asyncio.CancelledError):
        await client.complete(dummy_request)


# 13. Concurrency Limiting Test
@pytest.mark.asyncio
async def test_concurrency_bounding():
    max_concurrent = 2
    client = LLMClient(
        base_url="https://api.space-z.ai/v1",
        api_key="sk-test",
        max_concurrency=max_concurrent,
    )
    assert client._semaphore._value == max_concurrent


# 14. Fallback / Degraded Mode Test
@pytest.mark.asyncio
async def test_fallback_when_llm_disabled_or_failing():
    # 1. Disabled client returns None immediately
    disabled_client = LLMClient(enabled=False)
    advisory = await disabled_client.query_structured_advisory(
        agent_name="CHIEF",
        token_mint="MintTest11111111111111111111111111111111111",
        system_prompt="Analyze",
        user_prompt="Event data",
    )
    assert advisory is None

    # 2. Failing client returns None gracefully without crashing caller
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.side_effect = Exception("Network down")
    failing_client = LLMClient(
        enabled=True,
        api_key="sk-test",
        session=mock_session,
        max_retries=0,
    )
    advisory2 = await failing_client.query_structured_advisory(
        agent_name="CHIEF",
        token_mint="MintTest11111111111111111111111111111111111",
        system_prompt="Analyze",
        user_prompt="Event data",
    )
    assert advisory2 is None


# 15. Structured Output Parsing Test
@pytest.mark.asyncio
async def test_structured_advisory_parsing():
    structured_json = json.dumps({
        "decision": "BUY_CANDIDATE",
        "confidence": 0.88,
        "evidence": ["Volume surge +200%", "Consistent whale buyer detected"],
        "risks": ["Liquidity ratio tight"],
        "invalidation_conditions": ["Price dips below $1.15"],
        "summary": "High momentum breakout setup confirmed.",
    })
    wrapped_content = f"```json\n{structured_json}\n```"

    mock_resp = {
        "id": "c-struct-01",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": wrapped_content}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.return_value = MockAiohttpResponse(200, json.dumps(mock_resp))

    client = LLMClient(
        enabled=True,
        api_key="sk-test",
        session=mock_session,
    )

    advisory = await client.query_structured_advisory(
        agent_name="SCAN",
        token_mint="TokenMintTest11111111111111111111111111111",
        system_prompt="Test",
        user_prompt="Test",
    )
    assert advisory is not None
    assert isinstance(advisory, AgentLLMAdvisory)
    assert advisory.agent == "SCAN"
    assert advisory.decision == AgentDecision.BUY_CANDIDATE
    assert advisory.confidence == 0.88
    assert len(advisory.evidence) == 2
    assert advisory.raw_tokens_used == 150


# 16. Preservation of RISK Veto Regardless of LLM Advisory
@pytest.mark.asyncio
async def test_llm_cannot_override_risk_veto(repo):
    chief = ChiefAgent()
    
    # Simulate bullish LLM advisory
    bullish_llm = AgentLLMAdvisory(
        agent="CHIEF",
        token_mint="TokenMintVetoPreserve111111111111111111111",
        decision=AgentDecision.BUY_CANDIDATE,
        confidence=0.99,
        evidence=["Bullish breakout"],
        risks=[],
        invalidation_conditions=[],
        summary="Extremely bullish proposal from LLM",
    )

    event = NormalizedMarketEvent(
        source=MarketSource.SOLANA_RPC,
        event_id="ev_veto_preserve",
        token_mint="TokenMintVetoPreserve111111111111111111111",
        price_usd=1.0,
        liquidity_usd=50000.0,
        volume_24h_usd=100000.0,
        local_receive_timestamp=1000.0,
        processing_timestamp=1000.1,
    )

    # RISK agent emits hard VETO
    from backend.models.agent import AgentResult
    risk_veto_result = AgentResult(
        agent_name=AgentName.RISK,
        input_event_identifiers=["ev_veto_preserve"],
        timestamp=1000.0,
        decision=AgentDecision.VETO,
        reason_codes=["PORTFOLIO_DRAWDOWN_EXCEEDED_15%"],
        confidence=1.0,
        confidence_interpretation="Deterministic risk bounds breached",
        data_quality="GOOD",
        processing_latency_ms=0.01,
    )

    agent_results = {AgentName.RISK.value: risk_veto_result}

    consensus = chief.synthesize(
        event=event,
        agent_results=agent_results,
        start_time_monotonic=0.0,
        llm_advisory=bullish_llm,
    )

    # RISK Veto must remain absolute and inviolable!
    assert consensus.final_decision == AgentDecision.VETO
    assert consensus.strategic_decision == AgentDecision.VETO
    assert consensus.is_risk_vetoed is True
    assert "VETOED BY RISK" in consensus.chief_reason


# 17. Impossibility for LLM to Sign or Broadcast Transactions
@pytest.mark.asyncio
async def test_llm_cannot_sign_or_broadcast(mock_rpc, repo):
    broadcast_svc = LiveBroadcastService(rpc_client=mock_rpc, repository=repo)

    # LLM advisory cannot masquerade as user signature
    fake_llm_text = "BUY_APPROVED_BY_GLM_FLASH_MODEL"
    
    with pytest.raises(Exception):
        await broadcast_svc.broadcast_signed_transaction(
            proposal_id="prop_llm_drain_attempt",
            signed_tx_base64=fake_llm_text,
            wallet_address="5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
            token_mint="TokenMintTest11111111111111111111111111111",
            side="BUY",
            amount_sol=0.5,
            amount_tokens=100.0,
        )


# 18. Status Reporting Without Leaking API Key
def test_client_status_telemetry():
    client = LLMClient(
        base_url="https://preview-chat-5b88a64e-2cfd-4430-8a11-8a8190f3f6b2.space-z.ai/api/provider/v1",
        api_key="sk-secret-key-do-not-leak",
        model="glm-5.3-flash",
        enabled=True,
    )
    status = client.get_status()
    assert status["enabled"] is True
    assert status["configured"] is True
    assert status["model"] == "glm-5.3-flash"
    assert status["api_key_configured"] is True
    assert "sk-secret-key-do-not-leak" not in str(status)  # Key is never exposed in telemetry
