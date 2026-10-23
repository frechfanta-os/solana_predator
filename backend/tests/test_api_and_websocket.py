"""Tests for FastAPI HTTP routes, authentication, and WebSockets."""

import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.config import settings


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_api_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert data["project"] == "SOLANA PREDATOR"
    assert "LIVE MARKET DATA — PAPER TRADING ONLY" in data["security_notice"]


def test_api_state_endpoint(client):
    resp = client.get("/api/state")
    assert resp.status_code == 200
    data = resp.json()
    assert "cash_balance_usd" in data
    assert "security_notice" in data


def test_admin_auth_required_for_mutations(client):
    # Unauthenticated attempt should fail with 401
    resp_unauth = client.post("/api/simulation/start_replay")
    assert resp_unauth.status_code == 401

    # Authenticated attempt with X-Admin-Key header should succeed
    headers = {"X-Admin-Key": settings.ADMIN_API_KEY}
    resp_auth = client.post("/api/simulation/start_replay", headers=headers)
    assert resp_auth.status_code == 200
    data = resp_auth.json()
    assert data["status"] == "COMPLETED"
    assert data["events_replayed"] > 0


def test_websocket_connection_and_ping(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_text("ping")
        data = ws.receive_text()
        assert "PONG" in data


def test_llm_status_route(client):
    resp = client.get("/api/llm/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "model" in data
    assert data["model"] == settings.LLM_MODEL
    assert "api_key_configured" in data
    # Ensure raw secret is not leaked in status response
    assert settings.LLM_API_KEY not in json.dumps(data) if settings.LLM_API_KEY else True


def test_llm_analyze_fallback_when_disabled(client):
    # When LLM is queried via API, route returns explicit contract status
    resp = client.post("/api/llm/analyze", json={
        "token_mint": "TokenMintTest11111111111111111111111111111",
        "agent_role": "CHIEF",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in (
        "LLM_NOT_CONFIGURED",
        "LLM_FALLBACK",
        "SUCCESS",
        "LLM_UNAVAILABLE",
        "LLM_INVALID_RESPONSE",
        "LLM_AUTH_FAILED",
    )
