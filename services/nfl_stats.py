"""
NFL team stats — turnover differential and red zone efficiency via ESPN.

Uses the same ESPN team statistics endpoint as espn_pace.py. Pulls
giveaways, takeaways (turnover diff) and red zone scoring percentage
so the grade engine can score turnover_diff and red_zone with real data.

Cached per team_id for 30 minutes.
"""
from __future__ import annotations

import sys
sys.stdout.reconfigure(encoding="utf-8")

import logging
import time
from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

logger = logging.getLogger("edge-crew-v3.nfl_stats")

ESPN_TEAM_STATS = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/statistics"

_CACHE_TTL = 1800  # 30 minutes
_cache: dict = {}  # {team_id: (fetched_at, dict|None)}


def _extract_stat(categories: list, target_names: tuple) -> Optional[float]:
    """Walk ESPN's nested stat blocks and return the first matching stat value."""
    for cat in categories or []:
        for s in cat.get("stats", []) or []:
            name = (s.get("name") or "").lower()
            if name in target_names:
                val = s.get("value")
                try:
                    return float(val) if val is not None else None
                except (TypeError, ValueError):
                    return None
    return None


async def get_nfl_team_stats(team_name: str, espn_team_id: str = None) -> Optional[dict]:
    """Return {"turnover_diff": int, "red_zone_pct": float} or None on miss/fail."""
    if not espn_team_id:
        return None
    if httpx is None:
        return None

    team_id = str(espn_team_id)
    cached = _cache.get(team_id)
    if cached and (time.monotonic() - cached[0]) < _CACHE_TTL:
        return cached[1]

    url = ESPN_TEAM_STATS.format(team_id=team_id)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
        if r.status_code != 200:
            logger.debug(f"ESPN NFL stats {team_id} HTTP {r.status_code}")
            return None
        data = r.json() or {}
    except Exception as e:
        logger.debug(f"ESPN NFL stats {team_id} fetch failed: {e}")
        return None

    results = data.get("results") or {}
    stats_root = results.get("stats") or data.get("stats") or {}
    categories = stats_root.get("categories") or stats_root.get("splits") or []
    if not categories and "splits" in data:
        categories = data["splits"].get("categories") or []

    takeaways = _extract_stat(categories, ("totaltakeaways", "takeaways", "interceptions"))
    giveaways = _extract_stat(categories, ("totalgiveaways", "giveaways", "fumblesLost"))
    red_zone_pct = _extract_stat(categories, ("redzonescoring%", "redzoneefficiency", "redzonescoringpct"))

    if takeaways is None and giveaways is None and red_zone_pct is None:
        _cache[team_id] = (time.monotonic(), None)
        return None

    turnover_diff = None
    if takeaways is not None and giveaways is not None:
        turnover_diff = int(takeaways - giveaways)

    out = {}
    if turnover_diff is not None:
        out["turnover_diff"] = turnover_diff
    if red_zone_pct is not None:
        out["red_zone_pct"] = round(red_zone_pct, 1) if red_zone_pct > 1 else round(red_zone_pct * 100, 1)

    if not out:
        _cache[team_id] = (time.monotonic(), None)
        return None

    _cache[team_id] = (time.monotonic(), out)
    logger.info(f"[NFL_STATS] {team_name} (id={team_id}): {out}")
    return out
