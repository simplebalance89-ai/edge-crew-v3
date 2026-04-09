"""
Optional Postgres persistence layer.

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
from typing import Any, Optional

logger = logging.getLogger("edge-crew-v3.db")

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

_pool = None  # asyncpg.Pool when initialized
_init_attempted = False
_init_failed = False

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS picks (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    sport TEXT,
    game_id TEXT,
    team TEXT,
    type TEXT,
    line DOUBLE PRECISION,
    amount DOUBLE PRECISION,
    odds INTEGER,
    grade TEXT,
    result TEXT,
    profit DOUBLE PRECISION,
    locked_at TIMESTAMPTZ,
    settled_at TIMESTAMPTZ,
    raw JSONB
);
CREATE INDEX IF NOT EXISTS picks_username_idx ON picks(username);
CREATE INDEX IF NOT EXISTS picks_result_idx ON picks(result);
CREATE INDEX IF NOT EXISTS picks_sport_idx ON picks(sport);

CREATE TABLE IF NOT EXISTS calibration_snapshots (
    id BIGSERIAL PRIMARY KEY,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSONB NOT NULL
);
"""


def is_enabled() -> bool:
    return bool(DATABASE_URL) and not _init_failed


async def get_pool():
    """Lazy connect. Returns None if disabled or asyncpg unavailable."""
    global _pool, _init_attempted, _init_failed
    if not DATABASE_URL or _init_failed:
        return None
    if _pool is not None:
        return _pool
    if _init_attempted:
        return _pool  # may still be None if a prior attempt failed silently

    _init_attempted = True
    try:
        import asyncpg  # type: ignore
    except ImportError:
        logger.warning("[DB] DATABASE_URL set but asyncpg not installed; pip install asyncpg")
        _init_failed = True
        return None

    try:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute(CREATE_SQL)
        logger.info("[DB] postgres pool initialized; tables ensured")
        return _pool
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
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO picks
                    (id, username, sport, game_id, team, type, line, amount,
                     odds, grade, result, profit, locked_at, raw)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                ON CONFLICT (id) DO UPDATE SET
                    result = EXCLUDED.result,
                    profit = EXCLUDED.profit,
                    raw    = EXCLUDED.raw
                """,
                pick.get("id"),
                username,
                pick.get("sport"),
                pick.get("game_id"),
                pick.get("team"),
                pick.get("type"),
                _to_float(pick.get("line")),
                _to_float(pick.get("amount")),
                _to_int(pick.get("odds")),
                pick.get("grade"),
                pick.get("result"),
                _to_float(pick.get("profit")),
                pick.get("locked_at"),
                json.dumps(pick),
            )
    except Exception as e:
        logger.debug(f"[DB] upsert_pick failed for {pick.get('id')}: {e}")


async def update_pick_result(pick_id: str, result: str, profit: float) -> None:
    pool = await get_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE picks SET result=$2, profit=$3, settled_at=now() WHERE id=$1",
                pick_id, result, _to_float(profit),
            )
    except Exception as e:
        logger.debug(f"[DB] update_pick_result failed for {pick_id}: {e}")


async def write_calibration_snapshot(payload: dict) -> None:
    pool = await get_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO calibration_snapshots (payload) VALUES ($1::jsonb)",
                json.dumps(payload),
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
