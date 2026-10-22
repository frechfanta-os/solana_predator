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
