"""Reproducible early detection audit runner for SOLANA PREDATOR."""

import sys
import os
import asyncio
import time
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.market.dex_screener import DexScreenerClient
from backend.market.solana_rpc import SolanaRpcClient
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
from backend.database.migrations import apply_migrations
from backend.database.repository import Repository


async def run_early_detection_audit():
    print("=" * 80)
    print("SOLANA PREDATOR — EARLY DETECTION AUDIT BENCHMARK")
    print("=" * 80)

    db_path = "/tmp/test_audit_early_det.db"
    apply_migrations(db_path)
    repo = Repository(db_path)

    event_bus = EventBus()
    health = HealthTracker()
    normalizer = EventNormalizer()
    token_radar = TokenRadar(repo)
    whale_engine = WhaleIntelligenceEngine(repo)
    agents = AgentOrchestrator(repo)
    positions = PositionManager(repo)
    accounting = PaperAccounting(repo)
    broker = PaperBroker(accounting, positions, repo)
    exit_monitor = ExitMonitor(positions)

    engine = PredatorEngine(
        repository=repo,
        event_bus=event_bus,
        health_tracker=health,
        normalizer=normalizer,
        token_radar=token_radar,
        whale_engine=whale_engine,
        agent_orchestrator=agents,
        position_manager=positions,
        paper_accounting=accounting,
        paper_broker=broker,
        exit_monitor=exit_monitor,
    )
    await engine.initialize()

    # Step 1: Query DEX Screener for recently promoted / newest Solana tokens
    dex = DexScreenerClient()
    audit_results: List[Dict[str, Any]] = []

    try:
        profiles = await dex.get_latest_token_profiles()
        sample_addresses = [p["tokenAddress"] for p in profiles[:6] if p.get("tokenAddress")]
        pairs = await dex.get_tokens_pairs(sample_addresses)

        print(f"Discovered {len(pairs)} Solana pairs with verifiable on-chain metadata.")
        print("-" * 80)
        print(f"{'MINT':<16} | {'POOL CREATED':<12} | {'FIRST SEEN':<12} | {'RX AT':<12} | {'DETECT AT':<12} | {'DECIDED AT':<12}")
        print("-" * 80)

        for pair in pairs:
            rx_start = time.time()
            ev = normalizer.normalize_dex_screener_pair(pair, receive_timestamp=rx_start)
            if not ev:
                continue

            detect_start = time.time()
            state = await token_radar.process_event(ev)
            detect_end = time.time()

            decide_start = time.time()
            context = {
                "portfolio_equity": accounting.cash_balance,
                "cash_balance": accounting.cash_balance,
                "open_positions_count": len(positions.get_open_positions()),
                "current_drawdown_pct": 0.0,
                "has_existing_position": False,
            }
            consensus = await agents.run_pipeline(ev, context)
            decide_end = time.time()

            pool_created_str = (
                f"{int(ev.source_timestamp)}" if ev.source_timestamp else "N/A"
            )
            rx_str = f"{rx_start:.3f}"[-7:]
            detect_str = f"{detect_end:.3f}"[-7:]
            decide_str = f"{decide_end:.3f}"[-7:]

            audit_entry = {
                "mint": ev.token_mint,
                "symbol": pair.get("baseToken", {}).get("symbol", "N/A"),
                "pool_created_timestamp": ev.source_timestamp,
                "first_observed_timestamp": rx_start,
                "engine_receive_timestamp": rx_start,
                "token_detection_timestamp": detect_end,
                "final_decision_timestamp": decide_end,
                "detection_latency_ms": round((detect_end - rx_start) * 1000.0, 3),
                "decision_latency_ms": round((decide_end - detect_end) * 1000.0, 3),
                "decision": consensus.final_decision.value,
                "chief_reason": consensus.chief_reason,
            }
            audit_results.append(audit_entry)

            print(
                f"{ev.token_mint[:14]}.. | {pool_created_str:<12} | {rx_str:<12} | {rx_str:<12} | {detect_str:<12} | {decide_str:<12} | {consensus.final_decision.value}"
            )

    finally:
        await dex.close()
        await engine.shutdown()
        if os.path.exists(db_path):
            os.remove(db_path)

    print("=" * 80)
    print("EARLY DETECTION AUDIT SUMMARY:")
    for res in audit_results:
        pool_lead = (
            f"{(res['first_observed_timestamp'] - res['pool_created_timestamp']):.1f}s after pool creation"
            if res["pool_created_timestamp"]
            else "Unknown pool age"
        )
        print(f"Token: {res['symbol']} ({res['mint'][:12]}...)")
        print(f"  • Pool Creation: {res['pool_created_timestamp']}")
        print(f"  • Observation Delay: {pool_lead}")
        print(f"  • Engine Detection Latency: {res['detection_latency_ms']:.2f} ms")
        print(f"  • Full Decision Latency: {res['decision_latency_ms']:.2f} ms")
        print(f"  • Decision: {res['decision']} ({res['chief_reason']})")
    print("=" * 80)
    return audit_results


if __name__ == "__main__":
    asyncio.run(run_early_detection_audit())
