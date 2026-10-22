"""Pytest test fixtures for SOLANA PREDATOR backend tests."""

import os
import sys
import tempfile
import pytest
import pytest_asyncio

# Ensure /root/solana_predator is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.database.migrations import apply_migrations
from backend.database.repository import Repository
from backend.market.normalizer import EventNormalizer, EventDeduplicator
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


@pytest.fixture
def temp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    apply_migrations(path)
    yield path
    if os.path.exists(path):
        os.remove(path)
    # Also clean wal/shm if present
    for ext in ("-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.remove(p)


@pytest.fixture
def repo(temp_db_path):
    return Repository(temp_db_path)


@pytest.fixture
def health():
    return HealthTracker()


@pytest.fixture
def deduplicator():
    return EventDeduplicator(maxsize=1000, ttl_seconds=60.0)


@pytest.fixture
def normalizer(deduplicator):
    return EventNormalizer(deduplicator)


@pytest.fixture
def event_bus():
    return EventBus(maxsize=100)


@pytest.fixture
def token_radar(repo):
    return TokenRadar(repo)


@pytest.fixture
def whale_engine(repo):
    return WhaleIntelligenceEngine(repo)


@pytest.fixture
def agent_orchestrator(repo):
    return AgentOrchestrator(repo)


@pytest.fixture
def position_manager(repo):
    return PositionManager(repo)


@pytest.fixture
def paper_accounting(repo):
    return PaperAccounting(repo, initial_capital=10000.0)


@pytest.fixture
def paper_broker(paper_accounting, position_manager, repo):
    return PaperBroker(paper_accounting, position_manager, repo)


@pytest.fixture
def exit_monitor(position_manager):
    return ExitMonitor(position_manager)


@pytest_asyncio.fixture
async def predator_engine(
    repo,
    event_bus,
    health,
    normalizer,
    token_radar,
    whale_engine,
    agent_orchestrator,
    position_manager,
    paper_accounting,
    paper_broker,
    exit_monitor,
):
    engine = PredatorEngine(
        repository=repo,
        event_bus=event_bus,
        health_tracker=health,
        normalizer=normalizer,
        token_radar=token_radar,
        whale_engine=whale_engine,
        agent_orchestrator=agent_orchestrator,
        position_manager=position_manager,
        paper_accounting=paper_accounting,
        paper_broker=paper_broker,
        exit_monitor=exit_monitor,
    )
    await engine.initialize()
    yield engine
    await engine.shutdown()
