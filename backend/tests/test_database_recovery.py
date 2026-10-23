"""Tests for database WAL mode, migrations, and restart integrity."""

import sqlite3
import pytest
from backend.database.migrations import apply_migrations
from backend.database.repository import Repository
from backend.models import TokenMetadata


def test_schema_migrations_and_wal_mode(temp_db_path):
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    
    # Verify WAL mode
    cursor.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    assert mode.lower() == "wal"

    # Verify migration table
    cursor.execute("SELECT MAX(version) FROM schema_migrations;")
    max_v = cursor.fetchone()[0]
    assert max_v == 3

    # Verify indexes exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_market_events_token';")
    assert cursor.fetchone() is not None

    # Verify system_config table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_config';")
    assert cursor.fetchone() is not None
    conn.close()


@pytest.mark.asyncio
async def test_database_restart_recovery(temp_db_path):
    repo = Repository(temp_db_path)
    tok = TokenMetadata(
        mint="TokenMintPersist11111111111111111111111",
        name="PersistToken",
        symbol="PRST",
        first_observed_timestamp=1234567.8,
    )
    await repo.upsert_token(tok)

    # Persist kill-switch config
    await repo.set_system_config("emergency_kill_switch", "true")

    # Reconnect fresh repository simulating restart
    repo2 = Repository(temp_db_path)
    tokens = await repo2.get_all_tokens()
    assert any(t["mint"] == tok.mint for t in tokens)

    # Verify kill-switch state survived restart
    val = await repo2.get_system_config("emergency_kill_switch")
    assert val == "true"
