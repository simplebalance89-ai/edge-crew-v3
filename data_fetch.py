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


async def fetch_team_profile(team_name: str, sport: str, odds_key: str = "",
                             opponent_name: str = "") -> dict:
    """Fetch team profile from ESPN. Returns dict with record, ppg, rest, injuries, L5, etc."""
    cache_key = f"{sport}:{team_name}"
    cached = _team_cache.get(cache_key)
    if cached:
        age = (datetime.now(timezone.utc) - cached["_fetched"]).total_seconds()
        if age < TEAM_CACHE_TTL:
            # Return a shallow copy and clear starting_pitcher — that field is
            # game-specific and must be attached per-game by the caller
            # (see enrich_game_for_grading). Caching it here causes the wrong
            # pitcher to leak across different games of the same team.
            result = dict(cached)
            result["starting_pitcher"] = {}
            return result

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
                sched_task = _fetch_schedule_data(client, espn_sport, espn_league, team_id, team_name, opponent_name)
                injuries, schedule_data = await asyncio.gather(inj_task, sched_task)
                profile["injuries"] = injuries
                profile.update(schedule_data)

    except Exception as e:
        logger.warning(f"[ESPN] Fetch failed for {team_name}: {e}")

    profile["_fetched"] = datetime.now(timezone.utc)
    # Strip starting_pitcher before caching — it is event-specific and must
    # be attached per-game by enrich_game_for_grading. Keep a local copy on
    # the returned profile so the first call (which populated the cache from
    # today's scoreboard) still has a sensible value.
    sp_local = profile.get("starting_pitcher") or {}
    cache_entry = dict(profile)
    cache_entry["starting_pitcher"] = {}
    _team_cache[cache_key] = cache_entry
    profile["starting_pitcher"] = sp_local
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
    """Fetch injuries from ESPN core API + follow $refs. Cached."""
    cache_key = f"{sport}/{league}/{team_id}/injuries"
    cached = _injury_cache.get(cache_key)
    if cached:
        age = (datetime.now(timezone.utc) - cached.get("_ts", datetime.min.replace(tzinfo=timezone.utc))).total_seconds()
        if age < _INJURY_CACHE_TTL:
            return cached.get("data", [])

    injuries: List[dict] = []
    try:
        # Core API returns rich injury data with $refs (the site API returns {})
        list_url = f"http://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/teams/{team_id}/injuries?limit=30"
        resp = await client.get(list_url)
        if resp.status_code != 200:
            _injury_cache[cache_key] = {"data": [], "_ts": datetime.now(timezone.utc)}
            return []
        list_data = resp.json()
        items = list_data.get("items", [])
        if not items:
            _injury_cache[cache_key] = {"data": [], "_ts": datetime.now(timezone.utc)}
            return []

        # Fetch all injury details in parallel
        detail_urls = [it.get("$ref") for it in items if it.get("$ref")]
        detail_tasks = [client.get(u) for u in detail_urls]
        detail_resps = await asyncio.gather(*detail_tasks, return_exceptions=True)

        # For each injury detail, also fetch the athlete name in parallel
        injury_records = []
        athlete_url_to_idx: dict = {}
        athlete_urls: list = []
        for r in detail_resps:
            if isinstance(r, Exception) or r.status_code != 200:
                continue
            try:
                d = r.json()
            except Exception:
                continue
            status_text = d.get("status", "Unknown") or "Unknown"
            type_obj = d.get("type", {}) or {}
            if not status_text or status_text == "Unknown":
                status_text = type_obj.get("description", "Unknown")
            short_comment = d.get("shortComment", "") or ""
            details = d.get("details", {}) or {}
            inj_type = details.get("type", "")
            return_date = details.get("returnDate", "")
            athlete_ref = (d.get("athlete") or {}).get("$ref", "")
            idx = len(injury_records)
            injury_records.append({
                "player": "Unknown",  # filled in after athlete fetch
                "status": status_text.upper().replace(" ", "_"),
                "position": "",
                "ppg": 0,
                "injury_type": inj_type,
                "return_date": return_date,
                "comment": short_comment,
            })
            if athlete_ref:
                athlete_url_to_idx.setdefault(athlete_ref, []).append(idx)
                if athlete_ref not in athlete_urls:
                    athlete_urls.append(athlete_ref)

        # Fetch athletes in parallel
        if athlete_urls:
            athlete_tasks = [client.get(u) for u in athlete_urls]
            athlete_resps = await asyncio.gather(*athlete_tasks, return_exceptions=True)
            for url, ar in zip(athlete_urls, athlete_resps):
                if isinstance(ar, Exception) or ar.status_code != 200:
                    continue
                try:
                    a = ar.json()
                except Exception:
                    continue
                name = a.get("displayName") or a.get("fullName") or "Unknown"
                pos = ((a.get("position") or {}).get("abbreviation") or "")
                for idx in athlete_url_to_idx.get(url, []):
                    injury_records[idx]["player"] = name
                    injury_records[idx]["position"] = pos

        # Normalize status: "OUT" / "DOUBTFUL" / "QUESTIONABLE" / "DAY_TO_DAY"
        for r in injury_records:
            s = (r.get("status") or "").upper()
            if s in ("OUT", "OUT_INDEFINITELY"):
                r["status"] = "OUT"
            elif "DOUBT" in s:
                r["status"] = "DOUBTFUL"
            elif "QUESTION" in s:
                r["status"] = "QUESTIONABLE"
            elif "DAY" in s:
                r["status"] = "DAY_TO_DAY"

        injuries = injury_records
    except Exception as e:
        logger.warning(f"[ESPN] Injury fetch failed for team {team_id}: {type(e).__name__}: {str(e)[:120]}")

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
                                team_id: str, team_name: str,
                                opponent_name: str = "") -> dict:
    """Fetch team schedule to derive L5 record, margin, road trip, H2H, and congestion. Cached."""
    cache_key = f"{sport}/{league}/{team_id}/schedule"
    cached = _schedule_cache.get(cache_key)
    if cached:
        age = (datetime.now(timezone.utc) - cached.get("_ts", datetime.min.replace(tzinfo=timezone.utc))).total_seconds()
        if age < _SCHEDULE_CACHE_TTL:
            base = cached.get("data", {})
            # H2H needs opponent context — compute on-the-fly from cached events
            if opponent_name and cached.get("events"):
                base["h2h_season"] = _calc_h2h(cached["events"], team_name, opponent_name)
            return base

    result = {"L5": "", "L5_margin": 0, "road_trip_len": 0, "home_stand_len": 0,
              "h2h_season": "0-0", "matches_in_10d": 0}

    raw_events = []
    try:
        url = f"{ESPN_BASE}/{sport}/{league}/teams/{team_id}/schedule"
        resp = await client.get(url)
        if resp.status_code != 200:
            _schedule_cache[cache_key] = {"data": result, "_ts": datetime.now(timezone.utc)}
            return result

        data = resp.json()
        events = data.get("events", [])
        raw_events = events

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

        # H2H season record
        if opponent_name:
            result["h2h_season"] = _calc_h2h(events, team_name, opponent_name)

        # Fixture congestion (matches in +/- 10 days)
        result["matches_in_10d"] = _calc_congestion(events)

    except Exception as e:
        logger.debug(f"[ESPN] Schedule fetch failed for team {team_id}: {e}")

    _schedule_cache[cache_key] = {"data": result, "events": raw_events, "_ts": datetime.now(timezone.utc)}
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


