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


# 19. SKEPTIC Contradiction of LLM Bullish Advisory
@pytest.mark.asyncio
async def test_skeptic_contradicts_llm_advisory():
    from backend.agents.skeptic import SkepticAgent
    skeptic = SkepticAgent()
    chief = ChiefAgent()

    # Event exhibiting 25 buys and 0 sells (verifiable honeypot signature)
    event = NormalizedMarketEvent(
        event_id="evt_honeypot_1",
        source=MarketSource.SOLANA_RPC,
        token_mint="TokenHoneypot11111111111111111111111111111",
        price_usd=0.05,
        liquidity_usd=10000.0,
        volume_24h_usd=25000.0,
        local_receive_timestamp=1000.0,
        processing_timestamp=1000.1,
        metadata={"txns_5m": {"buys": 25, "sells": 0}},
    )

    skeptic_res = await skeptic.evaluate(event, {})
    assert skeptic_res.decision == AgentDecision.VETO
    assert "SKEPTIC_ZERO_SELLS_HONEYPOT_RISK" in skeptic_res.reason_codes

    # Even if LLM is hyper-bullish
    bullish_llm = AgentLLMAdvisory(
        agent="CHIEF",
        token_mint=event.token_mint,
        decision=AgentDecision.BUY_CANDIDATE,
        confidence=0.99,
        evidence=["Extreme buy momentum"],
        risks=[],
        invalidation_conditions=[],
        summary="GLM Flash advises strong buy",
        strategy_version="glm5-glm-5.3-flash",
        prompt_version="v1.0-chief-synthesis",
    )

    consensus = chief.synthesize(
        event=event,
        agent_results={AgentName.SKEPTIC.value: skeptic_res},
        start_time_monotonic=0.0,
        llm_advisory=bullish_llm,
    )

    # SKEPTIC veto must override LLM bullish advice!
    assert consensus.final_decision == AgentDecision.VETO
    assert "VETOED BY SKEPTIC" in consensus.chief_reason


# 20. Active Connectivity Probe (Separate Configuration & Live Check)
@pytest.mark.asyncio
async def test_client_connectivity_probe():
    # A. Unconfigured client
    unconf_client = LLMClient(api_key="", enabled=False)
    unconf_check = await unconf_client.check_connectivity()
    assert unconf_check["connectivity_status"] == "NOT_CONFIGURED"
    assert unconf_check["available"] is False

    # B. Configured client with 200 OK
    good_resp = json.dumps({
        "id": "chatcmpl-probe",
        "object": "chat.completion",
        "created": 1234567,
        "model": "glm-5.3-flash",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "pong"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    })
    session_mock = MagicMock()
    session_mock.closed = False
    session_mock.post.return_value = MockAiohttpResponse(200, good_resp)

    client = LLMClient(api_key="sk-testkey", enabled=True, session=session_mock)
    probe_ok = await client.check_connectivity()
    assert probe_ok["connectivity_status"] == "AVAILABLE"
    assert probe_ok["available"] is True
    assert probe_ok["http_status"] == 200

    # C. Auth failure (401)
    session_mock.post.return_value = MockAiohttpResponse(401, '{"error": "Unauthorized"}')
    client_401 = LLMClient(api_key="sk-badkey", enabled=True, session=session_mock)
    probe_401 = await client_401.check_connectivity()
    assert probe_401["connectivity_status"] == "AUTHENTICATION_FAILED"
    assert probe_401["available"] is False
    assert probe_401["http_status"] == 401


