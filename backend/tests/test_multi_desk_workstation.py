"""Comprehensive tests for Multi-Desk Intelligence Workstation (Phases B, C, D)."""

import time
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.config import settings
from backend.database.repository import Repository
from backend.market.normalizer import EventNormalizer
from backend.market.event_bus import EventBus
from backend.market.health import HealthTracker
from backend.discovery.token_radar import TokenRadar
from backend.whale.whale_intelligence import WhaleIntelligenceEngine
from backend.agents.orchestrator import AgentOrchestrator
from backend.paper.positions import PositionManager
from backend.paper.accounting import PaperAccounting
from backend.paper.broker import PaperBroker
from backend.paper.exit_monitor import ExitMonitor
from backend.pipeline.engine import PredatorEngine
from backend.desks.coordinator import MultiDeskCoordinator
from backend.models import (
    NormalizedMarketEvent,
    MarketSource,
    EventQuality,
    DeskId,
    ExecutionState,
)


def _make_sample_event(
    event_id: str = "ev_desk_test_1",
    token_mint: str = "So11111111111111111111111111111111111111112",
    price_usd: float = 152.5,
    liquidity_usd: float = 85000.0,
    volume_24h_usd: float = 240000.0,
) -> NormalizedMarketEvent:
    now = time.time()
    return NormalizedMarketEvent(
        event_id=event_id,
        source=MarketSource.DEX_SCREENER,
        token_mint=token_mint,
        source_timestamp=now - 2.0,
        local_receive_timestamp=now,
        processing_timestamp=now,
        freshness_seconds=2.0,
        price_usd=price_usd,
        liquidity_usd=liquidity_usd,
        volume_24h_usd=volume_24h_usd,
        quality=EventQuality.EXCELLENT,
        observation_state="GENUINELY_OBSERVED",
        missing_fields=[],
        confidence_score=0.95,
        metadata={"symbol": "SOL", "txns_5m": {"buys": 12, "sells": 5}},
    )


@pytest.mark.asyncio
async def test_six_desks_registered_and_persisted(temp_db_path):
    repo = Repository(temp_db_path)
    orch = AgentOrchestrator(repo)
    radar = TokenRadar(repo)
    whale = WhaleIntelligenceEngine(repo)
    coord = MultiDeskCoordinator(repo, orch, radar, whale)
    await coord.initialize()

    try:
        desks = await repo.get_all_desks()
        assert len(desks) == 6
        supervisors = {d["desk_id"]: d["supervisor"] for d in desks}
        assert supervisors == {
            "DESK_MARKET": "MarketSupervisor",
            "DESK_WHALE": "WhaleSupervisor",
            "DESK_INVESTIGATION": "InvestigationSupervisor",
            "DESK_QUANT": "QuantSupervisor",
            "DESK_RISK": "RiskSupervisor",
            "DESK_COMMAND": "CHIEF",
        }
        # All agents start in IDLE state, not fake RUNNING
        for ag_state in coord.agent_states.values():
            assert ag_state["status"] == ExecutionState.IDLE.value
    finally:
        await coord.shutdown()
        await orch.llm_client.close()


@pytest.mark.asyncio
async def test_real_agent_execution_and_structured_reports(temp_db_path):
    repo = Repository(temp_db_path)
    health = HealthTracker()
    norm = EventNormalizer()
    bus = EventBus()
    radar = TokenRadar(repo)
    whale = WhaleIntelligenceEngine(repo)
    orch = AgentOrchestrator(repo)
    pos = PositionManager(repo)
    acc = PaperAccounting(repo)
    broker = PaperBroker(acc, pos, repo)
    exit_mon = ExitMonitor(pos)
    coord = MultiDeskCoordinator(repo, orch, radar, whale)

    ws_messages = []

    async def _capture_ws(msg):
        ws_messages.append(msg)

    engine = PredatorEngine(
        repository=repo,
        event_bus=bus,
        health_tracker=health,
        normalizer=norm,
        token_radar=radar,
        whale_engine=whale,
        agent_orchestrator=orch,
        position_manager=pos,
        paper_accounting=acc,
        paper_broker=broker,
        exit_monitor=exit_mon,
        desk_coordinator=coord,
    )
    engine.set_ws_broadcast_callback(_capture_ws)
    await engine.initialize()

    try:
        ev = _make_sample_event()
        await engine.process_market_event(ev)

        tasks = await repo.get_desk_tasks(limit=50)
        reports = await repo.get_desk_reports(limit=50)
        assert len(tasks) >= 6
        assert len(reports) >= 6

        # Verify structured report separates observed facts, inferences, and missing fields
        cmd_reports = [r for r in reports if r["desk_id"] == "DESK_COMMAND"]
        assert len(cmd_reports) == 1
        assert len(cmd_reports[0]["observed_facts"]) >= 2
        assert len(cmd_reports[0]["inferred_conclusions"]) >= 1
        assert cmd_reports[0]["source"] == "DEX_SCREENER"

        # Verify WebSocket envelopes emitted
        event_types = {m.get("event_type") for m in ws_messages if "event_type" in m}
        assert "market.observation" in event_types
        assert "agent.task.completed" in event_types
        assert "agent.report.created" in event_types
        assert "desk.status" in event_types
        assert "chief.summary" in event_types
        assert "paper.position.updated" in event_types
    finally:
        await engine.shutdown()
        await orch.llm_client.close()


