"""Deterministic and live latency benchmarking tool for SOLANA PREDATOR."""

import sys
import os
import asyncio
import time
import json
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.models import NormalizedMarketEvent, MarketSource, EventQuality
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
from backend.market.dex_screener import DexScreenerClient


def generate_benchmark_events(count: int = 500) -> List[NormalizedMarketEvent]:
    events = []
    base_mint = "BenchMemeMint11111111111111111111111111111"
    now = time.time()
    for i in range(count):
        price = 0.00010 + (i * 0.0000005)
        liq = 20000.0 + (i * 50.0)
        vol = 5000.0 + (i * 100.0)
        
        meta = {
            "name": f"BenchToken_{i%10}",
            "symbol": f"BNCH_{i%10}",
            "pool_created_at": now - 3600.0,
            "txns_5m": {"buys": 10 + (i % 5), "sells": 2 + (i % 3)},
        }
        if i % 5 == 0:
            meta["whale_wallet"] = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
            meta["swap_type"] = "BUY"
            meta["amount_usd"] = 1500.0
            meta["amount_tokens"] = 15000000.0

        ev = NormalizedMarketEvent(
            source=MarketSource.REPLAY,
            event_id=f"bench_ev_{i:04d}",
            token_mint=f"{base_mint[:38]}_{i%10}",
            pair_address=f"PairBenchPool11111111111111111_{i%10}",
            source_timestamp=now - 1.0,
            local_receive_timestamp=now - 0.01,
            processing_timestamp=now,
            price_usd=price,
            liquidity_usd=liq,
            volume_24h_usd=vol,
            signature=f"5xSigBench_{i:06d}_11111111111111111111111111111111111111111111111111111111",
            quality=EventQuality.EXCELLENT,
            confidence_score=0.98,
            metadata=meta,
        )
        events.append(ev)
    return events


async def run_latency_benchmark(num_events: int = 500, test_name: str = "DETERMINISTIC REPLAY"):
    print("=" * 80)
    print(f"SOLANA PREDATOR — LATENCY BENCHMARK: {test_name}")
    print(f"Total Sample Count: {num_events} events")
    print("=" * 80)

    db_path = f"/tmp/bench_latency_{int(time.time()*1000)}.db"
    apply_migrations(db_path)
    repo = Repository(db_path)

    event_bus = EventBus(maxsize=10000)
    health = HealthTracker()
    normalizer = EventNormalizer()
    token_radar = TokenRadar(repo)
    whale_engine = WhaleIntelligenceEngine(repo)
    agents = AgentOrchestrator(repo)
    positions = PositionManager(repo)
    accounting = PaperAccounting(repo)
    broker = PaperBroker(accounting, positions, repo)
    exit_monitor = ExitMonitor(positions)

    # Simulated WebSocket client consumer
    broadcast_count = 0
    async def mock_ws_broadcast(payload: Dict[str, Any]):
        nonlocal broadcast_count
        broadcast_count += 1

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
    engine.set_ws_broadcast_callback(mock_ws_broadcast)
    await engine.initialize()

    dataset = generate_benchmark_events(num_events)
    start_bench_time = time.perf_counter()

    for ev in dataset:
        await engine.process_market_event(ev)

    total_bench_duration_sec = time.perf_counter() - start_bench_time
    throughput_eps = num_events / total_bench_duration_sec if total_bench_duration_sec > 0 else 0.0

    await engine.shutdown()
    if os.path.exists(db_path):
        os.remove(db_path)

    # Format Results
    summary = health.get_summary(event_bus.get_metrics(), normalizer.deduplicator.duplicate_count)
    latencies = summary["latencies_ms"]

    print(f"Benchmark Duration: {total_bench_duration_sec:.2f} seconds")
    print(f"Observed Pipeline Throughput: {throughput_eps:.2f} events/second")
    print(f"WebSocket Broadcast Messages: {broadcast_count}")
    print("-" * 80)
    print(f"{'STAGE':<24} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'p99 (ms)':<10} | {'AVG (ms)':<10}")
    print("-" * 80)

    stage_order = [
        ("Event Reception", "receive"),
        ("Normalization", "normalize"),
        ("Indicators (Whale/Radar)", "indicators"),
        ("Agent Analysis", "agent_analysis"),
        ("Risk Check", "risk_check"),
        ("Persistence (SQLite WAL)", "persistence"),
        ("Paper Fill Simulation", "paper_fill"),
        ("WebSocket Broadcast", "ws_broadcast"),
        ("End-to-End Latency", "end_to_end"),
    ]

    for label, key in stage_order:
        data = latencies.get(key, {})
        p50 = f"{data.get('p50', 0.0):.2f}"
        p95 = f"{data.get('p95', 0.0):.2f}"
        p99 = f"{data.get('p99', 0.0):.2f}"
        avg = f"{data.get('avg', 0.0):.2f}"
        print(f"{label:<24} | {p50:<10} | {p95:<10} | {p99:<10} | {avg:<10}")

    print("=" * 80)
    return {
        "test_name": test_name,
        "sample_count": num_events,
        "duration_sec": round(total_bench_duration_sec, 2),
        "throughput_eps": round(throughput_eps, 2),
        "errors": health.total_errors,
        "latencies": latencies,
    }


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    asyncio.run(run_latency_benchmark(count))