# ── H2H Season Record ────────────────────────────────────────────────

def _calc_h2h(events: list, team_name: str, opponent_name: str) -> str:
    """Calculate H2H season record from completed schedule events.
    Returns W-L string like '2-1'."""
    wins = 0
    losses = 0
    for ev in events:
        # Must be completed
        status_name = ev.get("status", {}).get("type", {}).get("name", "")
        comps = ev.get("competitions", [])
        if comps:
            comp_status = comps[0].get("status", {}).get("type", {}).get("name", "")
        else:
            comp_status = ""
        if status_name not in ("STATUS_FINAL", "STATUS_FULL_TIME") and \
           comp_status not in ("STATUS_FINAL", "STATUS_FULL_TIME"):
            continue

        if not comps:
            continue
        comp = comps[0]
        our_team = None
        opp_team = None
        is_h2h_game = False
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
            elif _name_match(opponent_name, names):
                opp_team = c
                is_h2h_game = True

        if our_team and opp_team and is_h2h_game:
            our_score = _safe_score(our_team)
            opp_score = _safe_score(opp_team)
            if our_score > opp_score:
                wins += 1
            elif opp_score > our_score:
                losses += 1

    if wins + losses == 0:
        return "0-0"
    return f"{wins}-{losses}"


# ── Fixture Congestion (Soccer) ──────────────────────────────────────

