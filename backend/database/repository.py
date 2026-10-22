"""Repository handling thread-safe SQLite operations for SOLANA PREDATOR."""

import sqlite3
import json
import time
import asyncio
import logging
from typing import List, Optional, Dict, Any
from backend.models import (
    NormalizedMarketEvent,
    TokenMetadata,
    TokenLifecycleRecord,
    TokenSnapshot,
    WhaleActivity,
    AgentResult,
    ChiefConsensusRecord,
    PaperOrder,
    PaperFill,
    PaperPosition,
    PortfolioSnapshot,
)

logger = logging.getLogger("predator.database.repository")


class Repository:
    """Thread-safe SQLite repository supporting transactions and async execution."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = asyncio.Lock()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # --- Market Events ---

    async def save_market_event(self, event: NormalizedMarketEvent) -> bool:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT OR IGNORE INTO market_events (
                                event_id, source, token_mint, pair_address, slot,
                                source_timestamp, local_receive_timestamp, processing_timestamp,
                                freshness_seconds, price_usd, volume_24h_usd, liquidity_usd,
                                signature, raw_payload_hash, quality, confidence_score, metadata_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            event.event_id,
                            event.source.value,
                            event.token_mint,
                            event.pair_address,
                            event.slot,
                            event.source_timestamp,
                            event.local_receive_timestamp,
                            event.processing_timestamp,
                            event.freshness_seconds,
                            event.price_usd,
                            event.volume_24h_usd,
                            event.liquidity_usd,
                            event.signature,
                            event.raw_payload_hash,
                            event.quality.value,
                            event.confidence_score,
                            json.dumps(event.metadata),
                        ))
                    return True
                except Exception as e:
                    logger.error("Failed to insert market event %s: %s", event.event_id, e)
                    return False
                finally:
                    conn.close()

            return await asyncio.to_thread(_op)

    async def get_recent_market_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        def _op():
            conn = self._get_connection()
            try:
                cursor = conn.execute("""
                    SELECT * FROM market_events 
                    ORDER BY local_receive_timestamp DESC 
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    item = dict(row)
                    if item.get("metadata_json"):
                        item["metadata"] = json.loads(item["metadata_json"])
                    result.append(item)
                return result
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

    # --- Token Registry & Lifecycle ---

    async def upsert_token(self, token: TokenMetadata, initial_state: str = "DISCOVERED") -> bool:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT INTO token_registry (
                                mint, name, symbol, decimals, first_observed_timestamp,
                                pool_created_timestamp, pair_address, dex_id, initial_liquidity_usd,
                                current_lifecycle_state
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(mint) DO UPDATE SET
                                name = COALESCE(excluded.name, token_registry.name),
                                symbol = COALESCE(excluded.symbol, token_registry.symbol),
                                pair_address = COALESCE(excluded.pair_address, token_registry.pair_address),
                                dex_id = COALESCE(excluded.dex_id, token_registry.dex_id),
                                initial_liquidity_usd = COALESCE(excluded.initial_liquidity_usd, token_registry.initial_liquidity_usd)
                        """, (
                            token.mint,
                            token.name,
                            token.symbol,
                            token.decimals,
                            token.first_observed_timestamp,
                            token.pool_created_timestamp,
                            token.pair_address,
                            token.dex_id,
                            token.initial_liquidity_usd,
                            initial_state,
                        ))
                    return True
                finally:
                    conn.close()

            return await asyncio.to_thread(_op)

    async def update_token_lifecycle(self, mint: str, new_state: str, reason: str) -> bool:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                now = time.time()
                try:
                    with conn:
                        # Fetch old state
                        cursor = conn.execute("SELECT current_lifecycle_state FROM token_registry WHERE mint = ?", (mint,))
                        row = cursor.fetchone()
                        old_state = row[0] if row else None

                        conn.execute("""
                            UPDATE token_registry 
                            SET current_lifecycle_state = ?
                            WHERE mint = ?
                        """, (new_state, mint))

                        conn.execute("""
                            INSERT INTO token_lifecycle_records (
                                token_mint, from_state, to_state, transition_timestamp, reason
                            ) VALUES (?, ?, ?, ?, ?)
                        """, (mint, old_state, new_state, now, reason))
                    return True
                finally:
                    conn.close()

            return await asyncio.to_thread(_op)

    async def get_all_tokens(self) -> List[Dict[str, Any]]:
        def _op():
            conn = self._get_connection()
            try:
                cursor = conn.execute("SELECT * FROM token_registry ORDER BY first_observed_timestamp DESC")
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

    # --- Token Snapshots ---

    async def save_token_snapshot(self, snapshot: TokenSnapshot) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO token_snapshots (
                                snapshot_id, token_mint, timestamp, price_usd, volume_24h_usd,
                                liquidity_usd, fdv_usd, buys_5m, sells_5m, lifecycle_state,
                                lifecycle_reason, is_stale
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            snapshot.snapshot_id,
                            snapshot.token_mint,
                            snapshot.timestamp,
                            snapshot.price_usd,
                            snapshot.volume_24h_usd,
                            snapshot.liquidity_usd,
                            snapshot.fdv_usd,
                            snapshot.buys_5m,
                            snapshot.sells_5m,
                            snapshot.lifecycle_state.value,
                            snapshot.lifecycle_reason,
                            1 if snapshot.is_stale else 0,
                        ))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    # --- Whale Activities ---

    async def save_whale_activity(self, activity: WhaleActivity) -> bool:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT OR IGNORE INTO whale_activities (
                                activity_id, signature, wallet_address, token_mint, activity_type,
                                amount_tokens, amount_usd, timestamp, slot, confidence, evidence_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            activity.activity_id,
                            activity.signature,
                            activity.wallet_address,
                            activity.token_mint,
                            activity.activity_type.value,
                            activity.amount_tokens,
                            activity.amount_usd,
                            activity.timestamp,
                            activity.slot,
                            activity.confidence,
                            json.dumps(activity.evidence_details),
                        ))
                    return True
                except sqlite3.IntegrityError:
                    return False
                finally:
                    conn.close()

            return await asyncio.to_thread(_op)

    async def get_whale_activities(self, limit: int = 50, mint: Optional[str] = None) -> List[Dict[str, Any]]:
        def _op():
            conn = self._get_connection()
            try:
                if mint:
                    cursor = conn.execute("""
                        SELECT * FROM whale_activities WHERE token_mint = ?
                        ORDER BY timestamp DESC LIMIT ?
                    """, (mint, limit))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM whale_activities ORDER BY timestamp DESC LIMIT ?
                    """, (limit,))
                rows = cursor.fetchall()
                out = []
                for r in rows:
                    item = dict(r)
                    if item.get("evidence_json"):
                        item["evidence_details"] = json.loads(item["evidence_json"])
                    out.append(item)
                return out
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

    # --- Agent Decisions ---

    async def save_agent_decision(self, consensus_id: str, token_mint: str, result: AgentResult) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT INTO agent_decisions (
                                consensus_id, token_mint, timestamp, agent_name, decision,
                                score, confidence, latency_ms, reason_codes_json, result_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            consensus_id,
                            token_mint,
                            result.timestamp,
                            result.agent_name.value,
                            result.decision.value,
                            result.score,
                            result.confidence,
                            result.processing_latency_ms,
                            json.dumps(result.reason_codes),
                            json.dumps(result.model_dump()),
                        ))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    async def get_recent_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        def _op():
            conn = self._get_connection()
            try:
                cursor = conn.execute("""
                    SELECT * FROM agent_decisions ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                out = []
                for r in rows:
                    item = dict(r)
                    if item.get("reason_codes_json"):
                        item["reason_codes"] = json.loads(item["reason_codes_json"])
                    if item.get("result_json"):
                        item["result"] = json.loads(item["result_json"])
                    out.append(item)
                return out
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

    # --- Paper Orders, Fills, Positions, Portfolio ---

    async def save_paper_order(self, order: PaperOrder) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO paper_orders (
                                order_id, token_mint, side, requested_amount_usd,
                                requested_qty, limit_price_usd, created_at, status, rejection_reason
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            order.order_id,
                            order.token_mint,
                            order.side.value,
                            order.requested_amount_usd,
                            order.requested_qty,
                            order.limit_price_usd,
                            order.created_at,
                            order.status.value,
                            order.rejection_reason,
                        ))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    async def save_paper_fill(self, fill: PaperFill) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO paper_fills (
                                fill_id, order_id, token_mint, side, executed_qty,
                                executed_price_usd, fee_usd, slippage_bps, fill_timestamp
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            fill.fill_id,
                            fill.order_id,
                            fill.token_mint,
                            fill.side.value,
                            fill.executed_qty,
                            fill.executed_price_usd,
                            fill.fee_usd,
                            fill.slippage_bps,
                            fill.fill_timestamp,
                        ))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    async def save_paper_position(self, pos: PaperPosition) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO paper_positions (
                                position_id, token_mint, token_symbol, qty, average_entry_price_usd,
                                current_price_usd, invested_capital_usd, current_value_usd,
                                unrealized_pnl_usd, unrealized_pnl_pct, realized_pnl_usd,
                                total_fees_paid_usd, is_open, is_stale_price, opened_at,
                                closed_at, peak_price_usd, exit_reason
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            pos.position_id,
                            pos.token_mint,
                            pos.token_symbol,
                            pos.qty,
                            pos.average_entry_price_usd,
                            pos.current_price_usd,
                            pos.invested_capital_usd,
                            pos.current_value_usd,
                            pos.unrealized_pnl_usd,
                            pos.unrealized_pnl_pct,
                            pos.realized_pnl_usd,
                            pos.total_fees_paid_usd,
                            1 if pos.is_open else 0,
                            1 if pos.is_stale_price else 0,
                            pos.opened_at,
                            pos.closed_at,
                            pos.peak_price_usd,
                            pos.exit_reason,
                        ))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    async def get_open_positions(self) -> List[PaperPosition]:
        def _op():
            conn = self._get_connection()
            try:
                cursor = conn.execute("SELECT * FROM paper_positions WHERE is_open = 1")
                rows = cursor.fetchall()
                positions = []
                for r in rows:
                    p = PaperPosition(
                        position_id=r["position_id"],
                        token_mint=r["token_mint"],
                        token_symbol=r["token_symbol"],
                        qty=r["qty"],
                        average_entry_price_usd=r["average_entry_price_usd"],
                        current_price_usd=r["current_price_usd"],
                        invested_capital_usd=r["invested_capital_usd"],
                        current_value_usd=r["current_value_usd"],
                        unrealized_pnl_usd=r["unrealized_pnl_usd"],
                        unrealized_pnl_pct=r["unrealized_pnl_pct"],
                        realized_pnl_usd=r["realized_pnl_usd"],
                        total_fees_paid_usd=r["total_fees_paid_usd"],
                        is_open=bool(r["is_open"]),
                        is_stale_price=bool(r["is_stale_price"]),
                        opened_at=r["opened_at"],
                        closed_at=r["closed_at"],
                        peak_price_usd=r["peak_price_usd"],
                        exit_reason=r["exit_reason"],
                    )
                    positions.append(p)
                return positions
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

    async def get_all_positions(self) -> List[PaperPosition]:
        def _op():
            conn = self._get_connection()
            try:
                cursor = conn.execute("SELECT * FROM paper_positions ORDER BY opened_at DESC")
                rows = cursor.fetchall()
                return [
                    PaperPosition(
                        position_id=r["position_id"],
                        token_mint=r["token_mint"],
                        token_symbol=r["token_symbol"],
                        qty=r["qty"],
                        average_entry_price_usd=r["average_entry_price_usd"],
                        current_price_usd=r["current_price_usd"],
                        invested_capital_usd=r["invested_capital_usd"],
                        current_value_usd=r["current_value_usd"],
                        unrealized_pnl_usd=r["unrealized_pnl_usd"],
                        unrealized_pnl_pct=r["unrealized_pnl_pct"],
                        realized_pnl_usd=r["realized_pnl_usd"],
                        total_fees_paid_usd=r["total_fees_paid_usd"],
                        is_open=bool(r["is_open"]),
                        is_stale_price=bool(r["is_stale_price"]),
                        opened_at=r["opened_at"],
                        closed_at=r["closed_at"],
                        peak_price_usd=r["peak_price_usd"],
                        exit_reason=r["exit_reason"],
                    )
                    for r in rows
                ]
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

    async def save_portfolio_snapshot(self, snap: PortfolioSnapshot) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO portfolio_snapshots (
                                snapshot_id, timestamp, cash_balance_usd, positions_value_usd,
                                total_equity_usd, total_realized_pnl_usd, total_unrealized_pnl_usd,
                                total_fees_paid_usd, peak_equity_usd, current_drawdown_pct,
                                max_drawdown_pct, open_positions_count
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            snap.snapshot_id,
                            snap.timestamp,
                            snap.cash_balance_usd,
                            snap.positions_value_usd,
                            snap.total_equity_usd,
                            snap.total_realized_pnl_usd,
                            snap.total_unrealized_pnl_usd,
                            snap.total_fees_paid_usd,
                            snap.peak_equity_usd,
                            snap.current_drawdown_pct,
                            snap.max_drawdown_pct,
                            snap.open_positions_count,
                        ))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    async def get_latest_portfolio_snapshot(self) -> Optional[PortfolioSnapshot]:
        def _op():
            conn = self._get_connection()
            try:
                cursor = conn.execute("""
                    SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1
                """)
                r = cursor.fetchone()
                if not r:
                    return None
                return PortfolioSnapshot(
                    snapshot_id=r["snapshot_id"],
                    timestamp=r["timestamp"],
                    cash_balance_usd=r["cash_balance_usd"],
                    positions_value_usd=r["positions_value_usd"],
                    total_equity_usd=r["total_equity_usd"],
                    total_realized_pnl_usd=r["total_realized_pnl_usd"],
                    total_unrealized_pnl_usd=r["total_unrealized_pnl_usd"],
                    total_fees_paid_usd=r["total_fees_paid_usd"],
                    peak_equity_usd=r["peak_equity_usd"],
                    current_drawdown_pct=r["current_drawdown_pct"],
                    max_drawdown_pct=r["max_drawdown_pct"],
                    open_positions_count=r["open_positions_count"],
                )
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

    async def get_portfolio_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        def _op():
            conn = self._get_connection()
            try:
                cursor = conn.execute("""
                    SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
                return [dict(r) for r in cursor.fetchall()]
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

    async def log_system_event(self, event_id: str, event_type: str, severity: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT INTO system_events (
                                event_id, event_type, timestamp, severity, message, details_json
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            event_id,
                            event_type,
                            time.time(),
                            severity,
                            message,
                            json.dumps(details or {}),
                        ))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    # --- Step 2: Multi-Agent Decisions Persistence ---

    async def save_chief_decision(self, consensus: ChiefConsensusRecord) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO chief_decisions (
                                consensus_id, token_mint, token_symbol, data_timestamp, decision_timestamp,
                                final_decision, strategic_decision, is_risk_vetoed, chief_reason,
                                sources_used_json, favorable_signals_json, unfavorable_signals_json,
                                confidence_score, confidence_method, invalidation_conditions_json,
                                identified_risks_json, strategy_version, expected_outcome,
                                evaluation_horizon_sec, target_price_usd, invalidation_price_usd,
                                entry_price_usd, recommended_position_usd, processing_latency_ms,
                                details_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            consensus.consensus_id,
                            consensus.token_mint,
                            consensus.token_symbol,
                            consensus.data_timestamp or consensus.timestamp,
                            consensus.timestamp,
                            consensus.final_decision.value if hasattr(consensus.final_decision, 'value') else str(consensus.final_decision),
                            consensus.strategic_decision.value if consensus.strategic_decision and hasattr(consensus.strategic_decision, 'value') else (str(consensus.strategic_decision) if consensus.strategic_decision else None),
                            1 if consensus.is_risk_vetoed else 0,
                            consensus.chief_reason,
                            json.dumps(consensus.sources_used),
                            json.dumps(consensus.favorable_signals),
                            json.dumps(consensus.unfavorable_signals),
                            consensus.confidence_score,
                            consensus.confidence_method,
                            json.dumps(consensus.invalidation_conditions),
                            json.dumps(consensus.identified_risks),
                            consensus.strategy_version,
                            consensus.expected_outcome,
                            consensus.evaluation_horizon_sec,
                            consensus.target_price_usd,
                            consensus.invalidation_price_usd,
                            consensus.entry_price_usd,
                            consensus.recommended_position_usd,
                            consensus.processing_total_latency_ms,
                            json.dumps({
                                "risk_veto_reasons": consensus.risk_veto_reasons,
                                "contributing_agents_count": len(consensus.contributing_agents),
                            }),
                        ))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    async def get_recent_chief_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        def _op():
            conn = self._get_connection()
            try:
                cursor = conn.execute("""
                    SELECT * FROM chief_decisions ORDER BY decision_timestamp DESC LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                out = []
                for r in rows:
                    item = dict(r)
                    for k in ("sources_used", "favorable_signals", "unfavorable_signals", "invalidation_conditions", "identified_risks", "details"):
                        json_k = f"{k}_json"
                        if item.get(json_k):
                            item[k] = json.loads(item[json_k])
                    out.append(item)
                return out
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

    # --- Step 3: Measurable Learning & Strategy Benchmarks ---

    async def save_decision_outcome(self, outcome: Any) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO decision_outcomes (
                                outcome_id, consensus_id, token_mint, evaluated_at, horizon_sec,
                                entry_price_usd, target_price_usd, invalidation_price_usd,
                                peak_price_usd, trough_price_usd, final_price_usd,
                                is_correct, is_false_positive, is_true_negative,
                                simulated_net_return_pct, max_drawdown_pct, price_forecast_error_abs,
                                strategy_version, split_type
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            outcome.outcome_id,
                            outcome.consensus_id,
                            outcome.token_mint,
                            outcome.evaluated_at,
                            outcome.horizon_sec,
                            outcome.entry_price_usd,
                            outcome.target_price_usd,
                            outcome.invalidation_price_usd,
                            outcome.peak_price_usd,
                            outcome.trough_price_usd,
                            outcome.final_price_usd,
                            1 if outcome.is_correct else 0,
                            1 if outcome.is_false_positive else 0,
                            1 if outcome.is_true_negative else 0,
                            outcome.simulated_net_return_pct,
                            outcome.max_drawdown_pct,
                            outcome.price_forecast_error_abs,
                            outcome.strategy_version,
                            outcome.split_type.value if hasattr(outcome.split_type, 'value') else str(outcome.split_type),
                        ))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    async def get_decision_outcomes(self, limit: int = 200, split: Optional[str] = None) -> List[Dict[str, Any]]:
        def _op():
            conn = self._get_connection()
            try:
                if split:
                    cursor = conn.execute("""
                        SELECT * FROM decision_outcomes WHERE split_type = ? ORDER BY evaluated_at DESC LIMIT ?
                    """, (split, limit))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM decision_outcomes ORDER BY evaluated_at DESC LIMIT ?
                    """, (limit,))
                return [dict(r) for r in cursor.fetchall()]
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

    async def save_strategy_benchmark(self, bench: Any) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO strategy_benchmarks (
                                version, created_at, description, is_active, sample_size,
                                accuracy_rate, false_positive_rate, simulated_net_return_pct,
                                max_drawdown_pct, benchmark_comparison_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            bench.version,
                            bench.created_at,
                            bench.description,
                            1 if bench.is_active else 0,
                            bench.sample_size,
                            bench.accuracy_rate,
                            bench.false_positive_rate,
                            bench.simulated_net_return_pct,
                            bench.max_drawdown_pct,
                            json.dumps(bench.benchmark_comparison),
                        ))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    async def get_strategy_benchmarks(self) -> List[Dict[str, Any]]:
        def _op():
            conn = self._get_connection()
            try:
                cursor = conn.execute("SELECT * FROM strategy_benchmarks ORDER BY created_at DESC")
                out = []
                for r in cursor.fetchall():
                    item = dict(r)
                    if item.get("benchmark_comparison_json"):
                        item["benchmark_comparison"] = json.loads(item["benchmark_comparison_json"])
                    out.append(item)
                return out
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

    # --- Step 4: Live Trading Proposals, Transactions & Risk Audit ---

    async def save_live_proposal(self, p: Dict[str, Any]) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO live_proposals (
                                proposal_id, token_mint, token_symbol, side, wallet_address,
                                input_amount_sol, expected_output_tokens, min_output_tokens,
                                estimated_fee_sol, slippage_bps, quote_json, unsigned_tx_base64,
                                status, rejection_reason, created_at, expires_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            p["proposal_id"],
                            p["token_mint"],
                            p.get("token_symbol", "TOKEN"),
                            p["side"],
                            p["wallet_address"],
                            p["input_amount_sol"],
                            p["expected_output_tokens"],
                            p["min_output_tokens"],
                            p["estimated_fee_sol"],
                            p["slippage_bps"],
                            json.dumps(p.get("quote", {})),
                            p["unsigned_tx_base64"],
                            p["status"],
                            p.get("rejection_reason"),
                            p["created_at"],
                            p["expires_at"],
                        ))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    async def get_live_proposals(self, limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
        def _op():
            conn = self._get_connection()
            try:
                if status:
                    cursor = conn.execute("""
                        SELECT * FROM live_proposals WHERE status = ? ORDER BY created_at DESC LIMIT ?
                    """, (status, limit))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM live_proposals ORDER BY created_at DESC LIMIT ?
                    """, (limit,))
                out = []
                for r in cursor.fetchall():
                    item = dict(r)
                    if item.get("quote_json"):
                        item["quote"] = json.loads(item["quote_json"])
                    out.append(item)
                return out
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

    async def update_live_proposal_status(self, proposal_id: str, status: str, rejection_reason: Optional[str] = None) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            UPDATE live_proposals SET status = ?, rejection_reason = ? WHERE proposal_id = ?
                        """, (status, rejection_reason, proposal_id))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    async def save_live_transaction(self, tx: Dict[str, Any]) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO live_transactions (
                                tx_signature, proposal_id, wallet_address, token_mint, side,
                                amount_sol, amount_tokens, slot, block_time, status,
                                confirmation_commitment, error_message, fee_paid_sol,
                                submitted_at, confirmed_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            tx["tx_signature"],
                            tx["proposal_id"],
                            tx["wallet_address"],
                            tx["token_mint"],
                            tx["side"],
                            tx["amount_sol"],
                            tx["amount_tokens"],
                            tx.get("slot"),
                            tx.get("block_time"),
                            tx["status"],
                            tx.get("confirmation_commitment", "confirmed"),
                            tx.get("error_message"),
                            tx.get("fee_paid_sol"),
                            tx.get("submitted_at", time.time()),
                            tx.get("confirmed_at"),
                        ))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    async def update_live_transaction_status(self, tx_signature: str, status: str, slot: Optional[int] = None, err: Optional[str] = None) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            UPDATE live_transactions 
                            SET status = ?, slot = COALESCE(?, slot), error_message = ?, confirmed_at = CASE WHEN ? = 'CONFIRMED' THEN ? ELSE confirmed_at END
                            WHERE tx_signature = ?
                        """, (status, slot, err, status, time.time(), tx_signature))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    async def get_live_transactions(self, limit: int = 50) -> List[Dict[str, Any]]:
        def _op():
            conn = self._get_connection()
            try:
                cursor = conn.execute("""
                    SELECT * FROM live_transactions ORDER BY submitted_at DESC LIMIT ?
                """, (limit,))
                return [dict(r) for r in cursor.fetchall()]
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

    async def log_risk_audit(
        self,
        proposal_id: Optional[str],
        check_name: str,
        passed: bool,
        threshold_val: str,
        observed_val: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        async with self._lock:
            def _op():
                conn = self._get_connection()
                try:
                    with conn:
                        conn.execute("""
                            INSERT INTO risk_audit_log (
                                proposal_id, check_name, passed, threshold_val, observed_val, timestamp, details_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            proposal_id,
                            check_name,
                            1 if passed else 0,
                            str(threshold_val),
                            str(observed_val),
                            time.time(),
                            json.dumps(details or {}),
                        ))
                finally:
                    conn.close()

            await asyncio.to_thread(_op)

    async def get_risk_audit_logs(self, limit: int = 50, proposal_id: Optional[str] = None) -> List[Dict[str, Any]]:
        def _op():
            conn = self._get_connection()
            try:
                if proposal_id:
                    cursor = conn.execute("""
                        SELECT * FROM risk_audit_log WHERE proposal_id = ? ORDER BY timestamp DESC LIMIT ?
                    """, (proposal_id, limit))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM risk_audit_log ORDER BY timestamp DESC LIMIT ?
                    """, (limit,))
                rows = cursor.fetchall()
                out = []
                for r in rows:
                    item = dict(r)
                    if item.get("details_json"):
                        item["details"] = json.loads(item["details_json"])
                    out.append(item)
                return out
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

    async def get_token_market_events(self, token_mint: str, start_time: Optional[float] = None, limit: int = 100) -> List[Dict[str, Any]]:
        def _op():
            conn = self._get_connection()
            try:
                if start_time is not None:
                    cursor = conn.execute("""
                        SELECT * FROM market_events 
                        WHERE token_mint = ? AND local_receive_timestamp >= ? 
                        ORDER BY local_receive_timestamp ASC LIMIT ?
                    """, (token_mint, start_time, limit))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM market_events 
                        WHERE token_mint = ? 
                        ORDER BY local_receive_timestamp ASC LIMIT ?
                    """, (token_mint, limit))
                return [dict(r) for r in cursor.fetchall()]
            finally:
                conn.close()

        return await asyncio.to_thread(_op)
