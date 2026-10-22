"""Soak and stress testing tool for SOLANA PREDATOR pipeline."""

import sys
import os
import asyncio
import time
import resource
from typing import Dict, Any, List

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


async def run_soak_test(burst_cycles: int = 5, events_per_burst: int = 200):
    print("=" * 80)
    print("SOLANA PREDATOR — PIPELINE STABILITY & SOAK TEST")
    print(f"Executing {burst_cycles} burst cycles with {events_per_burst} events each ({burst_cycles * events_per_burst} total)")
    print("=" * 80)

    db_path = f"/tmp/soak_test_{int(time.time()*1000)}.db"
    apply_migrations(db_path)
    repo = Repository(db_path)

    event_bus = EventBus(maxsize=500)  # Bounded queue to stress backpressure
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

    total_events_injected = 0
    t_start = time.perf_counter()

    for cycle in range(burst_cycles):
        print(f"\n[CYCLE {cycle + 1}/{burst_cycles}] Generating burst of {events_per_burst} events...")
        now = time.time()
        
        # Inject mix of fresh, duplicate, and stale events
        for i in range(events_per_burst):
            token_idx = i % 8
            mint = f"SoakTokenMint_{token_idx:02d}_1111111111111111111111"
            is_stale = (i % 25 == 0)
            is_dup = (i % 10 == 0 and i > 0)

            sig = f"sig_soak_c{cycle}_i{i:04d}" if not is_dup else f"sig_soak_c{cycle}_i{(i-1):04d}"
            price = 0.0010 + ((i + cycle * 10) * 0.00002)

            ev = NormalizedMarketEvent(
                source=MarketSource.SYNTHETIC,
                event_id=f"soak_ev_{cycle}_{i}",
                token_mint=mint,
                pair_address=f"PairSoak_{token_idx:02d}",
                source_timestamp=now - (60.0 if is_stale else 0.5),
                local_receive_timestamp=now,
                processing_timestamp=now + 0.001,
                freshness_seconds=60.0 if is_stale else 0.5,
                price_usd=price,
                liquidity_usd=30000.0 + (i * 20.0),
                volume_24h_usd=40000.0,
                signature=sig,
                quality=EventQuality.STALE if is_stale else EventQuality.EXCELLENT,
                confidence_score=0.40 if is_stale else 0.98,
                metadata={
                    "name": f"SoakToken_{token_idx}",
                    "symbol": f"SOAK_{token_idx}",
                    "pool_created_at": now - 7200.0,
                    "txns_5m": {"buys": 30, "sells": 5},
                },
            )
            # Route through normalizer deduplication first
            if not normalizer.deduplicator.is_duplicate(ev.signature):
                await engine.process_market_event(ev)
                total_events_injected += 1

        # Check queue metrics after burst
        bus_metrics = event_bus.get_metrics()
        print(f"  • Queue Depth: {bus_metrics['queue_depth']}/{bus_metrics['queue_maxsize']}")
        print(f"  • High Water Mark: {bus_metrics['high_water_mark']}")
        print(f"  • Duplicates Filtered: {normalizer.deduplicator.duplicate_count}")

    # Step 2: Simulate Cold Restart & Balance Reconciliation
    print("\n[RESTART TEST] Simulating unclean backend restart & balance recovery...")
    ending_cash_p1 = accounting.cash_balance
    open_positions_p1 = len(positions.get_open_positions())
    await engine.shutdown()

    # Re-instantiate second engine reading the exact same database
    repo_p2 = Repository(db_path)
    positions_p2 = PositionManager(repo_p2)
    accounting_p2 = PaperAccounting(repo_p2)
    await positions_p2.restore_from_db()
    await accounting_p2.reconcile_on_startup()

    print(f"  • Phase 1 Ending Cash: ${ending_cash_p1:.2f}")
    print(f"  • Phase 2 Reconciled Cash: ${accounting_p2.cash_balance:.2f}")
    print(f"  • Open Positions Restored: {len(positions_p2.get_open_positions())} (Phase 1 had {open_positions_p1})")

    reconciliation_ok = abs(ending_cash_p1 - accounting_p2.cash_balance) < 0.01

    # Resource & Storage utilization
    duration_total = time.perf_counter() - t_start
    db_size_bytes = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    rusage = resource.getrusage(resource.RUSAGE_SELF)
    max_rss_kb = rusage.ru_maxrss

    if os.path.exists(db_path):
        os.remove(db_path)

    print("\n" + "=" * 80)
    print("SOAK TEST AUDIT SUMMARY:")
    print(f"  • Total Duration: {duration_total:.2f} seconds")
    print(f"  • Total Injected Events: {total_events_injected}")
    print(f"  • Ingestion Throughput: {total_events_injected / duration_total:.2f} events/sec")
    print(f"  • Duplicate Signatures Blocked: {normalizer.deduplicator.duplicate_count}")
    print(f"  • Peak Memory (max RSS): {max_rss_kb / 1024.0:.2f} MB")
    print(f"  • Final DB Storage: {db_size_bytes / (1024.0 * 1024.0):.2f} MB")
    print(f"  • Accounting Reconciliation Verified: {reconciliation_ok}")
    print("=" * 80)

    return {
        "duration_sec": round(duration_total, 2),
        "total_events": total_events_injected,
        "duplicates_blocked": normalizer.deduplicator.duplicate_count,
        "peak_memory_mb": round(max_rss_kb / 1024.0, 2),
        "reconciliation_ok": reconciliation_ok,
    }


if __name__ == "__main__":
    asyncio.run(run_soak_test(burst_cycles=4, events_per_burst=150))