# 21. API Endpoint /api/llm/analyze Statuses
@pytest.mark.asyncio
async def test_llm_analyze_endpoint_all_states():
    from backend.api.routes import trigger_llm_analysis, LLMAnalysisRequest

    # State 1: LLM_NOT_CONFIGURED
    client_disabled = LLMClient(enabled=False)
    res1 = await trigger_llm_analysis(
        LLMAnalysisRequest(token_mint="Token111111111111111111111111111111111111111"),
        llm=client_disabled,
    )
    assert res1["status"] == "LLM_NOT_CONFIGURED"

    # State 2: LLM_AUTH_FAILED (401)
    session_mock = MagicMock()
    session_mock.closed = False
    session_mock.post.return_value = MockAiohttpResponse(401, '{"error": "Invalid API key"}')
    client_auth = LLMClient(api_key="sk-invalid", enabled=True, session=session_mock)
    res2 = await trigger_llm_analysis(
        LLMAnalysisRequest(token_mint="Token111111111111111111111111111111111111111"),
        llm=client_auth,
    )
    assert res2["status"] == "LLM_AUTH_FAILED"

    # State 3: LLM_UNAVAILABLE (502)
    session_mock.post.return_value = MockAiohttpResponse(502, '{"error": "Bad Gateway"}')
    client_unavail = LLMClient(api_key="sk-valid", enabled=True, session=session_mock, max_retries=0)
    res3 = await trigger_llm_analysis(
        LLMAnalysisRequest(token_mint="Token111111111111111111111111111111111111111"),
        llm=client_unavail,
    )
    assert res3["status"] == "LLM_UNAVAILABLE"

    # State 4: LLM_INVALID_RESPONSE (Malformed JSON)
    session_mock.post.return_value = MockAiohttpResponse(200, '{"choices": [{"message": {"content": "not json"}}]')
    client_invalid = LLMClient(api_key="sk-valid", enabled=True, session=session_mock)
    res4 = await trigger_llm_analysis(
        LLMAnalysisRequest(token_mint="Token111111111111111111111111111111111111111"),
        llm=client_invalid,
    )
    assert res4["status"] == "LLM_INVALID_RESPONSE"

    # State 5: SUCCESS
    valid_advisory_json = json.dumps({
        "decision": "PASS",
        "confidence": 0.85,
        "evidence": ["Normal turnover"],
        "risks": ["Low liquidity"],
        "invalidation_conditions": ["Liquidity spike"],
        "summary": "Observation phase recommended",
    })
    valid_resp = json.dumps({
        "id": "chatcmpl-ok",
        "object": "chat.completion",
        "created": 1234567,
        "model": "glm-5.3-flash",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": valid_advisory_json}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    })
    session_mock.post.return_value = MockAiohttpResponse(200, valid_resp)
    client_ok = LLMClient(api_key="sk-valid", model="glm-5.3-flash", enabled=True, session=session_mock)
    res5 = await trigger_llm_analysis(
        LLMAnalysisRequest(token_mint="Token111111111111111111111111111111111111111"),
        llm=client_ok,
    )
    assert res5["status"] == "SUCCESS"
    assert res5["advisory"]["decision"] == AgentDecision.PASS.value
    assert res5["advisory"]["model"] == "glm-5.3-flash"
    assert res5["advisory"]["prompt_version"] == "v1.0-chief-synthesis"


# 22. Persistence of Prompt Version and Advisory in SQLite Repository
@pytest.mark.asyncio
async def test_prompt_version_and_advisory_persistence(repo):
    chief = ChiefAgent()
    event = NormalizedMarketEvent(
        event_id="evt_persist_1",
        source=MarketSource.SOLANA_RPC,
        token_mint="TokenPersist1111111111111111111111111111111",
        price_usd=0.10,
        liquidity_usd=50000.0,
        local_receive_timestamp=1000.0,
        processing_timestamp=1000.1,
    )
    advisory = AgentLLMAdvisory(
        agent="CHIEF",
        token_mint=event.token_mint,
        decision=AgentDecision.PASS,
        confidence=0.75,
        evidence=["Steady liquidity depth"],
        risks=["Macro uncertainty"],
        invalidation_conditions=["Volume breakout"],
        summary="Prudent wait-and-see",
        strategy_version="glm5-glm-5.3-flash",
        prompt_version="v1.0-chief-synthesis",
    )
    consensus = chief.synthesize(
        event=event,
        agent_results={},
        start_time_monotonic=0.0,
        llm_advisory=advisory,
    )
    assert consensus.llm_advisory is not None
    assert consensus.prompt_version == "v1.0-chief-synthesis"

    # Persist in SQLite
    await repo.save_chief_decision(consensus)

    # Read back
    decisions = await repo.get_recent_chief_decisions(limit=5)
    saved = next(d for d in decisions if d["consensus_id"] == consensus.consensus_id)
    details = json.loads(saved["details_json"])
    assert details["prompt_version"] == "v1.0-chief-synthesis"
    assert details["llm_advisory"]["model"] == "glm-5.3-flash"


# 23. Multi-Model Pool Failover and Quota Rotation
@pytest.mark.asyncio
async def test_multi_model_pool_failover_and_quota_rotation():
    model_pool = [
        "primary-free-model:free",
        "fallback-free-model-1:free",
        "fallback-free-model-2:free"
    ]

    # Simulating session where model 0 hits 429 quota exhaustion, and model 1 succeeds
    def mock_post(url, json=None, headers=None, timeout=None):
        requested_model = json.get("model") if json else ""
        if requested_model == "primary-free-model:free":
            # 429 Quota exhausted
            return MockAiohttpResponse(429, '{"error": {"code": 429, "message": "Rate limit / quota exceeded"}}')
        elif requested_model == "fallback-free-model-1:free":
            # 200 Success
            body = {
                "id": "chatcmpl-fallback-ok",
                "object": "chat.completion",
                "created": 1234567,
                "model": "fallback-free-model-1:free",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": '{"decision": "PASS", "confidence": 0.8, "summary": "Fallback model evaluated successfully"}'},
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 15, "completion_tokens": 20, "total_tokens": 35}
            }
            return MockAiohttpResponse(200, json_pkg.dumps(body))
        return MockAiohttpResponse(500, '{"error": "Server error"}')

    import json as json_pkg
    session_mock = MagicMock()
    session_mock.closed = False
    session_mock.post.side_effect = mock_post

    client = LLMClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-testkey",
        model=model_pool[0],
        model_pool=model_pool,
        session=session_mock,
        enabled=True,
    )

    req = ChatCompletionRequest(
        model=model_pool[0],
        messages=[ChatMessage(role="user", content="ping")],
    )

    resp = await client.complete(req)
    assert resp.model == "fallback-free-model-1:free"
    assert "Fallback model evaluated successfully" in resp.choices[0].message.content

    # Check that client telemetry tracked the success and the models pool
    status = client.get_status()
    assert status["configured"] is True
    assert status["model_pool"] == model_pool
    assert status["call_count"] == 1
