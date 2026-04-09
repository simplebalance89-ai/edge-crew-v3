"""
ESPN MMA fighter lookup.

Combat sports (MMA/Boxing) currently grade from odds only — no fighter
context flows into the prompts or the grade engine. This module adds a
free, public-API fighter record + recent-form lookup so the AI prompt
builder can hand the models actual fight history instead of just
moneyline numbers.

Returns the same shape for both sides:
    {"name", "record", "wins", "losses", "draws", "last5", "ko_pct"}

Anything missing is left as None so the prompt builder can render "—".
Cached per fighter name for an hour. Defensive on every error path.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

logger = logging.getLogger("edge-crew-v3.mma_fighter")

ESPN_SEARCH = "https://site.web.api.espn.com/apis/search/v2"
ESPN_ATHLETE_DETAIL = "http://sports.core.api.espn.com/v2/sports/{sport_path}/leagues/{league}/athletes/{athlete_id}"

# (sport_path, league, search_sport_filter) per combat sport
SPORT_ROUTES = {
    "MMA":    ("mma",    "ufc",    "mma"),
    "BOXING": ("boxing", "boxing", "boxing"),
}

_CACHE_TTL = 3600
_cache: dict = {}  # {name_lower: (fetched_at, dict_or_none)}


async def _search_athlete_id(client, name: str, search_sport: str = "mma") -> Optional[str]:
    try:
        r = await client.get(
            ESPN_SEARCH,
            params={"query": name, "limit": 5, "type": "player", "sport": search_sport},
        )
        if r.status_code != 200:
            return None
        data = r.json() or {}
        results = data.get("results") or []
        for block in results:
            for hit in block.get("contents") or []:
                if (hit.get("type") or "").lower() != "player":
                    continue
                display = (hit.get("displayName") or "").lower()
                if name.lower() in display or display in name.lower():
                    uid = hit.get("uid") or hit.get("id") or ""
                    # uid format: s:3200~l:600~a:12345 — last segment is athlete id
                    if "a:" in str(uid):
                        return str(uid).split("a:")[-1].split("~")[0]
                    if hit.get("id"):
                        return str(hit["id"])
        return None
    except Exception as e:
        logger.debug(f"[MMA] athlete search failed for {name}: {e}")
        return None


async def _fetch_athlete_detail(client, athlete_id: str, sport_path: str, league: str) -> Optional[dict]:
    try:
        url = ESPN_ATHLETE_DETAIL.format(sport_path=sport_path, league=league, athlete_id=athlete_id)
        r = await client.get(url)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as e:
        logger.debug(f"[COMBAT] athlete detail failed for {athlete_id}: {e}")
        return None


def _parse_record(record_str: str) -> dict:
    """Parse '24-3-0' or '24-3' into wins/losses/draws."""
    out = {"wins": None, "losses": None, "draws": None}
    if not record_str:
        return out
    parts = record_str.split("-")
    try:
        if len(parts) >= 2:
            out["wins"] = int(parts[0])
            out["losses"] = int(parts[1])
        if len(parts) >= 3:
            out["draws"] = int(parts[2])
    except (ValueError, TypeError):
        pass
    return out


async def get_fighter_profile(name: str, sport: str = "MMA") -> Optional[dict]:
    """Return a fighter/boxer profile dict, or None if lookup fails.

    `sport` is "MMA" or "BOXING" — both go through ESPN's combat sports
    endpoints with the right league fragment swapped in.
    """
    if not name or httpx is None:
        return None
    sport_upper = sport.upper()
    if sport_upper not in SPORT_ROUTES:
        return None
    sport_path, league, search_sport = SPORT_ROUTES[sport_upper]

    key = f"{sport_upper}:{name.lower().strip()}"
    cached = _cache.get(key)
    if cached and (time.monotonic() - cached[0]) < _CACHE_TTL:
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            athlete_id = await _search_athlete_id(client, name, search_sport)
            if not athlete_id:
                _cache[key] = (time.monotonic(), None)
                return None
            detail = await _fetch_athlete_detail(client, athlete_id, sport_path, league)
    except Exception as e:
        logger.debug(f"[COMBAT] get_fighter_profile failed for {name} ({sport_upper}): {e}")
        _cache[key] = (time.monotonic(), None)
        return None

    if not detail:
        _cache[key] = (time.monotonic(), None)
        return None

    # ESPN athlete detail structure varies; pull what we can find.
    record_str = ""
    records = detail.get("records") or detail.get("statistics") or []
    if isinstance(records, dict):
        record_str = records.get("displayValue", "") or ""
    elif isinstance(records, list):
        for rec in records:
            if isinstance(rec, dict) and rec.get("displayValue"):
                record_str = rec["displayValue"]
                break

    parsed = _parse_record(record_str)
    out = {
        "name": detail.get("displayName") or detail.get("fullName") or name,
        "record": record_str or None,
        "wins": parsed["wins"],
        "losses": parsed["losses"],
        "draws": parsed["draws"],
        "weight_class": (detail.get("weightClass") or {}).get("text") if isinstance(detail.get("weightClass"), dict) else detail.get("weightClass"),
        "stance": detail.get("stance"),
        "espn_id": detail.get("id"),
    }
    _cache[key] = (time.monotonic(), out)
    return out
