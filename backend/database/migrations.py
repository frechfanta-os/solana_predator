"""Database migration engine for SOLANA PREDATOR SQLite WAL store."""

import sqlite3
import time
import logging
from backend.database.schema import SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4

logger = logging.getLogger("predator.database.migrations")

CURRENT_SCHEMA_VERSION = 4


def apply_migrations(db_path: str) -> None:
    """Apply versioned schema migrations ensuring WAL mode is enabled."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Enforce WAL mode and foreign keys
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        
        # Create migration tracking table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at REAL NOT NULL
            );
        """)
        conn.commit()
        
        # Check current version
        cursor.execute("SELECT MAX(version) FROM schema_migrations;")
        row = cursor.fetchone()
        current_version = row[0] if (row and row[0] is not None) else 0
        
        if current_version < 1:
            logger.info("Applying Schema V1 to %s", db_path)
            cursor.executescript(SCHEMA_V1)
            cursor.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (1, ?);",
                (time.time(),),
            )
            conn.commit()
            logger.info("Schema V1 applied successfully.")

        if current_version < 2:
            logger.info("Applying Schema V2 to %s", db_path)
            cursor.executescript(SCHEMA_V2)
            cursor.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (2, ?);",
                (time.time(),),
            )
            conn.commit()
            logger.info("Schema V2 applied successfully.")

        if current_version < 3:
            logger.info("Applying Schema V3 to %s", db_path)
            cursor.executescript(SCHEMA_V3)
            cursor.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (3, ?);",
                (time.time(),),
            )
            conn.commit()
            logger.info("Schema V3 applied successfully.")

        if current_version < 4:
            logger.info("Applying Schema V4 to %s", db_path)
            cursor.executescript(SCHEMA_V4)
            cursor.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (4, ?);",
                (time.time(),),
            )
            conn.commit()
            logger.info("Schema V4 applied successfully.")
        else:
            logger.debug("Database %s already at schema version %s.", db_path, current_version)
            
    finally:
        conn.close()
