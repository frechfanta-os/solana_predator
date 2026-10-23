"""FastAPI application entrypoint for SOLANA PREDATOR."""

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database.migrations import apply_migrations
from backend.database.repository import Repository
from backend.market.normalizer import EventNormalizer
from backend.market.event_bus import EventBus
from backend.market.health import HealthTracker
from backend.market.replay import DeterministicReplayProvider
from backend.discovery.token_radar import TokenRadar
from backend.whale.whale_intelligence import WhaleIntelligenceEngine
from backend.agents.orchestrator import AgentOrchestrator
from backend.paper.positions import PositionManager
from backend.paper.accounting import PaperAccounting
from backend.paper.broker import PaperBroker
from backend.paper.exit_monitor import ExitMonitor
from backend.pipeline.engine import PredatorEngine
from backend.api.routes import router as api_router
from backend.api.websocket_manager import WebSocketManager
import backend.api.routes as routes_module

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("predator.main")

# Global instances
ws_manager = WebSocketManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for database initialization and background engine."""
    logger.info("Initializing %s v%s...", settings.PROJECT_NAME, settings.APP_VERSION)
    logger.info("SECURITY MANDATE: %s", settings.SECURITY_NOTICE)

    # 1. Apply Database Migrations
    apply_migrations(settings.DATABASE_PATH)
    repo = Repository(settings.DATABASE_PATH)

    # 2. Instantiate Subsystems
    health = HealthTracker()
    normalizer = EventNormalizer()
    event_bus = EventBus()
    token_radar = TokenRadar(repo)
    whale_engine = WhaleIntelligenceEngine(repo)
    from backend.llm.client import LLMClient
    llm_client = LLMClient()
    agent_orchestrator = AgentOrchestrator(repo, llm_client=llm_client)
    pos_manager = PositionManager(repo)
    accounting = PaperAccounting(repo)
    broker = PaperBroker(accounting, pos_manager, repo)
    exit_monitor = ExitMonitor(pos_manager)
    replay = DeterministicReplayProvider(event_bus)

    # 3. Instantiate Learning & Live Trading Subsystems
    from backend.learning.evaluator import DecisionOutcomeEvaluator
    from backend.market.solana_rpc import SolanaRpcClient
    from backend.live.independent_risk import IndependentRiskGuard
    from backend.live.quote_service import LiveQuoteService
    from backend.live.tx_builder import UnsignedTransactionBuilder
    from backend.live.wallet import WalletService
    from backend.live.broadcast_service import LiveBroadcastService
    from backend.live.order_manager import LiveOrderManager

    evaluator = DecisionOutcomeEvaluator(repo)
    rpc_client = SolanaRpcClient(http_url=settings.SOLANA_RPC_HTTP, ws_url=settings.SOLANA_RPC_WS)
    risk_guard = IndependentRiskGuard()
    kill_switch_saved = await repo.get_system_config("emergency_kill_switch")
    if kill_switch_saved == "true":
        risk_guard.set_emergency_kill_switch(True)
        logger.warning("RESTORED PERSISTENT EMERGENCY KILL-SWITCH: LIVE TRADING HALTED")
    quote_svc = LiveQuoteService()
    tx_builder = UnsignedTransactionBuilder()
    wallet_svc = WalletService(rpc_client)
    broadcast_svc = LiveBroadcastService(rpc_client, repo)
    live_order_mgr = LiveOrderManager(repo, risk_guard, quote_svc, tx_builder, broadcast_svc, wallet_svc)

    # 4. Create Predator Engine
    engine = PredatorEngine(
        repository=repo,
        event_bus=event_bus,
        health_tracker=health,
        normalizer=normalizer,
        token_radar=token_radar,
        whale_engine=whale_engine,
        agent_orchestrator=agent_orchestrator,
        position_manager=pos_manager,
        paper_accounting=accounting,
        paper_broker=broker,
        exit_monitor=exit_monitor,
        live_order_manager=live_order_mgr,
        learning_evaluator=evaluator,
    )
    engine.set_ws_broadcast_callback(ws_manager.broadcast)
    await engine.initialize()

    # 5. Inject global references into routes module
    routes_module.engine_instance = engine
    routes_module.repository_instance = repo
    routes_module.health_instance = health
    routes_module.replay_instance = replay
    routes_module.learning_evaluator_instance = evaluator
    routes_module.live_order_manager_instance = live_order_mgr
    routes_module.wallet_service_instance = wallet_svc
    routes_module.risk_guard_instance = risk_guard
    routes_module.llm_client_instance = llm_client

    yield

    # 5. Shutdown Sequence
    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    await engine.shutdown()
    await rpc_client.close()
    await llm_client.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.APP_VERSION,
    description="Real-time Solana market intelligence terminal with coordinated analysis agents and a deterministic Paper Trading simulator.",
    lifespan=lifespan,
)

# CORS setup for Web Terminal
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount REST API
app.include_router(api_router, prefix="/api")


# WebSocket Streaming Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive receive ping
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type": "PONG"}')
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        await ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=False)