def _calc_congestion(events: list) -> int:
    """Count matches within 10 days before and after today from schedule events."""
    today = datetime.now(timezone.utc).date()
    count = 0
    for ev in events:
        try:
            ev_date = datetime.fromisoformat(
                ev.get("date", "").replace("Z", "+00:00")
            ).date()
        except (ValueError, AttributeError):
            continue
        days_diff = (ev_date - today).days
        if -10 <= days_diff <= 10 and days_diff != 0:
            count += 1
    return count


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
                    return {"competitor": competitor, "team": team, "competition": comp}
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

    # ── Pace proxy (NBA/NCAAB) ──
    if sport in ("NBA", "NCAAB") and profile.get("ppg_L5") and profile.get("opp_ppg_L5"):
        profile["pace_L5"] = round(profile["ppg_L5"] + profile["opp_ppg_L5"], 1)

    # ── Starting Pitcher (MLB) — extract from competition probables ──
    if sport == "MLB":
        competition = data.get("competition", {})
        # ESPN puts probables on each competitor
        probables = comp.get("probables", [])
        if probables:
            for prob in probables:
                athlete = prob.get("athlete", {})
                if athlete:
                    sp_info = {"name": athlete.get("displayName", athlete.get("fullName", "Unknown"))}
                    # Try to get ERA from athlete stats
                    for stat_block in athlete.get("statistics", []):
                        for stat in stat_block.get("stats", []):
                            pass  # ESPN stats are positional
                        # Sometimes stats is a flat list with names
                        splits = stat_block.get("splits", {})
                        for cat in splits.get("categories", []):
                            for s in cat.get("stats", []):
                                if s.get("name", "").lower() == "era":
                                    sp_info["era"] = s.get("displayValue", s.get("value"))
                    profile["starting_pitcher"] = sp_info
                    break
        # Fallback: check competition-level probables
        if not profile.get("starting_pitcher") or not profile["starting_pitcher"].get("name"):
            for c in competition.get("competitors", []):
                c_team = c.get("team", {})
                c_id = str(c_team.get("id", ""))
                comp_team_id = str(data.get("team", {}).get("id", ""))
                if c_id == comp_team_id or _name_match(
                        c_team.get("displayName", ""),
                        [data.get("team", {}).get("displayName", "")]):
                    for prob in c.get("probables", []):
                        athlete = prob.get("athlete", {})
                        if athlete:
                            sp_info = {"name": athlete.get("displayName", "Unknown")}
                            stats = athlete.get("stats", [])
                            # ESPN sometimes has stats as flat array: [W, L, ERA, ...]
                            if len(stats) >= 3:
                                try:
                                    sp_info["era"] = float(stats[2])
                                except (ValueError, TypeError, IndexError):
                                    pass
                            profile["starting_pitcher"] = sp_info
                            break

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

    # ── Pace proxy (NBA/NCAAB): pace_L5 = team_ppg + opp_ppg ──
    if sport in ("NBA", "NCAAB") and profile.get("ppg_L5") and profile.get("opp_ppg_L5"):
        profile["pace_L5"] = round(profile["ppg_L5"] + profile["opp_ppg_L5"], 1)

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
        "matches_in_10d": 0,
        "starting_pitcher": {},
        "injuries": [],
    }


