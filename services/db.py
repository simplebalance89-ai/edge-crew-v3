"""
Optional Postgres persistence layer with connection pooling.

Lazy-loaded: if DATABASE_URL isn't set, every call here is a silent no-op
and the app keeps writing to JSON files in PERSIST_DIR exactly as before.
This is intentionally additive — picks.json and calibration.json remain
the source of truth until a full migration happens.

When DATABASE_URL is set, the app writes through to two minimal tables:
  - picks(id, username, sport, game_id, team, type, line, amount, odds,
          grade, result, profit, locked_at)
  - calibration_snapshots(id, generated_at, payload_jsonb)

Schema is created on first connect via CREATE TABLE IF NOT EXISTS so no
external migration step is needed. The full hypertable schema in
infrastructure/db/schema.sql is a separate, future-state migration target.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Optional

# Add parent directory to path for database import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import get_db_session

logger = logging.getLogger("edge-crew-v3.db")

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

_pool = None  # asyncpg.Pool when initialized
_init_attempted = False
_init_failed = False

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS picks (
    id VARCHAR PRIMARY KEY,
    username VARCHAR NOT NULL,
    sport VARCHAR,
    game_id VARCHAR,
    team VARCHAR,
    type VARCHAR,
    line DOUBLE PRECISION,
    amount DOUBLE PRECISION,
    odds INTEGER,
    grade VARCHAR,
    result VARCHAR,
    profit DOUBLE PRECISION,
    locked_at TIMESTAMP WITH TIME ZONE,
    settled_at TIMESTAMP WITH TIME ZONE,
    raw JSONB
);
CREATE INDEX IF NOT EXISTS picks_username_idx ON picks(username);
CREATE INDEX IF NOT EXISTS picks_result_idx ON picks(result);
CREATE INDEX IF NOT EXISTS picks_sport_idx ON picks(sport);

CREATE TABLE IF NOT EXISTS calibration_snapshots (
    id BIGSERIAL PRIMARY KEY,
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    payload JSONB NOT NULL
);
"""


def is_enabled() -> bool:
    return bool(DATABASE_URL) and not _init_failed


async def get_pool():
    """Lazy connect. Returns database session if available, None if disabled."""
    global _pool, _init_attempted, _init_failed
    if not DATABASE_URL or _init_failed:
        return None
    if _pool is not None:
        return _pool
    if _init_attempted:
        return _pool  # may still be None if a prior attempt failed silently

    _init_attempted = True
    try:
        # Initialize database manager with connection pooling
        from app.database import initialize_database
        db_manager = initialize_database()
        
        # Test connection
        if db_manager.test_connection():
            logger.info("[DB] postgres pool initialized with connection pooling")
            _pool = True  # Use a simple flag to indicate success
            return _pool
        else:
            logger.warning("[DB] postgres connection test failed")
            _init_failed = True
            return None
            
    except Exception as e:
        logger.warning(f"[DB] postgres init failed: {e}")
        _init_failed = True
        _pool = None
        return None


async def upsert_pick(pick: dict, username: str) -> None:
    """Write-through for a locked pick. No-op if postgres disabled."""
    pool = await get_pool()
    if pool is None:
        return
    try:
        # Create tables if they don't exist
        await _ensure_tables_exist()
        
        # Use database session for the operation
        with get_db_session() as session:
            session.execute(
                """
                INSERT INTO picks
                    (id, username, sport, game_id, team, type, line, amount,
                     odds, grade, result, profit, locked_at, raw)
                VALUES (:id, :username, :sport, :game_id, :team, :type, :line, :amount,
                        :odds, :grade, :result, :profit, :locked_at, :raw)
                ON CONFLICT (id) DO UPDATE SET
                    result = EXCLUDED.result,
                    profit = EXCLUDED.profit,
                    raw    = EXCLUDED.raw
                """,
                {
                    "id": pick.get("id"),
                    "username": username,
                    "sport": pick.get("sport"),
                    "game_id": pick.get("game_id"),
                    "team": pick.get("team"),
                    "type": pick.get("type"),
                    "line": _to_float(pick.get("line")),
                    "amount": _to_float(pick.get("amount")),
                    "odds": _to_int(pick.get("odds")),
                    "grade": pick.get("grade"),
                    "result": pick.get("result"),
                    "profit": _to_float(pick.get("profit")),
                    "locked_at": pick.get("locked_at"),
                    "raw": json.dumps(pick)
                }
            )
    except Exception as e:
        logger.debug(f"[DB] upsert_pick failed for {pick.get('id')}: {e}")


async def _ensure_tables_exist():
    """Ensure database tables exist"""
    try:
        with get_db_session() as session:
            session.execute(CREATE_SQL)
            logger.info("[DB] Database tables ensured")
    except Exception as e:
        logger.warning(f"[DB] Failed to ensure tables: {e}")


async def update_pick_result(pick_id: str, result: str, profit: float) -> None:
    pool = await get_pool()
    if pool is None:
        return
    try:
        with get_db_session() as session:
            session.execute(
                "UPDATE picks SET result=:result, profit=:profit, settled_at=now() WHERE id=:pick_id",
                {"pick_id": pick_id, "result": result, "profit": _to_float(profit)}
            )
    except Exception as e:
        logger.debug(f"[DB] update_pick_result failed for {pick_id}: {e}")


async def write_calibration_snapshot(payload: dict) -> None:
    pool = await get_pool()
    if pool is None:
        return
    try:
        with get_db_session() as session:
            session.execute(
                "INSERT INTO calibration_snapshots (payload) VALUES (:payload)",
                {"payload": json.dumps(payload)}
            )
    except Exception as e:
        logger.debug(f"[DB] write_calibration_snapshot failed: {e}")


def _to_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
