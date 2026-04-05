"""
Edge Crew v3 — Data Fetch Layer
Pulls team profiles from ESPN for real grading data.
Caches aggressively to stay within rate limits.
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
    "SOCCER": ("soccer", "usa.1"),  # MLS default, override per league
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


async def fetch_team_profile(team_name: str, sport: str, odds_key: str = "") -> dict:
    """Fetch team profile from ESPN. Returns dict with record, form, etc."""
    cache_key = f"{sport}:{team_name}"
    cached = _team_cache.get(cache_key)
    if cached:
        age = (datetime.now(timezone.utc) - cached["_fetched"]).total_seconds()
        if age < TEAM_CACHE_TTL:
            return cached

    # Determine ESPN sport/league
    if sport == "SOCCER" and odds_key:
        espn_sport, espn_league = SOCCER_LEAGUE_MAP.get(odds_key, ("soccer", "usa.1"))
    else:
        espn_sport, espn_league = SPORT_ESPN_MAP.get(sport, ("basketball", "nba"))

    profile = _default_profile(team_name)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Fetch scoreboard for today's context
            scoreboard = await _fetch_scoreboard(client, espn_sport, espn_league)
            team_data = _find_team_in_scoreboard(scoreboard, team_name)

            if team_data:
                profile.update(_extract_team_data(team_data, sport))

            # Try standings for record data
            standings = await _fetch_standings(client, espn_sport, espn_league)
            standing = _find_team_in_standings(standings, team_name)
            if standing:
                profile.update(_extract_standings_data(standing))

    except Exception as e:
        logger.warning(f"ESPN fetch failed for {team_name}: {e}")

    profile["_fetched"] = datetime.now(timezone.utc)
    _team_cache[cache_key] = profile
    return profile


async def _fetch_scoreboard(client: httpx.AsyncClient, sport: str, league: str) -> dict:
    url = f"{ESPN_BASE}/{sport}/{league}/scoreboard"
    resp = await client.get(url)
    return resp.json() if resp.status_code == 200 else {}


async def _fetch_standings(client: httpx.AsyncClient, sport: str, league: str) -> dict:
    url = f"{ESPN_BASE}/{sport}/{league}/standings"
    resp = await client.get(url)
    return resp.json() if resp.status_code == 200 else {}


def _find_team_in_scoreboard(data: dict, team_name: str) -> Optional[dict]:
    """Find team data in ESPN scoreboard response."""
    tn = team_name.lower().strip()
    for event in data.get("events", []):
        for comp in event.get("competitions", []):
            for competitor in comp.get("competitors", []):
                team = competitor.get("team", {})
                names = [
                    team.get("displayName", "").lower(),
                    team.get("shortDisplayName", "").lower(),
                    team.get("name", "").lower(),
                    team.get("abbreviation", "").lower(),
                ]
                if any(tn in n or n in tn for n in names if n):
                    return {
                        "competitor": competitor,
                        "team": team,
                        "event": event,
                        "competition": comp,
                    }
    return None


def _find_team_in_standings(data: dict, team_name: str) -> Optional[dict]:
    """Find team in ESPN standings response."""
    tn = team_name.lower().strip()
    for group in data.get("children", []):
        for standing in group.get("standings", {}).get("entries", []):
            team = standing.get("team", {})
            names = [
                team.get("displayName", "").lower(),
                team.get("shortDisplayName", "").lower(),
                team.get("name", "").lower(),
            ]
            if any(tn in n or n in tn for n in names if n):
                return standing
    # Flat standings (some leagues)
    for entry in data.get("standings", {}).get("entries", []):
        team = entry.get("team", {})
        names = [
            team.get("displayName", "").lower(),
            team.get("shortDisplayName", "").lower(),
            team.get("name", "").lower(),
        ]
        if any(tn in n or n in tn for n in names if n):
            return entry
    return None


def _extract_team_data(data: dict, sport: str) -> dict:
    """Extract profile fields from scoreboard competitor data."""
    comp = data["competitor"]
    records = comp.get("records", [])
    profile = {}

    # Overall record
    for rec in records:
        if rec.get("type") == "total" or rec.get("name") == "overall":
            profile["record"] = rec.get("summary", "")
        elif rec.get("type") == "home" or rec.get("name") == "Home":
            profile["home_record"] = rec.get("summary", "")
        elif rec.get("type") == "road" or rec.get("name") == "Road":
            profile["away_record"] = rec.get("summary", "")

    # If no split records, try to parse from statistics
    stats = {}
    for stat in comp.get("statistics", []):
        stats[stat.get("name", "")] = stat.get("displayValue", stat.get("value"))

    if stats:
        profile["_raw_stats"] = stats

    return profile


def _extract_standings_data(entry: dict) -> dict:
    """Extract standings data into profile format."""
    profile = {}
    stats = {}
    for stat in entry.get("stats", []):
        name = stat.get("name", "") or stat.get("abbreviation", "")
        val = stat.get("value", stat.get("displayValue"))
        if name:
            stats[name.lower()] = val

    # Map ESPN stats to our profile fields
    if "wins" in stats and "losses" in stats:
        w = int(stats["wins"])
        l = int(stats["losses"])
        profile["record"] = f"{w}-{l}"

    if "streak" in stats:
        profile["streak"] = str(stats["streak"])

    if "pointsfor" in stats or "pointsFor" in stats:
        pf = float(stats.get("pointsfor", stats.get("pointsFor", 0)))
        games = int(stats.get("gamesplayed", stats.get("gamesPlayed", 82)))
        if games > 0:
            profile["ppg_L5"] = round(pf / games, 1)

    if "pointsagainst" in stats or "pointsAgainst" in stats:
        pa = float(stats.get("pointsagainst", stats.get("pointsAgainst", 0)))
        games = int(stats.get("gamesplayed", stats.get("gamesPlayed", 82)))
        if games > 0:
            profile["opp_ppg_L5"] = round(pa / games, 1)

    if "playoffseed" in stats:
        profile["league_position"] = int(stats["playoffseed"])

    if "differential" in stats:
        try:
            profile["avg_margin_L10"] = round(float(stats["differential"]) / max(1, int(stats.get("gamesplayed", 82))) * 10, 1)
        except (ValueError, TypeError):
            pass

    profile["_standings_stats"] = stats
    return profile


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
    """
    Take a parsed odds game and enrich it with team profiles for grading.
    Returns a game dict ready for grade_engine.grade_both_sides().
    """
    home = game_data.get("homeTeam", "")
    away = game_data.get("awayTeam", "")

    home_profile = await fetch_team_profile(home, sport, odds_key)
    away_profile = await fetch_team_profile(away, sport, odds_key)

    # Build the game dict the grade engine expects
    odds = game_data.get("odds", {})
    return {
        "game_id": game_data.get("id", ""),
        "sport": sport,
        "home": home,
        "away": away,
        "home_team": home,
        "away_team": away,
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
