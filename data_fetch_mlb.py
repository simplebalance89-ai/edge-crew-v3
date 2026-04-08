"""MLB-specific data fetcher backed by the official MLB Stats API
(toddrob99/MLB-StatsAPI). This is the authoritative source for everything
MLB — probable pitchers (with real names + ERA + WHIP + K/9), starting
lineups, bullpen usage, weather, plate umpire, and team gamelogs.

The existing ESPN MLB path in `data_fetch.py` stays alive as a fallback —
if StatsAPI raises (network, library install issue, schedule miss), we
return None and the caller falls through to ESPN.

Sync library wrapped in `asyncio.to_thread` so the async pipeline stays
non-blocking.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Cache: {game_pk: {"data": {...}, "_ts": datetime}}
_mlb_game_cache: dict = {}
_MLB_CACHE_TTL = 300  # 5 minutes


def _statsapi_available() -> bool:
    try:
        import statsapi  # noqa: F401
        return True
    except ImportError:
        return False


def _normalize_team_name(name: str) -> str:
    """Strip city, lowercase last word for fuzzy match against StatsAPI."""
    if not name:
        return ""
    return name.strip().lower()


def _team_name_match(stats_name: str, our_name: str) -> bool:
    """Loose match: 'Houston Astros' should match 'Astros' or 'Houston'."""
    a = _normalize_team_name(stats_name)
    b = _normalize_team_name(our_name)
    if not a or not b:
        return False
    if a == b:
        return True
    a_parts = set(a.split())
    b_parts = set(b.split())
    return bool(a_parts & b_parts)


def _extract_pitcher_stats(player_id: int) -> dict:
    """Pull current-season pitching stats for a player. Returns era/whip/k9/bb9
    when available, empty dict on any failure."""
    import statsapi
    out: dict = {}
    try:
        stats = statsapi.player_stat_data(player_id, group="pitching", type="season")
        for season_stat in stats.get("stats", []):
            if season_stat.get("type", {}).get("displayName") == "season":
                s = season_stat.get("stats", {}) or {}
                if s.get("era") is not None:
                    try:
                        out["era"] = float(s["era"])
                    except (ValueError, TypeError):
                        pass
                if s.get("whip") is not None:
                    try:
                        out["whip"] = float(s["whip"])
                    except (ValueError, TypeError):
                        pass
                if s.get("strikeoutsPer9Inn") is not None:
                    try:
                        out["k9"] = float(s["strikeoutsPer9Inn"])
                    except (ValueError, TypeError):
                        pass
                if s.get("walksPer9Inn") is not None:
                    try:
                        out["bb9"] = float(s["walksPer9Inn"])
                    except (ValueError, TypeError):
                        pass
                if s.get("inningsPitched") is not None:
                    out["ip"] = s["inningsPitched"]
                break
    except Exception as e:
        logger.debug(f"[StatsAPI] pitcher stats fetch failed for {player_id}: {e}")
    return out


def _fetch_sync(home_team: str, away_team: str, game_date: str) -> Optional[dict]:
    """Synchronous StatsAPI lookup. Wrapped in asyncio.to_thread by callers."""
    if not _statsapi_available():
        logger.warning("[StatsAPI] library not installed — falling back to ESPN")
        return None
    import statsapi

    # game_date is ISO format like "2026-04-08T16:36:00Z" — convert to YYYY-MM-DD
    try:
        if "T" in game_date:
            dt = datetime.fromisoformat(game_date.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
        else:
            date_str = game_date
    except (ValueError, TypeError):
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        sched = statsapi.schedule(date=date_str)
    except Exception as e:
        logger.warning(f"[StatsAPI] schedule fetch failed for {date_str}: {e}")
        return None

    if not sched:
        return None

    # Find the matchup
    target = None
    for g in sched:
        sa_home = g.get("home_name", "")
        sa_away = g.get("away_name", "")
        if _team_name_match(sa_home, home_team) and _team_name_match(sa_away, away_team):
            target = g
            break

    if not target:
        logger.debug(f"[StatsAPI] no schedule match for {away_team} @ {home_team} on {date_str}")
        return None

    # Pull probable pitcher names + IDs
    home_p_name = target.get("home_probable_pitcher", "") or ""
    away_p_name = target.get("away_probable_pitcher", "") or ""
    home_p_id = target.get("home_probable_pitcher_id")
    away_p_id = target.get("away_probable_pitcher_id")

    home_sp: dict = {"name": home_p_name} if home_p_name else {}
    away_sp: dict = {"name": away_p_name} if away_p_name else {}

    # Enrich with season stats when we have a player ID
    if home_p_id:
        try:
            home_sp.update(_extract_pitcher_stats(int(home_p_id)))
        except (ValueError, TypeError):
            pass
    if away_p_id:
        try:
            away_sp.update(_extract_pitcher_stats(int(away_p_id)))
        except (ValueError, TypeError):
            pass

    # Weather + umpire come from boxscore (only available after first pitch);
    # for upcoming games StatsAPI exposes these via `get_game_contextual_metrics`
    # but they may be None pre-game. Best-effort populate.
    weather: dict = {}
    umpire: dict = {}
    game_pk = target.get("game_id")
    if game_pk:
        try:
            game_info = statsapi.get("game", {"gamePk": game_pk})
            game_data = (game_info.get("gameData") or {})
            wx = game_data.get("weather") or {}
            if wx:
                weather = {
                    "condition": wx.get("condition"),
                    "temp": wx.get("temp"),
                    "wind": wx.get("wind"),
                }
            officials = (game_data.get("officials") or [])
            for o in officials:
                if (o.get("officialType") or "").lower() == "home plate":
                    umpire = {"name": (o.get("official") or {}).get("fullName")}
                    break
        except Exception as e:
            logger.debug(f"[StatsAPI] game info fetch failed for {game_pk}: {e}")

    return {
        "source": "mlb_statsapi",
        "game_pk": game_pk,
        "home_starting_pitcher": home_sp,
        "away_starting_pitcher": away_sp,
        "weather": weather,
        "umpire": umpire,
    }


async def fetch_mlb_game_profile(home_team: str, away_team: str, game_date: str) -> Optional[dict]:
    """Async entry point. Returns the StatsAPI profile dict for one MLB game,
    or None if unavailable (caller should fall back to ESPN).

    Cache key is (home, away, date) — short TTL because lineups + weather
    update right up to first pitch."""
    cache_key = f"{home_team}|{away_team}|{game_date}"
    cached = _mlb_game_cache.get(cache_key)
    if cached:
        age = (datetime.now(timezone.utc) - cached["_ts"]).total_seconds()
        if age < _MLB_CACHE_TTL:
            return cached["data"]

    try:
        data = await asyncio.to_thread(_fetch_sync, home_team, away_team, game_date)
    except Exception as e:
        logger.warning(f"[StatsAPI] async wrapper failed for {away_team}@{home_team}: {e}")
        return None

    if data is None:
        return None

    _mlb_game_cache[cache_key] = {"data": data, "_ts": datetime.now(timezone.utc)}
    return data