@pytest.mark.asyncio
async def test_desk_pause_resume_and_restart_recovery(temp_db_path):
    repo = Repository(temp_db_path)
    orch = AgentOrchestrator(repo)
    radar = TokenRadar(repo)
    whale = WhaleIntelligenceEngine(repo)
    coord = MultiDeskCoordinator(repo, orch, radar, whale)
    await coord.initialize()

    try:
        paused_rec = await coord.pause_desk(DeskId.DESK_MARKET.value)
        assert paused_rec.is_paused is True
        assert paused_rec.status == ExecutionState.PAUSED

        ev = _make_sample_event("ev_pause_test")
        res = await coord.run_desk_now(DeskId.DESK_MARKET.value, ev)
        assert res["status"] == ExecutionState.PAUSED.value
        assert coord.desks[DeskId.DESK_MARKET.value].skipped_tasks == 1
    finally:
        await coord.shutdown()
        await orch.llm_client.close()

    # Simulate restart with fresh coordinator against same SQLite DB
    coord2 = MultiDeskCoordinator(repo, orch, radar, whale)
    await coord2.initialize()
    try:
        assert coord2.desks[DeskId.DESK_MARKET.value].is_paused is True
        assert coord2.desks[DeskId.DESK_MARKET.value].status == ExecutionState.PAUSED
        resumed = await coord2.resume_desk(DeskId.DESK_MARKET.value)
        assert resumed.is_paused is False
        assert resumed.status == ExecutionState.IDLE
    finally:
        await coord2.shutdown()


@pytest.mark.asyncio
async def test_scheduler_deduplication_and_authoritative_risk_veto(temp_db_path):
    repo = Repository(temp_db_path)
    orch = AgentOrchestrator(repo)
    radar = TokenRadar(repo)
    whale = WhaleIntelligenceEngine(repo)
    coord = MultiDeskCoordinator(repo, orch, radar, whale, dedup_window_sec=10.0)
    await coord.initialize()

    try:
        ev = _make_sample_event("ev_dedup_1")
        r1 = await coord.enqueue_desk_task(DeskId.DESK_QUANT.value, ev)
        assert r1["status"] == ExecutionState.QUEUED.value

        # Immediate duplicate must be skipped
        r2 = await coord.enqueue_desk_task(DeskId.DESK_QUANT.value, ev)
        assert r2["status"] == ExecutionState.SKIPPED.value

        # Trigger authoritative RISK VETO via drawdown breach
        veto_context = {
            "open_positions_count": 0,
            "current_drawdown_pct": 0.50,  # Exceeds 15% max drawdown limit
            "has_existing_position": False,
            "cash_balance": 10000.0,
        }
        consensus = await orch.run_pipeline(ev, veto_context)
        assert consensus.is_risk_vetoed is True
        assert consensus.final_decision.value == "VETO"

        reports = await coord.record_pipeline_execution(ev, consensus, veto_context)
        risk_rep = next(r for r in reports if r.agent_id == "RISK")
        chief_rep = next(r for r in reports if r.agent_id == "CHIEF")
        assert risk_rep.is_veto is True
        assert chief_rep.is_veto is True
        assert chief_rep.decision == "VETO"
    finally:
        await coord.shutdown()
        await orch.llm_client.close()


def test_desks_and_system_health_rest_endpoints(temp_db_path, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_PATH", temp_db_path)
    admin_headers = {"X-Admin-Key": settings.ADMIN_API_KEY}

    with TestClient(app) as client:
        # 1. List 6 desks
        r_desks = client.get("/api/desks")
        assert r_desks.status_code == 200
        desks = r_desks.json()
        assert len(desks) == 6

        # 2. Single desk workspace snapshot
        r_m = client.get("/api/desks/DESK_MARKET")
        assert r_m.status_code == 200
        assert r_m.json()["desk"]["supervisor"] == "MarketSupervisor"

        # 3. On-demand desk run
        r_run = client.post(
            "/api/desks/DESK_MARKET/run",
            json={"token_mint": "So11111111111111111111111111111111111111112", "price_usd": 155.0},
        )
        assert r_run.status_code == 200
        assert len(r_run.json()["tasks"]) == 1
        assert len(r_run.json()["reports"]) == 1

        # 4. Pause & resume desk (requires admin auth)
        unauth = client.post("/api/desks/DESK_MARKET/pause")
        assert unauth.status_code in (401, 403)
        r_pause = client.post("/api/desks/DESK_MARKET/pause", headers=admin_headers)
        assert r_pause.status_code == 200
        assert r_pause.json()["is_paused"] is True
        r_res = client.post("/api/desks/DESK_MARKET/resume", headers=admin_headers)
        assert r_res.status_code == 200
        assert r_res.json()["is_paused"] is False

        # 5. Agents & Watchlist
        r_ag = client.get("/api/agents")
        assert r_ag.status_code == 200
        assert len(r_ag.json()) == 9

        r_wl = client.get("/api/watchlist")
        assert r_wl.status_code == 200
        assert len(r_wl.json()) >= 2

        # 6. Comprehensive System Health
        r_sys = client.get("/api/system/health")
        assert r_sys.status_code == 200
        sys_data = r_sys.json()
        assert sys_data["execution_mode"] == "PAPER_TRADING_ONLY"
        assert sys_data["allow_transaction_submission"] is False
        assert len(sys_data["desks"]) == 6

        # 7. WebSocket /ws/live alias
        with client.websocket_connect("/ws/live") as ws:
            ws.send_text("ping")
            reply = ws.receive_json()
            assert reply["type"] == "PONG"
