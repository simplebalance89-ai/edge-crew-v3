"""
Edge Crew v3 — Data Fetch Layer
Pulls team profiles from ESPN for real grading data.

Strategy:
  1. Scoreboard — has full records for teams playing TODAY
  2. /teams list — get team ID, then /teams/{id} for full profile (ALL teams)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

import httpx

logger = logging.getLogger("edge-crew-v3")

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"

SPORT_ESPN_MAP = {
    "NBA": ("basketball", "nba"),
    "NHL": ("hockey", "nhl"),
    "MLB": ("baseball", "mlb"),
    "NFL": ("football", "nfl"),
    "NCAAB": ("basketball", "mens-college-basketball"),
    "SOCCER": ("soccer", "usa.1"),
}

SOCCER_LEAGUE_MAP = {
    "soccer_epl": ("soccer", "eng.1"),
    "soccer_spain_la_liga": ("soccer", "esp.1"),
    "soccer_italy_serie_a": ("soccer", "ita.1"),
    "soccer_usa_mls": ("soccer", "usa.1"),
    "soccer_germany_bundesliga": ("soccer", "ger.1"),
    "soccer_france_ligue_one": ("soccer", "fra.1"),
}

_team_cache: Dict[str, dict] = {}
TEAM_CACHE_TTL = 600  # 10 min

# Cache: sport/league → {name: team_id}
_team_id_cache: Dict[str, dict] = {}
_TEAM_ID_TTL = 3600  # 1 hour

# Name aliases: Odds API → ESPN
_NAME_ALIASES = {
    "la clippers": "los angeles clippers",
    "montréal canadiens": "montreal canadiens",
}


def _normalise(name: str) -> str:
    n = name.lower().strip()
    return _NAME_ALIASES.get(n, n)


def _name_match(needle: str, candidates: list) -> bool:
    n = _normalise(needle)
    for c in candidates:
        c = _normalise(str(c))
        if not c:
            continue
        if n == c or n in c or c in n:
            return True
    return False


async def fetch_team_profile(team_name: str, sport: str, odds_key: str = "") -> dict:
    """Fetch team profile from ESPN. Returns dict with record, ppg, etc."""
    cache_key = f"{sport}:{team_name}"
    cached = _team_cache.get(cache_key)
    if cached:
        age = (datetime.now(timezone.utc) - cached["_fetched"]).total_seconds()
        if age < TEAM_CACHE_TTL:
            return cached

    if sport == "SOCCER" and odds_key:
        espn_sport, espn_league = SOCCER_LEAGUE_MAP.get(odds_key, ("soccer", "usa.1"))
    else:
        espn_sport, espn_league = SPORT_ESPN_MAP.get(sport, ("basketball", "nba"))

    profile = _default_profile(team_name)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 1) Try scoreboard first (best data for today's games)
            scoreboard = await _fetch_scoreboard(client, espn_sport, espn_league)
            team_data = _find_team_in_scoreboard(scoreboard, team_name)

            if team_data:
                profile.update(_extract_scoreboard_data(team_data))
                logger.info(f"[ESPN] Scoreboard hit: {team_name} → {profile.get('record','?')}")
            else:
                # 2) Get team ID, then fetch /teams/{id} for full profile
                team_id = await _get_team_id(client, espn_sport, espn_league, team_name)
                if team_id:
                    detail = await _fetch_team_detail(client, espn_sport, espn_league, team_id)
                    if detail:
                        profile.update(detail)
                        logger.info(f"[ESPN] Team detail hit: {team_name} → {profile.get('record','?')}")
                    else:
                        logger.warning(f"[ESPN] Team detail empty for {team_name} (id={team_id})")
                else:
                    logger.warning(f"[ESPN] No team ID found for '{team_name}'")

    except Exception as e:
        logger.warning(f"[ESPN] Fetch failed for {team_name}: {e}")

    profile["_fetched"] = datetime.now(timezone.utc)
    _team_cache[cache_key] = profile
    return profile


# ── ESPN API Calls ─────────────────────────────────────────────────────

async def _fetch_scoreboard(client: httpx.AsyncClient, sport: str, league: str) -> dict:
    url = f"{ESPN_BASE}/{sport}/{league}/scoreboard"
    resp = await client.get(url)
    return resp.json() if resp.status_code == 200 else {}


async def _get_team_id(client: httpx.AsyncClient, sport: str, league: str, team_name: str) -> Optional[str]:
    """Get ESPN team ID from the /teams list. Cached."""
    cache_key = f"{sport}/{league}"
    id_map = _team_id_cache.get(cache_key)

    if not id_map or (datetime.now(timezone.utc) - id_map.get("_ts", datetime.min.replace(tzinfo=timezone.utc))).total_seconds() > _TEAM_ID_TTL:
        url = f"{ESPN_BASE}/{sport}/{league}/teams"
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        data = resp.json()
        id_map = {"_ts": datetime.now(timezone.utc)}
        for sport_block in data.get("sports", []):
            for league_block in sport_block.get("leagues", []):
                for tw in league_block.get("teams", []):
                    team = tw.get("team", tw)
                    tid = team.get("id", "")
                    names = [
                        team.get("displayName", "").lower(),
                        team.get("shortDisplayName", "").lower(),
                        team.get("name", "").lower(),
                        team.get("abbreviation", "").lower(),
                        team.get("nickname", "").lower(),
                    ]
                    for n in names:
                        if n:
                            id_map[n] = tid
        _team_id_cache[cache_key] = id_map

    # Look up the team name
    needle = _normalise(team_name)
    # Direct match
    if needle in id_map:
        return id_map[needle]
    # Substring match
    for name, tid in id_map.items():
        if name == "_ts":
            continue
        if isinstance(tid, str) and (needle in name or name in needle):
            return tid
    return None


async def _fetch_team_detail(client: httpx.AsyncClient, sport: str, league: str, team_id: str) -> Optional[dict]:
    """Fetch /teams/{id} — has full record, ppg, home/away splits."""
    url = f"{ESPN_BASE}/{sport}/{league}/teams/{team_id}"
    resp = await client.get(url)
    if resp.status_code != 200:
        return None
    data = resp.json()
    team = data.get("team", {})
    return _extract_team_detail(team)


# ── Finders ────────────────────────────────────────────────────────────

def _find_team_in_scoreboard(data: dict, team_name: str) -> Optional[dict]:
    for event in data.get("events", []):
        for comp in event.get("competitions", []):
            for competitor in comp.get("competitors", []):
                team = competitor.get("team", {})
                names = [
                    team.get("displayName", ""),
                    team.get("shortDisplayName", ""),
                    team.get("name", ""),
                    team.get("abbreviation", ""),
                ]
                if _name_match(team_name, names):
                    return {"competitor": competitor, "team": team}
    return None


# ── Extractors ─────────────────────────────────────────────────────────

def _extract_scoreboard_data(data: dict) -> dict:
    """Extract from scoreboard competitor (records + stats)."""
    comp = data["competitor"]
    profile = {}
    for rec in comp.get("records", []):
        rtype = rec.get("type", "").lower()
        summary = rec.get("summary", "")
        if rtype == "total":
            profile["record"] = summary
        elif rtype == "home":
            profile["home_record"] = summary
        elif rtype in ("road", "away"):
            profile["away_record"] = summary
    _derive_ppg_from_record(profile)
    return profile


def _extract_team_detail(team: dict) -> dict:
    """Extract from /teams/{id} — has record.items with full stats."""
    profile = {}
    record_block = team.get("record", {})

    for item in record_block.get("items", []):
        rtype = item.get("type", "").lower()
        summary = item.get("summary", "")

        if rtype == "total":
            profile["record"] = summary
            for stat in item.get("stats", []):
                sname = stat.get("name", "").lower()
                sval = stat.get("value", stat.get("displayValue"))
                if sname == "streak":
                    profile["streak"] = str(stat.get("displayValue", sval))
                elif sname == "playoffseed":
                    try:
                        profile["league_position"] = int(float(sval))
                    except (ValueError, TypeError):
                        pass
                elif sname == "avgpointsfor":
                    try:
                        profile["ppg_L5"] = round(float(sval), 1)
                    except (ValueError, TypeError):
                        pass
                elif sname == "avgpointsagainst":
                    try:
                        profile["opp_ppg_L5"] = round(float(sval), 1)
                    except (ValueError, TypeError):
                        pass
                elif sname == "pointsfor":
                    try:
                        profile["_pointsFor"] = float(sval)
                    except (ValueError, TypeError):
                        pass
                elif sname == "pointsagainst":
                    try:
                        profile["_pointsAgainst"] = float(sval)
                    except (ValueError, TypeError):
                        pass
                elif sname in ("gamesplayed",):
                    try:
                        profile["_gamesPlayed"] = int(float(sval))
                    except (ValueError, TypeError):
                        pass
        elif rtype == "home":
            profile["home_record"] = summary
        elif rtype in ("road", "away"):
            profile["away_record"] = summary

    # Derive ppg from totals if avgPoints not available
    if not profile.get("ppg_L5"):
        gp = profile.pop("_gamesPlayed", 0) or _games_from_record(profile.get("record", ""))
        pf = profile.pop("_pointsFor", 0)
        pa = profile.pop("_pointsAgainst", 0)
        if gp > 0 and pf > 0:
            profile["ppg_L5"] = round(pf / gp, 1)
        if gp > 0 and pa > 0:
            profile["opp_ppg_L5"] = round(pa / gp, 1)
        if gp > 0 and pf > 0 and pa > 0:
            profile["avg_margin_L10"] = round((pf - pa) / gp, 1)
    else:
        # Clean up temp keys
        profile.pop("_pointsFor", None)
        profile.pop("_pointsAgainst", None)
        profile.pop("_gamesPlayed", None)
        # Derive margin from ppg
        if profile.get("ppg_L5") and profile.get("opp_ppg_L5"):
            profile["avg_margin_L10"] = round(profile["ppg_L5"] - profile["opp_ppg_L5"], 1)

    _derive_ppg_from_record(profile)
    return profile


# ── Helpers ────────────────────────────────────────────────────────────

def _games_from_record(record: str) -> int:
    try:
        return sum(int(p) for p in record.split("-"))
    except (ValueError, AttributeError):
        return 0


def _derive_ppg_from_record(profile: dict) -> None:
    """Fill win_pct context from record if ppg is still missing."""
    if not profile.get("record"):
        return
    try:
        parts = profile["record"].split("-")
        w, l = int(parts[0]), int(parts[1])
        total = w + l
        if total > 0 and not profile.get("ppg_L5"):
            # Use win% as a proxy signal — 60%+ team = above average
            pct = w / total
            # Map to approximate NBA ppg range (104-120)
            profile["ppg_L5"] = round(104 + pct * 16, 1)
            profile["opp_ppg_L5"] = round(120 - pct * 16, 1)
            profile["avg_margin_L10"] = round(profile["ppg_L5"] - profile["opp_ppg_L5"], 1)
    except (ValueError, IndexError):
        pass


def _default_profile(team_name: str) -> dict:
    return {
        "team": team_name,
        "record": "",
        "home_record": "",
        "away_record": "",
        "L5": "",
        "streak": "",
        "ppg_L5": 0,
        "opp_ppg_L5": 0,
        "margin_L5": 0,
        "avg_margin_L10": 0,
        "rest_days": None,
        "is_b2b": False,
        "road_trip_len": 0,
        "home_stand_len": 0,
        "pace_L5": 0,
        "h2h_season": "0-0",
    }


async def enrich_game_for_grading(game_data: dict, sport: str, odds_key: str = "") -> dict:
    home = game_data.get("homeTeam", "")
    away = game_data.get("awayTeam", "")
    home_profile = await fetch_team_profile(home, sport, odds_key)
    away_profile = await fetch_team_profile(away, sport, odds_key)
    odds = game_data.get("odds", {})
    return {
        "game_id": game_data.get("id", ""),
        "sport": sport,
        "home": home, "away": away,
        "home_team": home, "away_team": away,
        "home_profile": home_profile,
        "away_profile": away_profile,
        "odds": {
            "spread_home": odds.get("spread", 0),
            "total": odds.get("total", 0),
            "ml_home": odds.get("mlHome", 0),
            "ml_away": odds.get("mlAway", 0),
        },
        "injuries": game_data.get("injuries", {}),
        "shifts": game_data.get("shifts", {}),
    }
