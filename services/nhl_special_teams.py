"""
NHL special teams data (PP%, PK%) via the official NHL Stats API.

Uses the same summary endpoint as nhl_pace — that response already
contains powerPlayPct and penaltyKillPct for every team. We maintain
a separate cache so this module can be imported and tested independently.
"""
from __future__ import annotations

import logging
import sys
import time
from typing import Optional

sys.stdout.reconfigure(encoding="utf-8")

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

from services.nhl_pace import NAME_MAP

logger = logging.getLogger("edge-crew-v3.nhl_special_teams")

NHL_SUMMARY_URL = "https://api.nhle.com/stats/rest/en/team/summary"

_CACHE_TTL = 3600
_cache: dict = {"fetched_at": 0.0, "by_team": {}}


async def _refresh_cache() -> None:
    """Pull the current-season summary for all teams in one request."""
    global _cache
    if httpx is None:
        return
    try:
        params = {
            "isAggregate": "false",
            "isGame": "false",
            "sort": '[{"property":"points","direction":"DESC"}]',
            "start": 0,
            "limit": 50,
            "factCayenneExp": "gamesPlayed>=1",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(NHL_SUMMARY_URL, params=params)
        if r.status_code != 200:
            logger.debug(f"NHL summary HTTP {r.status_code}")
            return
        data = r.json() or {}
        rows = data.get("data") or []
        by_team: dict[str, dict] = {}
        for row in rows:
            name = row.get("teamFullName") or ""
            if not name:
                continue
            pp = row.get("powerPlayPct")
            pk = row.get("penaltyKillPct")
            by_team[name] = {
                "pp_pct": round(float(pp), 1) if pp is not None else None,
                "pk_pct": round(float(pk), 1) if pk is not None else None,
            }
        _cache = {"fetched_at": time.monotonic(), "by_team": by_team}
        logger.info(f"[NHL_ST] cached special teams for {len(by_team)} teams")
    except Exception as e:
        logger.debug(f"[NHL_ST] refresh failed: {e}")


async def get_team_special_teams(team_name: str) -> Optional[dict]:
    """Return {"pp_pct": float, "pk_pct": float} or None."""
    age = time.monotonic() - _cache["fetched_at"]
    if not _cache["by_team"] or age > _CACHE_TTL:
        await _refresh_cache()
    if not _cache["by_team"]:
        return None

    canonical = NAME_MAP.get(team_name, team_name)
    row = _cache["by_team"].get(canonical)
    if row is None:
        return None

    if row.get("pp_pct") is None and row.get("pk_pct") is None:
        return None

    return {
        "pp_pct": row.get("pp_pct"),
        "pk_pct": row.get("pk_pct"),
    }