async def _fetch_mlb_starting_pitchers(home: str, away: str) -> dict:
    """Fetch today's MLB scoreboard and return {'home': sp_dict, 'away': sp_dict}
    for the SPECIFIC event matching home vs away. This is fetched per-game
    (not cached on the team profile) so the same team in different games gets
    the correct pitcher for each game.
    """
    out = {"home": {}, "away": {}}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            espn_sport, espn_league = SPORT_ESPN_MAP.get("MLB", ("baseball", "mlb"))
            scoreboard = await _fetch_scoreboard(client, espn_sport, espn_league)
            for event in scoreboard.get("events", []):
                for comp in event.get("competitions", []):
                    competitors = comp.get("competitors", [])
                    if len(competitors) < 2:
                        continue
                    # Identify home/away competitor by homeAway flag
                    by_side = {}
                    for c in competitors:
                        side = c.get("homeAway", "")
                        by_side[side] = c
                    home_c = by_side.get("home")
                    away_c = by_side.get("away")
                    if not home_c or not away_c:
                        continue
                    home_names = [
                        home_c.get("team", {}).get("displayName", ""),
                        home_c.get("team", {}).get("shortDisplayName", ""),
                        home_c.get("team", {}).get("name", ""),
                        home_c.get("team", {}).get("abbreviation", ""),
                    ]
                    away_names = [
                        away_c.get("team", {}).get("displayName", ""),
                        away_c.get("team", {}).get("shortDisplayName", ""),
                        away_c.get("team", {}).get("name", ""),
                        away_c.get("team", {}).get("abbreviation", ""),
                    ]
                    if not (_name_match(home, home_names) and _name_match(away, away_names)):
                        continue
                    # Found the matching event — extract probables
                    for side_key, comp_obj in (("home", home_c), ("away", away_c)):
                        for prob in comp_obj.get("probables", []):
                            athlete = prob.get("athlete", {})
                            if not athlete:
                                continue
                            sp_info = {"name": athlete.get("displayName",
                                       athlete.get("fullName", "Unknown"))}
                            stats = athlete.get("stats", [])
                            if isinstance(stats, list) and len(stats) >= 3:
                                try:
                                    sp_info["era"] = float(stats[2])
                                except (ValueError, TypeError, IndexError):
                                    pass
                            out[side_key] = sp_info
                            break
                    return out
    except Exception as e:
        logger.warning(f"[ESPN] MLB pitcher fetch failed for {away}@{home}: {e}")
    return out


async def enrich_game_for_grading(game_data: dict, sport: str, odds_key: str = "") -> dict:
    home = game_data.get("homeTeam", "")
    away = game_data.get("awayTeam", "")
    home_profile, away_profile = await asyncio.gather(
        fetch_team_profile(home, sport, odds_key, opponent_name=away),
        fetch_team_profile(away, sport, odds_key, opponent_name=home),
    )

    # ── MLB: starting pitcher must be fetched per-game (not from team cache)
    # because the same team can appear in only one game per day but the
    # team-level profile cache can leak a stale value across calls. Always
    # overwrite with the game-specific probables from today's scoreboard.
    if sport == "MLB":
        sp_map = await _fetch_mlb_starting_pitchers(home, away)
        if sp_map.get("home"):
            home_profile["starting_pitcher"] = sp_map["home"]
        if sp_map.get("away"):
            away_profile["starting_pitcher"] = sp_map["away"]
    odds = game_data.get("odds", {})

    # Pull injuries from profiles for the grade engine
    # Ensure each injury has the fields the grade engine expects:
    #   player, status, position, ppg (default 0)
    home_injuries = []
    for inj in home_profile.get("injuries", []):
        home_injuries.append({
            "player": inj.get("player", "Unknown"),
            "status": inj.get("status", "UNKNOWN"),
            "position": inj.get("position", ""),
            "ppg": inj.get("ppg", 0),
        })
    away_injuries = []
    for inj in away_profile.get("injuries", []):
        away_injuries.append({
            "player": inj.get("player", "Unknown"),
            "status": inj.get("status", "UNKNOWN"),
            "position": inj.get("position", ""),
            "ppg": inj.get("ppg", 0),
        })

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
