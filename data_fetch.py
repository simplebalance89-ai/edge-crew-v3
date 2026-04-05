"""
Edge Crew v3 — Data Fetch Layer
Pulls team profiles from ESPN for real grading data.

Strategy:
  1. Scoreboard — has full records for teams playing TODAY
  2. /teams list — get team ID, then /teams/{id} for full profile (ALL teams)
  3. Yesterday/2-day-ago scoreboard — rest days + B2B detection
  4. /teams/{id}/injuries — key player injury data
  5. /teams/{id}/schedule — L5 record + road trip length
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

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
    "MMA": ("mma", "ufc"),
    "BOXING": ("boxing", "boxing"),
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

# Cache: scoreboard by date+league (yesterday doesn't change)
_scoreboard_cache: Dict[str, dict] = {}
_SCOREBOARD_CACHE_TTL = 7200  # 2 hours for historical dates

# Cache: injuries by team_id
_injury_cache: Dict[str, dict] = {}
_INJURY_CACHE_TTL = 1800  # 30 min

# Cache: schedule by team_id
_schedule_cache: Dict[str, dict] = {}
_SCHEDULE_CACHE_TTL = 3600  # 1 hour

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
    """Fetch team profile from ESPN. Returns dict with record, ppg, rest, injuries, L5, etc."""
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
            team_id = None

            if team_data:
                profile.update(_extract_scoreboard_data(team_data, sport))
                team_id = str(team_data.get("team", {}).get("id", ""))
                logger.info(f"[ESPN] Scoreboard hit: {team_name} → {profile.get('record','?')}")
            else:
                # 2) Get team ID, then fetch /teams/{id} for full profile
                team_id = await _get_team_id(client, espn_sport, espn_league, team_name)
                if team_id:
                    detail = await _fetch_team_detail(client, espn_sport, espn_league, team_id, sport)
                    if detail:
                        profile.update(detail)
                        logger.info(f"[ESPN] Team detail hit: {team_name} → {profile.get('record','?')}")
                    else:
                        logger.warning(f"[ESPN] Team detail empty for {team_name} (id={team_id})")
                else:
                    logger.warning(f"[ESPN] No team ID found for '{team_name}'")

            # ── Rest days / B2B (uses cached yesterday scoreboards) ───
            rest_info = await _fetch_rest_days(client, espn_sport, espn_league, team_name)
            profile.update(rest_info)

            # ── Injuries + Schedule (parallel if we have team_id) ─────
            if team_id:
                inj_task = _fetch_injuries(client, espn_sport, espn_league, team_id)
                sched_task = _fetch_schedule_data(client, espn_sport, espn_league, team_id, team_name)
                injuries, schedule_data = await asyncio.gather(inj_task, sched_task)
                profile["injuries"] = injuries
                profile.update(schedule_data)

    except Exception as e:
        logger.warning(f"[ESPN] Fetch failed for {team_name}: {e}")

    profile["_fetched"] = datetime.now(timezone.utc)
    _team_cache[cache_key] = profile
    return profile


# ── ESPN API Calls ─────────────────────────────────────────────────────

async def _fetch_scoreboard(client: httpx.AsyncClient, sport: str, league: str,
                            date_str: str = "") -> dict:
    """Fetch scoreboard. date_str is YYYYMMDD or empty for today. Cached."""
    cache_key = f"{sport}/{league}/{date_str}"
    cached = _scoreboard_cache.get(cache_key)
    if cached:
        age = (datetime.now(timezone.utc) - cached.get("_ts", datetime.min.replace(tzinfo=timezone.utc))).total_seconds()
        ttl = _SCOREBOARD_CACHE_TTL if date_str else 300  # today = 5 min
        if age < ttl:
            return cached.get("data", {})

    url = f"{ESPN_BASE}/{sport}/{league}/scoreboard"
    params = {}
    if date_str:
        params["dates"] = date_str
    resp = await client.get(url, params=params)
    data = resp.json() if resp.status_code == 200 else {}
    _scoreboard_cache[cache_key] = {"data": data, "_ts": datetime.now(timezone.utc)}
    return data


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


async def _fetch_team_detail(client: httpx.AsyncClient, sport: str, league: str,
                              team_id: str, sport_label: str = "NBA") -> Optional[dict]:
    """Fetch /teams/{id} — has full record, ppg, home/away splits."""
    url = f"{ESPN_BASE}/{sport}/{league}/teams/{team_id}"
    resp = await client.get(url)
    if resp.status_code != 200:
        return None
    data = resp.json()
    team = data.get("team", {})
    return _extract_team_detail(team, sport_label)


# ── Rest Days / B2B ──────────────────────────────────────────────────

async def _fetch_rest_days(client: httpx.AsyncClient, sport: str, league: str,
                            team_name: str) -> dict:
    """Check yesterday and 2-days-ago scoreboard to determine rest days and B2B.
    Uses cached scoreboards so this adds 0 extra API calls after first fetch."""
    today = datetime.now(timezone.utc).date()
    yesterday = (today - timedelta(days=1)).strftime("%Y%m%d")
    two_days_ago = (today - timedelta(days=2)).strftime("%Y%m%d")

    result = {"rest_days": None, "is_b2b": False}

    # Check yesterday — if team played, it's a B2B
    sb_yesterday = await _fetch_scoreboard(client, sport, league, yesterday)
    if _find_team_in_scoreboard(sb_yesterday, team_name):
        result["rest_days"] = 1
        result["is_b2b"] = True
        return result

    # Check 2 days ago
    sb_2d = await _fetch_scoreboard(client, sport, league, two_days_ago)
    if _find_team_in_scoreboard(sb_2d, team_name):
        result["rest_days"] = 2
        result["is_b2b"] = False
        return result

    # 3+ days rest
    result["rest_days"] = 3
    result["is_b2b"] = False
    return result


# ── Injuries ──────────────────────────────────────────────────────────

async def _fetch_injuries(client: httpx.AsyncClient, sport: str, league: str,
                           team_id: str) -> List[dict]:
    """Fetch injuries from ESPN /teams/{id}/injuries endpoint. Cached."""
    cache_key = f"{sport}/{league}/{team_id}/injuries"
    cached = _injury_cache.get(cache_key)
    if cached:
        age = (datetime.now(timezone.utc) - cached.get("_ts", datetime.min.replace(tzinfo=timezone.utc))).total_seconds()
        if age < _INJURY_CACHE_TTL:
            return cached.get("data", [])

    injuries: List[dict] = []
    try:
        url = f"{ESPN_BASE}/{sport}/{league}/teams/{team_id}/injuries"
        resp = await client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            # ESPN injuries response has varying structures:
            # Structure A: { injuries: [ { athlete: {}, status: {} } ] }
            for item in data.get("injuries", []):
                athlete = item.get("athlete", {})
                status_obj = item.get("status", item.get("type", {}))
                if isinstance(status_obj, dict):
                    status_text = status_obj.get("description",
                                  status_obj.get("type", "Unknown"))
                else:
                    status_text = str(status_obj)
                injuries.append({
                    "player": athlete.get("displayName",
                              athlete.get("fullName", "Unknown")),
                    "status": status_text.upper() if status_text else "UNKNOWN",
                    "position": athlete.get("position", {}).get("abbreviation", ""),
                })
            # Structure B: { team: { injuries: [ { injuries: [...] } ] } }
            for group in data.get("team", {}).get("injuries", []):
                for entry in group.get("injuries", []):
                    athlete = entry.get("athlete", {})
                    status_text = entry.get("status", "Unknown")
                    if isinstance(status_text, dict):
                        status_text = status_text.get("description", "Unknown")
                    injuries.append({
                        "player": athlete.get("displayName",
                                  athlete.get("fullName", "Unknown")),
                        "status": status_text.upper() if status_text else "UNKNOWN",
                        "position": athlete.get("position", {}).get("abbreviation", ""),
                    })
    except Exception as e:
        logger.debug(f"[ESPN] Injury fetch failed for team {team_id}: {e}")

    # Deduplicate by player name
    seen = set()
    unique = []
    for inj in injuries:
        if inj["player"] not in seen:
            seen.add(inj["player"])
            unique.append(inj)
    injuries = unique

    _injury_cache[cache_key] = {"data": injuries, "_ts": datetime.now(timezone.utc)}
    if injuries:
        logger.info(f"[ESPN] Injuries for team {team_id}: {len(injuries)} entries")
    return injuries


# ── Schedule / L5 / Road Trip ────────────────────────────────────────

async def _fetch_schedule_data(client: httpx.AsyncClient, sport: str, league: str,
                                team_id: str, team_name: str) -> dict:
    """Fetch team schedule to derive L5 record, margin, and road trip length. Cached."""
    cache_key = f"{sport}/{league}/{team_id}/schedule"
    cached = _schedule_cache.get(cache_key)
    if cached:
        age = (datetime.now(timezone.utc) - cached.get("_ts", datetime.min.replace(tzinfo=timezone.utc))).total_seconds()
        if age < _SCHEDULE_CACHE_TTL:
            return cached.get("data", {})

    result = {"L5": "", "L5_margin": 0, "road_trip_len": 0, "home_stand_len": 0}

    try:
        url = f"{ESPN_BASE}/{sport}/{league}/teams/{team_id}/schedule"
        resp = await client.get(url)
        if resp.status_code != 200:
            _schedule_cache[cache_key] = {"data": result, "_ts": datetime.now(timezone.utc)}
            return result

        data = resp.json()
        events = data.get("events", [])

        # Filter to completed games
        completed = []
        for ev in events:
            # Check top-level status
            status_name = ev.get("status", {}).get("type", {}).get("name", "")
            if status_name in ("STATUS_FINAL", "STATUS_FULL_TIME"):
                completed.append(ev)
                continue
            # Check competition-level status
            comps = ev.get("competitions", [])
            if comps:
                comp_status = comps[0].get("status", {}).get("type", {}).get("name", "")
                if comp_status in ("STATUS_FINAL", "STATUS_FULL_TIME"):
                    completed.append(ev)

        # Sort by date descending (most recent first)
        completed.sort(key=lambda e: e.get("date", ""), reverse=True)

        # L5: last 5 completed games
        last5 = completed[:5]
        if last5:
            result.update(_calc_l5_record(last5, team_name))

        # Road trip / home stand
        result.update(_calc_trip_info(events, team_name))

    except Exception as e:
        logger.debug(f"[ESPN] Schedule fetch failed for team {team_id}: {e}")

    _schedule_cache[cache_key] = {"data": result, "_ts": datetime.now(timezone.utc)}
    return result


def _calc_l5_record(last5_events: list, team_name: str) -> dict:
    """Calculate W-L record and avg margin from last 5 completed games."""
    wins = 0
    losses = 0
    total_margin = 0

    for ev in last5_events:
        comps = ev.get("competitions", [])
        if not comps:
            continue
        comp = comps[0]
        our_team = None
        opp_team = None
        for c in comp.get("competitors", []):
            team = c.get("team", {})
            names = [
                team.get("displayName", ""),
                team.get("shortDisplayName", ""),
                team.get("name", ""),
                team.get("abbreviation", ""),
            ]
            if _name_match(team_name, names):
                our_team = c
            else:
                opp_team = c

        if our_team and opp_team:
            our_score = _safe_score(our_team)
            opp_score = _safe_score(opp_team)
            if our_score > opp_score:
                wins += 1
            else:
                losses += 1
            total_margin += (our_score - opp_score)

    count = max(wins + losses, 1)
    return {
        "L5": f"{wins}-{losses}",
        "L5_margin": round(total_margin / count, 1),
    }


def _safe_score(competitor: dict) -> int:
    """Extract numeric score from competitor, handling dict or string."""
    score = competitor.get("score", 0)
    if isinstance(score, dict):
        score = score.get("value", score.get("displayValue", 0))
    try:
        return int(float(str(score)))
    except (ValueError, TypeError):
        return 0


def _calc_trip_info(events: list, team_name: str) -> dict:
    """Calculate current road trip or home stand length from schedule."""
    today = datetime.now(timezone.utc).date()
    result = {"road_trip_len": 0, "home_stand_len": 0}

    # Gather home/away for games around today
    relevant = []
    for ev in events:
        try:
            ev_date = datetime.fromisoformat(
                ev.get("date", "").replace("Z", "+00:00")
            ).date()
        except (ValueError, AttributeError):
            continue
        if abs((ev_date - today).days) > 10:
            continue
        comps = ev.get("competitions", [])
        if not comps:
            continue
        for c in comps[0].get("competitors", []):
            team = c.get("team", {})
            names = [
                team.get("displayName", ""),
                team.get("shortDisplayName", ""),
                team.get("name", ""),
                team.get("abbreviation", ""),
            ]
            if _name_match(team_name, names):
                relevant.append({
                    "date": ev_date,
                    "is_home": c.get("homeAway", "") == "home",
                })

    relevant.sort(key=lambda x: x["date"])

    # Walk backward from today to find consecutive home or away streak
    consecutive_away = 0
    consecutive_home = 0
    for game in reversed(relevant):
        if game["date"] > today:
            continue
        if game["is_home"]:
            if consecutive_away == 0:
                consecutive_home += 1
            else:
                break
        else:
            if consecutive_home == 0:
                consecutive_away += 1
            else:
                break

    # Extend forward (upcoming games on same trip)
    for game in relevant:
        if game["date"] <= today:
            continue
        if consecutive_away > 0 and not game["is_home"]:
            consecutive_away += 1
        elif consecutive_home > 0 and game["is_home"]:
            consecutive_home += 1
        else:
            break

    result["road_trip_len"] = consecutive_away
    result["home_stand_len"] = consecutive_home
    return result


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

def _extract_scoreboard_data(data: dict, sport: str = "NBA") -> dict:
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
    _derive_ppg_from_record(profile, sport)
    return profile


def _extract_team_detail(team: dict, sport: str = "NBA") -> dict:
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
                elif sname in ("avgpointsfor", "avgPointsFor"):
                    try:
                        profile["ppg_L5"] = round(float(sval), 1)
                    except (ValueError, TypeError):
                        pass
                elif sname in ("avgpointsagainst", "avgPointsAgainst"):
                    try:
                        profile["opp_ppg_L5"] = round(float(sval), 1)
                    except (ValueError, TypeError):
                        pass
                elif sname in ("gamesplayed", "gamesPlayed"):
                    try:
                        profile["_gamesPlayed"] = int(float(sval))
                    except (ValueError, TypeError):
                        pass
                elif sname in ("pointsfor", "pointsFor"):
                    try:
                        profile["_pointsFor"] = float(sval)
                    except (ValueError, TypeError):
                        pass
                elif sname in ("pointsagainst", "pointsAgainst"):
                    try:
                        profile["_pointsAgainst"] = float(sval)
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

    _derive_ppg_from_record(profile, sport)
    return profile


# ── Helpers ────────────────────────────────────────────────────────────

def _games_from_record(record: str) -> int:
    try:
        return sum(int(p) for p in record.split("-"))
    except (ValueError, AttributeError):
        return 0


def _derive_ppg_from_record(profile: dict, sport: str = "NBA") -> None:
    """Fill win_pct-derived PPG from record if ppg is still missing.
    Sport-specific PPG ranges so soccer doesn't get NBA-scale numbers.
    """
    if not profile.get("record"):
        return
    try:
        parts = profile["record"].split("-")
        w, l = int(parts[0]), int(parts[1])
        total = w + l
        if total > 0 and not profile.get("ppg_L5"):
            pct = w / total
            # Sport-specific PPG derivation from win%
            PPG_RANGES = {
                "SOCCER": (0.8, 1.5),    # goals/game: 0.8 - 2.3
                "NHL":    (2.0, 1.5),     # goals/game: 2.0 - 3.5
                "MLB":    (3.5, 2.5),     # runs/game:  3.5 - 6.0
                "NBA":    (95.0, 25.0),   # points:     95 - 120
                "NFL":    (17.0, 10.0),   # points:     17 - 27
                "NCAAB":  (60.0, 20.0),   # points:     60 - 80
            }
            base, span = PPG_RANGES.get(sport, PPG_RANGES["NBA"])
            profile["ppg_L5"] = round(base + pct * span, 1)
            profile["opp_ppg_L5"] = round(base + span - pct * span, 1)
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
        "L5_margin": 0,
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
        "injuries": [],
    }


async def enrich_game_for_grading(game_data: dict, sport: str, odds_key: str = "") -> dict:
    home = game_data.get("homeTeam", "")
    away = game_data.get("awayTeam", "")
    home_profile, away_profile = await asyncio.gather(
        fetch_team_profile(home, sport, odds_key),
        fetch_team_profile(away, sport, odds_key),
    )
    odds = game_data.get("odds", {})

    # Pull injuries from profiles for the grade engine
    home_injuries = home_profile.get("injuries", [])
    away_injuries = away_profile.get("injuries", [])
    home_out = [i for i in home_injuries if i.get("status") in ("OUT", "DOUBTFUL")]
    away_out = [i for i in away_injuries if i.get("status") in ("OUT", "DOUBTFUL")]

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
        "injuries": {
            "home": home_injuries,
            "away": away_injuries,
            "home_out": home_out,
            "away_out": away_out,
            "home_out_count": len(home_out),
            "away_out_count": len(away_out),
        },
        "rest": {
            "home_rest_days": home_profile.get("rest_days"),
            "away_rest_days": away_profile.get("rest_days"),
            "home_b2b": home_profile.get("is_b2b", False),
            "away_b2b": away_profile.get("is_b2b", False),
        },
        "shifts": game_data.get("shifts", {}),
    }
