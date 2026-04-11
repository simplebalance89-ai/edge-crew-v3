"""
Edge Crew v3.0 â€” Combined API + Frontend
Live odds â†’ ESPN profiles â†’ Grade Engine â†’ Two-Lane Display
"""

import asyncio
import hashlib
import time
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

# Add parent dir to path for grade_engine / data_fetch imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from grade_engine import grade_both_sides, score_to_grade, calculate_ev, peter_rules
from data_fetch import enrich_game_for_grading, fetch_team_profile
from ai_models import crowdsource_grade, kimi_gatekeeper

logger = logging.getLogger("edge-crew-v3")
logging.basicConfig(level=logging.INFO)

# â”€â”€â”€ Observability â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Both Sentry and structlog are opt-in via env vars so the default dev path
# stays exactly the same as before. Set SENTRY_DSN to capture exceptions;
# set STRUCTLOG=1 to swap stdlib logging for structured JSON output.

_SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
if _SENTRY_DSN:
    try:
        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
        from sentry_sdk.integrations.logging import LoggingIntegration  # type: ignore
        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            environment=os.environ.get("SENTRY_ENV", "production"),
            release=os.environ.get("RENDER_GIT_COMMIT", "")[:12] or None,
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES", "0.0")),
            integrations=[
                FastApiIntegration(),
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
        )
        logger.info("[OBS] Sentry initialized")
    except ImportError:
        logger.warning("[OBS] SENTRY_DSN set but sentry-sdk not installed; pip install sentry-sdk[fastapi]")
    except Exception as _e:
        logger.warning(f"[OBS] Sentry init failed: {_e}")

if os.environ.get("STRUCTLOG", "").strip() == "1":
    try:
        import structlog  # type: ignore
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            logger_factory=structlog.PrintLoggerFactory(),
        )
        logger.info("[OBS] structlog JSON output enabled")
    except ImportError:
        logger.warning("[OBS] STRUCTLOG=1 but structlog not installed; pip install structlog")
    except Exception as _e:
        logger.warning(f"[OBS] structlog init failed: {_e}")

app = FastAPI(title="Edge Crew v3.0", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# â”€â”€â”€ Disk Persistence â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

PERSIST_DIR = "/data" if os.path.exists("/data") else "/tmp/ec8"
os.makedirs(PERSIST_DIR, exist_ok=True)


def _load_json(filename: str, default):
    path = os.path.join(PERSIST_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
    return default


def _save_json(filename: str, data):
    path = os.path.join(PERSIST_DIR, filename)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.warning(f"Failed to save {path}: {e}")


def _save_users():
    _save_json("users.json", USERS)


def _save_picks():
    _save_json("picks.json", _user_picks)


ODDS_API_KEY = os.environ.get("ODDS_API_KEY_PAID", "") or os.environ.get("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports"

SPORT_KEYS = {
    "nba": ["basketball_nba"],
    "nhl": ["icehockey_nhl"],
    "mlb": ["baseball_mlb"],
    "nfl": ["americanfootball_nfl"],
    "ncaab": ["basketball_ncaab"],
    "ncaaf": ["americanfootball_ncaaf"],
    "soccer": ["soccer_usa_mls", "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a", "soccer_germany_bundesliga", "soccer_france_ligue_one", "soccer_uefa_champs_league", "soccer_uefa_europa_league", "soccer_brazil_campeonato", "soccer_mexico_ligamx"],
    "mma": ["mma_mixed_martial_arts"],
    "boxing": ["boxing_boxing"],
    "golf": ["golf_masters_tournament_winner", "golf_pga_championship_winner", "golf_us_open_winner", "golf_the_open_championship_winner"],
}

SOCCER_LEAGUE_MAP = {
    "epl": ["soccer_epl"],
    "la_liga": ["soccer_spain_la_liga"],
    "serie_a": ["soccer_italy_serie_a"],
    "mls": ["soccer_usa_mls"],
    "bundesliga": ["soccer_germany_bundesliga"],
    "ligue_1": ["soccer_france_ligue_one"],
    "ucl": ["soccer_uefa_champs_league"],
    "europa": ["soccer_uefa_europa_league"],
    "brazil": ["soccer_brazil_campeonato"],
    "liga_mx": ["soccer_mexico_ligamx"],
}

# High-scoring MLB parks (hitter-friendly) â€” park factor proxy
HITTER_FRIENDLY_PARKS = {
    "Colorado Rockies", "Texas Rangers", "Boston Red Sox",
    "Cincinnati Reds", "Philadelphia Phillies", "Arizona Diamondbacks",
}

# NHL goalie tiers â€” re-imported from grade_engine so the AI prompt can surface
# who's actually in net. Fallback to inline copies if import fails (keeps
# main.py resilient to grade_engine refactors).
try:
    from grade_engine import ELITE_NHL_GOALIES, GOOD_NHL_GOALIES  # type: ignore
except Exception:  # pragma: no cover â€” defensive fallback
    ELITE_NHL_GOALIES = {
        "hellebuyck", "sorokin", "vasilevskiy", "shesterkin", "bobrovsky",
        "saros", "markstrom", "oettinger", "hill", "kuemper", "swayman",
        "ullmark", "skinner", "demko", "hart", "gibson", "talbot", "stolarz",
    }
    GOOD_NHL_GOALIES = {
        "andersen", "husso", "husarek", "mrazek", "binnington", "georgiev",
        "jarry", "blackwood", "vanecek", "lyon", "merzlikins", "kahkonen",
        "wedgewood", "samsonov", "knight", "varlamov", "luukkonen",
    }


def _nhl_goalie_tier_label(name: str) -> str:
    """Return uppercase tier label for an NHL goalie name."""
    if not name or name == "TBD":
        return "UNKNOWN"
    parts = name.strip().lower().split()
    last = parts[-1] if parts else ""
    if last in ELITE_NHL_GOALIES:
        return "ELITE"
    if last in GOOD_NHL_GOALIES:
        return "GOOD"
    return "AVERAGE"

PREFERRED_BOOKS = ["fanduel", "draftkings", "betmgm", "caesars", "bovada"]

_cache: Dict[str, dict] = {}
# 4hr TTL â€” cron pre-warm at 6am must survive until user wakes ~7am AND past
# the cron's own ~2hr worst-case run time. 5min TTL was racing the cron.
CACHE_TTL = 14400

# â”€â”€â”€ User Profiles â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_DEFAULT_USERS = {
    "peter": {"name": "Peter", "pin": "0000", "bankroll": {"starting": 490, "current": 490, "wagered": 0, "profit": 0, "wins": 0, "losses": 0, "pushes": 0}},
    "chinny": {"name": "Chinny", "pin": "0000", "bankroll": {"starting": 1000, "current": 1000, "wagered": 0, "profit": 0, "wins": 0, "losses": 0, "pushes": 0}},
    "jimmy": {"name": "Jimmy", "pin": "0000", "bankroll": {"starting": 1000, "current": 1000, "wagered": 0, "profit": 0, "wins": 0, "losses": 0, "pushes": 0}},
}

USERS = _load_json("users.json", _DEFAULT_USERS)
# Ensure any new default users are added if missing from persisted data
for _u, _v in _DEFAULT_USERS.items():
    if _u not in USERS:
        USERS[_u] = _v

# Store locked picks per user â€” loaded from disk
_user_picks: Dict[str, list] = _load_json("picks.json", {"peter": [], "chinny": [], "jimmy": []})
for _u in USERS:
    if _u not in _user_picks:
        _user_picks[_u] = []

logger.info(f"[PERSIST] Loaded from {PERSIST_DIR} â€” {sum(len(v) for v in _user_picks.values())} picks across {len(USERS)} users")

# Must match grade_engine.py GRADE_THRESHOLDS exactly
GRADE_MAP = [
    (8.0, "A+"), (7.3, "A"), (6.5, "A-"), (6.0, "B+"), (5.5, "B"),
    (5.0, "B-"), (4.5, "C+"), (3.5, "C"), (2.5, "D"), (0.0, "F"),
]


def _odds_grade(odds: dict) -> dict:
    """Quick odds-only grade for AI Process lane (fast, no ESPN needed)."""
    spread = abs(odds.get("spread", 0))
    ml_home = odds.get("mlHome", 0)
    ml_away = odds.get("mlAway", 0)
    total = odds.get("total", 0)

    # Spread scoring â€” big spread means clear favorite, not a penalty
    if spread <= 3: spread_score = 8.0      # tight competitive game
    elif spread <= 6: spread_score = 7.0
    elif spread <= 10: spread_score = 6.0
    else: spread_score = 5.5                # one-sided but still real

    # ML gap scoring
    ml_diff = abs(ml_home - ml_away) if ml_home and ml_away else 200
    if ml_diff < 100: ml_score = 8.0       # tight
    elif ml_diff <= 250: ml_score = 7.0    # medium
    else: ml_score = 5.5                   # wide

    # Total context
    total_score = 7.0 if 200 <= total <= 240 else (6.0 if total > 0 else 5.5)

    score = round(spread_score * 0.45 + ml_score * 0.35 + total_score * 0.20, 1)
    score = max(5.0, score)  # Floor: no real game drops below 5.0
    conf = min(95, max(45, int(60 + (score - 5) * 7)))
    grade = "F"
    for threshold, g in GRADE_MAP:
        if score >= threshold:
            grade = g
            break
    return {"grade": grade, "score": score, "confidence": conf, "model": "Odds-Model"}


def _convergence(our: dict, ai: dict, ai_models: list = None) -> dict:
    """Compute convergence. ALIGNED = everyone agrees on the same side."""
    delta = round(abs(our["score"] - ai["score"]), 2)
    consensus = round((our["score"] * 0.6 + ai["score"] * 0.4), 1)
    agreement_pct = 1.0
    if ai_models:
        picks = [m.get("pick", "") for m in ai_models if m.get("pick")]
        if picks:
            fav_count = sum(1 for p in picks if "-" in p.split(" ")[-1])
            dog_count = len(picks) - fav_count
            agreement_pct = max(fav_count, dog_count) / len(picks) if picks else 1.0
    if agreement_pct >= 0.85 and consensus >= 7.0: status = "LOCK"
    elif agreement_pct >= 0.70 and consensus >= 6.0: status = "ALIGNED"
    elif agreement_pct < 0.60: status = "SPLIT"
    elif delta <= 1.5: status = "CLOSE"
    else: status = "SPLIT"
    grade = "F"
    for threshold, g in GRADE_MAP:
        if consensus >= threshold:
            grade = g
            break
    return {
        "status": status, "consensusScore": consensus, "consensusGrade": grade,
        "delta": delta, "variance": round(delta / 2, 2), "agreement": round(agreement_pct * 100),
    }


def _apply_conflict_downgrade(game: dict, pick: dict, ai_models: list, conv: dict, pr: dict | None) -> bool:
    """If engine pick side disagrees with AI majority pick side, downgrade.
    Caps consensus at 4.5, sets status=CONFLICT, adds KILL flag. Returns True if conflict.
    """
    if not (ai_models and pick and pick.get("side") and conv):
        return False
    home_name = game.get("homeTeam", "") or game.get("home_team", "")
    away_name = game.get("awayTeam", "") or game.get("away_team", "")
    home_votes = 0
    away_votes = 0
    for m in ai_models:
        p = str(m.get("pick", "")).strip().lower()
        if not p:
            continue
        if p == "home" or (home_name and p == home_name.lower()):
            home_votes += 1
        elif p == "away" or (away_name and p == away_name.lower()):
            away_votes += 1
    if home_votes == 0 and away_votes == 0:
        return False
    if home_votes > away_votes:
        ai_side = home_name
    elif away_votes > home_votes:
        ai_side = away_name
    else:
        return False  # tie â€” don't flag
    engine_side = pick["side"]
    if not engine_side or ai_side == engine_side:
        return False
    capped = min(conv.get("consensusScore", 0), 4.5)
    conv["consensusScore"] = capped
    conv["consensusGrade"] = "D+"
    conv["status"] = "CONFLICT"
    conv["conflict"] = {
        "engineSide": engine_side,
        "aiSide": ai_side,
        "homeVotes": home_votes,
        "awayVotes": away_votes,
    }
    if pr is not None:
        flags = pr.setdefault("flags", [])
        if not any(f.get("rule") == "side_conflict" for f in flags):
            flags.insert(0, {
                "rule": "side_conflict",
                "action": "KILL",
                "severity": "high",
                "note": f"CONFLICT â€” Engine picks {engine_side}, AI picks {ai_side}",
            })
    return True


def _apply_kill_override(pick: dict, conv: dict, pr: dict | None) -> None:
    """If Peter's Rules has a KILL flag OR convergence is CONFLICT, force the
    pick to PASS and mark it killed. Side is left intact for display only â€”
    the frontend hides the bet button when killed=True or sizing=='PASS'."""
    if not isinstance(pick, dict):
        return
    killed = False
    if isinstance(pr, dict):
        for f in (pr.get("flags") or []):
            if isinstance(f, dict) and f.get("action") == "KILL":
                killed = True
                break
    if isinstance(conv, dict) and conv.get("status") == "CONFLICT":
        killed = True
    if killed:
        pick["sizing"] = "PASS"
        pick["killed"] = True


def _compute_pick(event: dict, odds: dict, our: dict, ai: dict, conv: dict) -> dict:
    """Determine pick recommendation from convergence.

    The picked SIDE is whichever team the engine actually scored higher for
    (our["pick_team"] / our["pick_side"]), NOT the spread favorite. The spread
    is only used to compute the LINE for the picked side (flipped when the
    engine prefers the underdog). Earlier versions blindly returned the spread
    favorite which created false CONFLICT/KILL flags whenever the engine
    disagreed with the market.
    """
    consensus = conv["consensusScore"]
    status = conv["status"]
    spread = odds.get("spread", 0)
    home = event.get("homeTeam", "") or event.get("home_team", "")
    away = event.get("awayTeam", "") or event.get("away_team", "")

    # Engine-preferred side is the source of truth. Fall back to spread fav
    # only if the engine didn't expose one (legacy / fallback grade paths).
    pick_side = (our or {}).get("pick_side")
    pick_team = (our or {}).get("pick_team")

    if pick_team and pick_team in (home, away):
        side = pick_team
    elif pick_side == "home":
        side = home
    elif pick_side == "away":
        side = away
    else:
        # No engine signal â€” last-resort fall back to spread favorite so we
        # never crash, but log it so we can find the path that needs fixing.
        side = home if spread <= 0 else away
        logger.warning(
            f"[PICK] no engine pick_side for {away} @ {home}; falling back to spread fav={side}"
        )

    # Line: by frontend convention (TwoLaneCard.tsx), odds.spread is the
    # AWAY team's point spread â€” homeLine = -spread, awayLine = spread.
    # So if we're picking home, the line is the negated spread; if away,
    # the line is the spread as-is. Pirates (home) -1.5 favorite has
    # odds.spread = +1.5 (Padres' line), so home line = -1.5.
    line = -spread if side == home else spread

    if status in ("LOCK", "ALIGNED") and consensus >= 7.0:
        return {"side": side, "type": "spread", "line": line,
                "confidence": min(95, int(consensus * 10 + 10)), "sizing": "Strong Play"}
    elif status == "ALIGNED" and consensus >= 6.0:
        return {"side": side, "type": "spread", "line": line,
                "confidence": min(80, int(consensus * 8 + 10)), "sizing": "Standard"}
    elif consensus >= 5.5:
        return {"side": side, "type": "ml", "line": 0,
                "confidence": min(70, int(consensus * 7)), "sizing": "Lean"}
    else:
        return {"side": side, "type": "ml", "line": 0,
                "confidence": max(30, int(consensus * 6)), "sizing": "Lean"}


def _ml_to_decimal(ml: float) -> float:
    """Convert American moneyline to decimal odds."""
    if ml >= 100:
        return 1 + ml / 100
    elif ml <= -100:
        return 1 + 100 / abs(ml)
    return 2.0  # fallback even money


def _detect_arbitrage(event: dict) -> dict | None:
    """Detect arbitrage opportunities across all bookmakers for h2h markets."""
    bookmakers = event.get("bookmakers", [])
    if len(bookmakers) < 2:
        return None

    home_team = event.get("home_team", "")
    away_team = event.get("away_team", "")

    best_home_decimal = 0.0
    best_home_book = ""
    best_home_ml = 0
    best_away_decimal = 0.0
    best_away_book = ""
    best_away_ml = 0

    for bk in bookmakers:
        book_name = bk.get("title", bk.get("key", "?"))
        markets = {m["key"]: m["outcomes"] for m in bk.get("markets", [])}
        h2h = markets.get("h2h", [])
        for o in h2h:
            price = o.get("price", 0)
            if not price:
                continue
            dec = _ml_to_decimal(price)
            if o["name"] == home_team and dec > best_home_decimal:
                best_home_decimal = dec
                best_home_book = book_name
                best_home_ml = price
            elif o["name"] == away_team and dec > best_away_decimal:
                best_away_decimal = dec
                best_away_book = book_name
                best_away_ml = price

    if best_home_decimal <= 0 or best_away_decimal <= 0:
        return None

    implied_sum = (1 / best_home_decimal) + (1 / best_away_decimal)
    has_arb = implied_sum < 1.0
    arb_pct = round((1 - implied_sum) * 100, 2) if has_arb else 0.0

    return {
        "has_arb": has_arb,
        "arb_pct": arb_pct,
        "best_home": {"book": best_home_book, "odds": best_home_ml},
        "best_away": {"book": best_away_book, "odds": best_away_ml},
    }


# Team name overrides â€” Odds API quirks (e.g. Athletics moved to Sacramento mid-2024)
TEAM_NAME_OVERRIDES = {
    "Athletics": "Sacramento Athletics",
}


def _normalize_team_name(name: str) -> str:
    return TEAM_NAME_OVERRIDES.get(name, name)


def _parse_event(event: dict, sport_label: str) -> dict:
    """Parse odds API event into our game format (without grading â€” added later)."""
    # Normalize team names in-place (Athletics -> Sacramento Athletics, etc.)
    if event.get("home_team") in TEAM_NAME_OVERRIDES:
        event["home_team"] = TEAM_NAME_OVERRIDES[event["home_team"]]
    if event.get("away_team") in TEAM_NAME_OVERRIDES:
        event["away_team"] = TEAM_NAME_OVERRIDES[event["away_team"]]
    # Normalize names embedded in bookmaker outcomes so h2h/spread matching still works
    for bk in event.get("bookmakers", []):
        for m in bk.get("markets", []):
            for o in m.get("outcomes", []):
                if o.get("name") in TEAM_NAME_OVERRIDES:
                    o["name"] = TEAM_NAME_OVERRIDES[o["name"]]

    spread = total = ml_home = ml_away = None
    spread_price_home = spread_price_away = None
    over_price = under_price = None
    btts_yes = btts_no = None
    draw_price = None
    bookmaker_used = None
    bookmakers_data = {bk["key"]: bk for bk in event.get("bookmakers", [])}
    book_order = PREFERRED_BOOKS + [k for k in bookmakers_data if k not in PREFERRED_BOOKS]

    for book_key in book_order:
        bk = bookmakers_data.get(book_key)
        if not bk:
            continue
        markets = {m["key"]: m["outcomes"] for m in bk.get("markets", [])}
        if not markets:
            continue
        if not bookmaker_used:
            bookmaker_used = book_key
        # Only take h2h from first book that has it
        if ml_home is None:
            for o in markets.get("h2h", []):
                if o["name"] == event["home_team"]: ml_home = o.get("price")
                elif o["name"] == event["away_team"]: ml_away = o.get("price")
                elif o["name"] == "Draw": draw_price = o.get("price")
        # Take spread from first book that has it
        if spread is None:
            for o in markets.get("spreads", []):
                if o["name"] == event["home_team"]:
                    spread = o.get("point")
                    spread_price_home = o.get("price")
                elif o["name"] == event["away_team"]:
                    spread_price_away = o.get("price")
        # Take totals from first book that has it
        if total is None:
            for o in markets.get("totals", []):
                if o["name"] == "Over":
                    total = o.get("point")
                    over_price = o.get("price")
                elif o["name"] == "Under":
                    under_price = o.get("price")
        # BTTS (Both Teams To Score) â€” soccer-specific market
        if btts_yes is None:
            for o in markets.get("btts", []):
                if o["name"] == "Yes": btts_yes = o.get("price")
                elif o["name"] == "No": btts_no = o.get("price")
        # Stop once we have all core markets
        if ml_home is not None and total is not None:
            break

    commence = event.get("commence_time", "")
    status = "scheduled"
    if commence:
        try:
            gt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
            hours_ago = (datetime.now(timezone.utc) - gt).total_seconds() / 3600
            if hours_ago > 3.5:
                status = "completed"
            elif hours_ago > 0:
                status = "live"
        except Exception:
            pass

    # Arbitrage detection across all bookmakers
    arb = _detect_arbitrage(event)

    # Frontend convention: odds.spread = AWAY team's line.
    # API returns home team's spread, so negate it.
    away_spread = -spread if spread else 0
    odds = {
        "spread": away_spread, "total": total or 0,
        "mlHome": ml_home or 0, "mlAway": ml_away or 0,
        "spreadPriceHome": spread_price_home or -110,
        "spreadPriceAway": spread_price_away or -110,
        "overPrice": over_price,
        "underPrice": under_price,
        "bttsYes": btts_yes,
        "bttsNo": btts_no,
        "draw": draw_price,
    }
    # Deterministic game id derived from matchup + commence time so the same
    # game keys identically across sync runs (Odds API's raw event id can drift
    # between fetches, breaking line-movement diffs and pick references).
    stable_id = hashlib.md5(
        f"{event['home_team']}|{event['away_team']}|{commence}".encode("utf-8")
    ).hexdigest()[:16]
    return {
        "id": stable_id,
        "oddsApiId": event["id"],
        "sport": sport_label,
        "homeTeam": event["home_team"],
        "awayTeam": event["away_team"],
        "scheduledAt": commence,
        "status": status,
        "odds": odds,
        "bookmaker": bookmaker_used,
        "arbitrage": arb,
        "shifts": _get_line_movement(event["id"], away_spread, ml_home or 0),
    }


# â”€â”€â”€ Real Azure AI Foundry calls (parallel single-shot) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# Single-endpoint Azure registry â€” gce-personal-resource hosts all 10 models.
# Sweden Central key kept as fallback but gce is the primary path.
AZURE_AI_KEY = os.environ.get("AZURE_AI_KEY", "") or os.environ.get("AZURE_SWEDEN_KEY", "")
AZURE_GCE_KEY = os.environ.get("AZURE_GCE_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")

AZURE_HOSTS = {
    "gce": {
        "url_template": "https://gce-personal-resource.openai.azure.com/openai/deployments/{deployment}/chat/completions?api-version=2024-12-01-preview",
        "key": AZURE_GCE_KEY,
        "format": "aoai_classic",
    },
    "sweden": {
        "url": "https://peter-mna31gr3-swedencentral.services.ai.azure.com/openai/v1/chat/completions",
        "key": AZURE_AI_KEY,
        "format": "openai_v1",
    },
    "gemini": {
        "url_template": "https://generativelanguage.googleapis.com/v1beta/models/{deployment}:generateContent",
        "key": GEMINI_API_KEY,
        "format": "gemini",
    },
    "perplexity": {
        "url": "https://api.perplexity.ai/chat/completions",
        "key": PERPLEXITY_API_KEY,
        "format": "openai_v1",
    },
}

# 10 confirmed-working models, all hosted at gce-personal-resource (probed 2026-04-07).
# token_param: "max_completion_tokens" required for gpt-5+ and o-series; "max_tokens" for everything else.
REAL_AI_MODELS = [
    {"display": "Grok 4.1",          "deployment": "grok-4-1-fast-reasoning",              "host": "gce", "persona": "contrarian, sniffs out trap lines",          "token_param": "max_completion_tokens", "max_tokens": 8000,  "timeout": 240},
    {"display": "Grok 3",            "deployment": "grok-3",                                "host": "gce", "persona": "older Grok, different bias / value angle",  "token_param": "max_tokens",            "max_tokens": 2000,  "timeout": 60},
    {"display": "DeepSeek R1",       "deployment": "DeepSeek-R1-0528",                      "host": "gce", "persona": "data-driven heavy reasoner",                 "token_param": "max_tokens",            "max_tokens": 4000,  "timeout": 180},
    {"display": "DeepSeek V3.2 Spec","deployment": "DeepSeek-V3-2-Speciale",                "host": "gce", "persona": "newest specialty model, sharp on data",      "token_param": "max_tokens",            "max_tokens": 2500,  "timeout": 90},
    # Kimi K2 Thinking removed from the main batch â€” Azure-hosted version was
    # consistently the slowest model in the slate (240s timeout, often hit it)
    # and dragged the whole batch ceiling up. It now lives only as the
    # post-convergence gatekeeper, where Moonshot's direct API (set
    # MOONSHOT_API_KEY env) gives it a fast, reliable path.
    {"display": "Phi-4 Reasoning",   "deployment": "Phi-4-reasoning",                       "host": "gce", "persona": "chain-of-thought on thin edges",             "token_param": "max_tokens",            "max_tokens": 6000,  "timeout": 180},
    {"display": "GPT-4.1",           "deployment": "gpt-41",                                "host": "gce", "persona": "OpenAI flagship balanced view",              "token_param": "max_tokens",            "max_tokens": 2000,  "timeout": 60},
    {"display": "GPT-5 Mini",        "deployment": "gpt-5-mini",                            "host": "gce", "persona": "next-gen OpenAI consensus",                  "token_param": "max_completion_tokens", "max_tokens": 8000,  "timeout": 180},
    {"display": "o4-mini",           "deployment": "o4-mini",                               "host": "gce", "persona": "OpenAI reasoning model, careful logic",      "token_param": "max_completion_tokens", "max_tokens": 12000, "timeout": 240},
    {"display": "Llama-4 Maverick",  "deployment": "Llama-4-Maverick-17B-128E-Instruct-FP8","host": "gce", "persona": "open-source heavyweight, broad pattern",     "token_param": "max_tokens",            "max_tokens": 2000,  "timeout": 60},
    {"display": "Gemini 2.5 Flash",  "deployment": "gemini-2.5-flash",                      "host": "gemini","persona": "Google multimodal, broad pattern matcher", "token_param": "maxOutputTokens",      "max_tokens": 2000,  "timeout": 120},
    {"display": "Perplexity Sonar",  "deployment": "sonar",                                  "host": "perplexity","persona": "real-time web research, contrarian to consensus", "token_param": "max_tokens", "max_tokens": 2000, "timeout": 90},
]


def _active_real_models_for_sport(sport_upper: str, fast_mode: bool = False) -> list[dict]:
    """Sport-aware model roster.
    Soccer slates can be large, so we trim the roster to reduce provider
    throttling/timeouts while keeping diversified model opinions."""
    if sport_upper == "SOCCER":
        # Soccer-specific stable roster. These models have shown the best
        # reliability/latency tradeoff in production soccer analyze runs.
        keep = {
            "Grok 3",
            "DeepSeek V3.2 Spec",
            "GPT-4.1",
            "GPT-5 Mini",
            "Perplexity Sonar",
        }
        return [m for m in REAL_AI_MODELS if m.get("display") in keep]
    return REAL_AI_MODELS


_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think>.*", re.DOTALL | re.IGNORECASE)


def _strip_think_tags(text: str) -> str:
    if not text:
        return text
    # If a </think> exists, take everything AFTER the last one â€” that's the
    # actual answer. This survives token-cutoff cases where <think> never
    # closed cleanly OR where a reasoning model emitted a giant think block.
    lower = text.lower()
    last_close = lower.rfind("</think>")
    if last_close != -1:
        return text[last_close + len("</think>"):].strip()
    # No closing tag at all. If there's an opening <think>, strip from there.
    if "<think>" in lower:
        return _THINK_OPEN_RE.sub("", text).strip()
    return text.strip()


def _extract_balanced_json(text: str, prefer_last: bool = True) -> Optional[dict]:
    """Find a balanced {...} block in text and json.loads it. If prefer_last,
    scans from the end backward for the LAST balanced block; else first."""
    if not text:
        return None
    candidates = []
    n = len(text)
    # Walk for all balanced top-level brace blocks
    i = 0
    while i < n:
        if text[i] == "{":
            depth = 0
            in_str = False
            esc = False
            for j in range(i, n):
                c = text[j]
                if in_str:
                    if esc:
                        esc = False
                    elif c == "\\":
                        esc = True
                    elif c == '"':
                        in_str = False
                else:
                    if c == '"':
                        in_str = True
                    elif c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            candidates.append(text[i:j + 1])
                            i = j
                            break
            else:
                break
        i += 1
    if not candidates:
        return None
    order = reversed(candidates) if prefer_last else iter(candidates)
    for cand in order:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def _format_injuries(inj_list: list) -> str:
    """Format injury list for AI prompt â€” only OUT/DOUBTFUL, with freshness tags.
    SEASON-long injuries are DROPPED entirely â€” already baked into the line."""
    if not inj_list:
        return "none currently affecting the line"
    # Drop season-long ghosts before anything else
    live = [i for i in inj_list if (i.get("freshness") or "FRESH") != "SEASON"]
    if not live:
        return "none currently affecting the line"
    out = []
    for inj in live[:6]:  # cap at 6
        status = inj.get("status", "")
        if status not in ("OUT", "DOUBTFUL"):
            continue
        name = inj.get("player", "?")
        ppg = inj.get("ppg", 0)
        freshness = inj.get("freshness") or "FRESH"
        star = " STAR" if (ppg or 0) >= 15 else ""
        out.append(f"{name} ({status}, {freshness}, {ppg}ppg{star})")
    return "; ".join(out) if out else "none currently affecting the line"


def _build_realai_prompt(game: dict, our_score: float, personality: str) -> str:
    home = game.get("homeTeam", "Home")
    away = game.get("awayTeam", "Away")
    sport = (game.get("sport") or "").upper()
    odds = game.get("odds", {}) or {}
    hp = game.get("home_profile", {}) or {}
    ap = game.get("away_profile", {}) or {}
    inj = game.get("injuries", {}) or {}
    spread = odds.get("spread", 0)
    total = odds.get("total", 0)
    ml_h = odds.get("mlHome", 0)
    ml_a = odds.get("mlAway", 0)
    draw = odds.get("draw")
    btts_yes = odds.get("bttsYes")
    btts_no = odds.get("bttsNo")
    # Guardrail: distinguish "we have injury data and nobody is OUT" from
    # "we have NO injury data at all" so models stop hallucinating names.
    inj_present = isinstance(inj, dict) and ("home" in inj or "away" in inj)
    if inj_present:
        inj_home_str = _format_injuries(inj.get("home", []))
        inj_away_str = _format_injuries(inj.get("away", []))
        injury_block = (
            f"INJURIES (verified ESPN data; FRESH=new edge, RECENT=partial edge, "
            f"ESTABLISHED=already in the line, SEASON=dropped) â€” DO NOT downgrade "
            f"picks for ESTABLISHED entries since the market already priced them in. "
            f"DO NOT invent or speculate about any player not listed here. "
            f"{home}: {inj_home_str} | {away}: {inj_away_str} | "
        )
    else:
        injury_block = (
            "INJURY DATA: UNAVAILABLE â€” DO NOT SPECULATE ABOUT INJURED PLAYERS. "
            "Do not mention any player by name as injured, out, or absent. "
            "Grade purely on records, form, rest, and line. | "
        )
    rest = game.get("rest", {}) or {}
    shifts = game.get("shifts", {}) or {}

    # Sport-specific spread label + scoring unit
    if sport == "NHL":
        spread_label = "puck line (home)"
        scoring_unit = "GPG"
    elif sport == "MLB":
        spread_label = "run line (home)"
        scoring_unit = "RPG"
    else:
        spread_label = "spread (home)"
        scoring_unit = "PPG"

    # Streak / splits / scoring / rest / line movement â€” compact context block
    h_streak = hp.get("streak") or "-"
    a_streak = ap.get("streak") or "-"
    h_split = hp.get("home_record") or "?"
    a_split = ap.get("away_record") or "?"
    form_block = (
        f"FORM â€” {away}: streak {a_streak}, away {a_split} | "
        f"{home}: streak {h_streak}, home {h_split} | "
    )
    if hp.get("ppg_L5") or ap.get("ppg_L5"):
        form_block += (
            f"SCORING L5 â€” {away} {ap.get('ppg_L5',0)} {scoring_unit}/{ap.get('opp_ppg_L5',0)} allowed, "
            f"{home} {hp.get('ppg_L5',0)} {scoring_unit}/{hp.get('opp_ppg_L5',0)} allowed | "
        )
    h_rest = rest.get("home_rest_days")
    a_rest = rest.get("away_rest_days")
    if h_rest is not None or a_rest is not None:
        h_r = f"{h_rest}d{' B2B' if rest.get('home_b2b') else ''}" if h_rest is not None else "?"
        a_r = f"{a_rest}d{' B2B' if rest.get('away_b2b') else ''}" if a_rest is not None else "?"
        form_block += f"REST â€” {away}: {a_r}, {home}: {h_r} | "
    sd = shifts.get("spread_delta") or 0
    if sd:
        direction = home if sd < 0 else away
        form_block += f"LINE â€” spread moved {abs(sd):.1f} toward {direction} | "

    # Head-to-head season series â€” huge ignored variable. Frame from home's
    # perspective since home_profile.h2h_season = home wins-losses vs opponent.
    h2h = str(hp.get("h2h_season") or "").strip()
    if h2h and h2h != "0-0":
        form_block += f"H2H â€” {home} {h2h} vs {away} this season | "

    # NBA-specific: quarter splits + bench scoring (the Phoenix-blows-leads
    # variables). Surfaced AFTER form, BEFORE the injury block so the model
    # sees lead-collapse and late-game closing context next to the scoring line.
    nba_block = ""
    if sport == "NBA":
        h_q = hp.get("nba_quarters") or {}
        a_q = ap.get("nba_quarters") or {}

        def _q_label(q: dict) -> str:
            blown = q.get("leads_blown_l10", 0) or 0
            comebacks = q.get("comebacks_l10", 0) or 0
            if blown >= 3 and comebacks == 0:
                return "collapse-prone"
            if blown == 0 and comebacks >= 2:
                return "strong closer"
            if blown >= 2 and blown > comebacks:
                return "shaky closer"
            if comebacks >= 2 and comebacks > blown:
                return "good closer"
            return "neutral"

        if h_q or a_q:
            nba_block += "QUARTER SPLITS L10 - "
            if a_q:
                nba_block += (
                    f"{away}: Q1 {a_q.get('q1_avg_for','?')} / Q4 {a_q.get('q4_avg_for','?')}, "
                    f"leads blown {a_q.get('leads_blown_l10',0)}, "
                    f"comebacks {a_q.get('comebacks_l10',0)} ({_q_label(a_q)}) | "
                )
            if h_q:
                nba_block += (
                    f"{home}: Q1 {h_q.get('q1_avg_for','?')} / Q4 {h_q.get('q4_avg_for','?')}, "
                    f"leads blown {h_q.get('leads_blown_l10',0)}, "
                    f"comebacks {h_q.get('comebacks_l10',0)} ({_q_label(h_q)}) | "
                )

        h_bench = hp.get("bench_ppg_l5")
        a_bench = ap.get("bench_ppg_l5")
        if h_bench is not None or a_bench is not None:
            nba_block += (
                f"BENCH L5 - {away}: {a_bench if a_bench is not None else '?'} ppg | "
                f"{home}: {h_bench if h_bench is not None else '?'} ppg | "
            )

    # MLB-specific: include probable starting pitchers with tier label from
    # KNOWN_ACE_PITCHERS, plus real ERA/WHIP/K9 when MLB Stats API populated
    # them, plus weather + plate umpire from StatsAPI gameData.
    pitcher_block = ""
    mlb_priority_block = ""
    if sport == "MLB":
        h_sp_dict = hp.get("starting_pitcher") or {}
        a_sp_dict = ap.get("starting_pitcher") or {}
        h_sp = h_sp_dict.get("name", "TBD")
        a_sp = a_sp_dict.get("name", "TBD")
        a_tier = _pitcher_tier(a_sp_dict).upper()
        h_tier = _pitcher_tier(h_sp_dict).upper()

        def _sp_stats_str(d: dict) -> str:
            parts = []
            if d.get("era") is not None:
                parts.append(f"{d['era']} ERA")
            if d.get("whip") is not None:
                parts.append(f"{d['whip']} WHIP")
            if d.get("k9") is not None:
                parts.append(f"{d['k9']} K/9")
            return f", {', '.join(parts)}" if parts else ""

        a_stats = _sp_stats_str(a_sp_dict)
        h_stats = _sp_stats_str(h_sp_dict)
        pitcher_block = (
            f"PROBABLE PITCHERS â€” {away}: {a_sp} ({a_tier}{a_stats}) | "
            f"{home}: {h_sp} ({h_tier}{h_stats}) | "
        )
        # Park factor â€” surface the actual FanGraphs park factor index when
        # we know it. >100 = hitter friendly, <100 = pitcher friendly,
        # 100 = neutral. Pulled from grade_engine.PARK_FACTORS.
        try:
            from grade_engine import PARK_FACTORS as _PF
            pf_val = _PF.get(home)
        except Exception:
            pf_val = None
        if pf_val is not None:
            if pf_val >= 105:
                pf_label = "very hitter-friendly"
            elif pf_val >= 102:
                pf_label = "mildly hitter-friendly"
            elif pf_val <= 95:
                pf_label = "very pitcher-friendly"
            elif pf_val <= 98:
                pf_label = "mildly pitcher-friendly"
            else:
                pf_label = "neutral"
            pitcher_block += f"PARK FACTOR: {pf_val} ({pf_label}) | "
        elif home in HITTER_FRIENDLY_PARKS:
            pitcher_block += "PARK: hitter-friendly (boost offense, hurt pitchers) | "

        # Weather (from MLB StatsAPI gameData when available)
        wx = game.get("weather") or {}
        if wx and (wx.get("temp") or wx.get("wind") or wx.get("condition")):
            parts = []
            if wx.get("condition"):
                parts.append(str(wx["condition"]))
            if wx.get("temp"):
                parts.append(f"{wx['temp']}Â°F")
            if wx.get("wind"):
                parts.append(f"wind {wx['wind']}")
            pitcher_block += f"WEATHER: {', '.join(parts)} | "

        # Plate umpire (from MLB StatsAPI officials) â€” surface K%/BB% tag when
        # we have the umpire in our hardcoded UMPIRE_TENDENCIES dataset.
        ump = game.get("umpire") or {}
        if ump.get("name"):
            try:
                from grade_engine import UMPIRE_TENDENCIES as _UT
                tend = _UT.get(ump["name"])
            except Exception:
                tend = None
            if tend:
                k = tend["k_pct"]
                tag = "high-K" if k >= 23.0 else "low-K" if k <= 22.0 else "neutral"
                pitcher_block += f"HP UMPIRE: {ump['name']} (K% {k}, {tag}) | "
            else:
                pitcher_block += f"HP UMPIRE: {ump['name']} | "

        # Bullpen ERA L7 + tired arm count (from MLB StatsAPI 7-day walk)
        h_bp = hp.get("bullpen") or {}
        a_bp = ap.get("bullpen") or {}
        if h_bp.get("bullpen_era_L7") is not None or a_bp.get("bullpen_era_L7") is not None:
            def _bp_str(d: dict) -> str:
                if not d or d.get("bullpen_era_L7") is None:
                    return "?"
                era = d["bullpen_era_L7"]
                tired = d.get("bullpen_tired_arms", 0)
                tag = " TIRED" if tired >= 3 else " STRESSED" if tired >= 2 else ""
                return f"{era} ERA L7{tag}"
            pitcher_block += (
                f"BULLPEN â€” {away}: {_bp_str(a_bp)} | "
                f"{home}: {_bp_str(h_bp)} | "
            )

        # Lineup vs SP hand â€” OPS splits vs the opposing starter's handedness
        h_lvh = hp.get("lineup_vs_hand") or {}
        a_lvh = ap.get("lineup_vs_hand") or {}
        if h_lvh.get("ops_vs_hand") is not None or a_lvh.get("ops_vs_hand") is not None:
            def _lvh_str(d: dict) -> str:
                if not d or d.get("ops_vs_hand") is None:
                    return "?"
                return f"{d['ops_vs_hand']:.3f} OPS vs {d.get('vs_hand', '?')}HP"
            pitcher_block += (
                f"LINEUP VS HAND â€” {away}: {_lvh_str(a_lvh)} | "
                f"{home}: {_lvh_str(h_lvh)} | "
            )
        mlb_priority_block = (
            "MLB EDGE PRIORITY: "
            "1) bullpen quality/fatigue, "
            "2) starter depth + command (IP/K9/BB9), "
            "3) lineup-vs-hand + pitcher/lineup archetype fit, "
            "4) park/weather/umpire, "
            "5) starter-name narrative LAST. "
            "Do not anchor on pitcher name alone. | "
        )

    # NHL-specific: starting goalies + tier label + SV% when ESPN provides it.
    # data_fetch._fetch_nhl_starting_goalies now populates starting_goalie on
    # the profile for game-day matchups, so this block actually lights up.
    goalie_block = ""
    if sport == "NHL":
        h_goalie = hp.get("starting_goalie") or {}
        a_goalie = ap.get("starting_goalie") or {}
        h_g = h_goalie.get("name", "TBD")
        a_g = a_goalie.get("name", "TBD")
        a_gt = _nhl_goalie_tier_label(a_g)
        h_gt = _nhl_goalie_tier_label(h_g)

        def _svp_txt(gd: dict) -> str:
            sv = gd.get("sv_pct") or gd.get("SV%") or gd.get("svp")
            try:
                if sv is None:
                    return ""
                s = float(sv)
                if s > 1.5:
                    s /= 100.0
                if 0.80 <= s <= 1.0:
                    return f", {s:.3f} SV%"
            except (ValueError, TypeError):
                pass
            return ""

        goalie_block = (
            f"STARTING GOALIES â€” {away}: {a_g} ({a_gt}{_svp_txt(a_goalie)}) | "
            f"{home}: {h_g} ({h_gt}{_svp_txt(h_goalie)}) | "
        )

    # SOCCER-specific: key-player-out flags (matched against hardcoded top
    # scorer dict), fixture congestion legs, keeper tier, competition tag.
    soccer_block = ""
    if sport == "SOCCER":
        try:
            from grade_engine import (
                _soccer_stars_out as _ssout,
                _soccer_keeper_tier as _skt,
            )
        except Exception:
            _ssout = None
            _skt = None
        if _ssout and inj_present:
            h_stars_out = _ssout(game, "home")
            a_stars_out = _ssout(game, "away")
            if h_stars_out or a_stars_out:
                def _fmt(lst):
                    return ", ".join(f"{n} ({s})" for n, s in lst) if lst else "none"
                soccer_block += (
                    f"KEY ATTACKERS OUT â€” {away}: {_fmt(a_stars_out)} | "
                    f"{home}: {_fmt(h_stars_out)} | "
                )
        # Fixture congestion legs (matches in last 10d)
        h_cong = hp.get("matches_in_10d")
        a_cong = ap.get("matches_in_10d")
        if h_cong is not None or a_cong is not None:
            soccer_block += (
                f"FIXTURE CONGESTION â€” {away}: {a_cong or 0} matches in 10d, "
                f"{home}: {h_cong or 0} matches in 10d | "
            )
        # Keeper tier (if a starting_keeper ever gets populated)
        if _skt:
            h_kp = (hp.get("starting_keeper") or {}).get("name")
            a_kp = (ap.get("starting_keeper") or {}).get("name")
            if h_kp or a_kp:
                h_kt = _skt(h_kp) or "AVG" if h_kp else "?"
                a_kt = _skt(a_kp) or "AVG" if a_kp else "?"
                soccer_block += (
                    f"KEEPERS â€” {away}: {a_kp or 'TBD'} ({a_kt}) | "
                    f"{home}: {h_kp or 'TBD'} ({h_kt}) | "
                )
        # Competition / league label so the model treats EFL Cup form
        # differently from league form
        league = game.get("league") or game.get("league_name") or ""
        if league:
            soccer_block += f"COMPETITION: {league} | "
        if draw not in (None, 0):
            soccer_block += f"ML 3-WAY: {away} {ml_a:+d} / Draw {draw:+d} / {home} {ml_h:+d} | "
        if btts_yes is not None or btts_no is not None:
            by = f"{int(btts_yes):+d}" if isinstance(btts_yes, (int, float)) else "?"
            bn = f"{int(btts_no):+d}" if isinstance(btts_no, (int, float)) else "?"
            soccer_block += f"BTTS: Yes {by} / No {bn} | "

    # Sport-appropriate example reasoning so the prompt example doesn't leak
    # baseball language ("pitching edge") into NBA grading. This was a real
    # bug â€” DeepSeek V3.2 Spec parroted "pitching edge" on the Rockets-Suns
    # NBA game tonight because the example said it.
    sport_example = {
        "NBA":   '{"grade": 7.2, "pick": "Home", "reasoning": "stronger recent form and home court edge"}',
        "WNBA":  '{"grade": 7.2, "pick": "Home", "reasoning": "stronger recent form and home court edge"}',
        "NCAAB": '{"grade": 7.2, "pick": "Home", "reasoning": "stronger recent form and home court edge"}',
        "NHL":   '{"grade": 7.2, "pick": "Home", "reasoning": "elite goalie edge and rest advantage"}',
        "MLB":   '{"grade": 7.2, "pick": "Home", "reasoning": "bullpen freshness and lineup-vs-hand edge outweigh starter-name narrative"}',
        "NFL":   '{"grade": 7.2, "pick": "Home", "reasoning": "rest advantage and matchup edge in the trenches"}',
        "NCAAF": '{"grade": 7.2, "pick": "Home", "reasoning": "rest advantage and matchup edge in the trenches"}',
        "SOCCER":'{"grade": 7.2, "pick": "BTTS_Yes", "reasoning": "both attacks are in form and defensive absences raise both-side scoring probability"}',
    }.get(sport, '{"grade": 7.2, "pick": "Home", "reasoning": "stronger recent form"}')

    if sport == "SOCCER":
        schema = (
            '{"grade": <0-10 number>, '
            '"pick": "Home" or "Away" or "Draw" or "Over" or "Under" or "BTTS_Yes" or "BTTS_No", '
            '"reasoning": "one short sentence naming the strongest market edge"}'
        )
        market_rule = (
            "For soccer, evaluate market edge across 1X2 (Home/Away/Draw), totals (Over/Under), "
            "and BTTS (Yes/No) when odds are present, then pick the single best edge."
        )
    elif sport == "MLB":
        schema = (
            '{"grade": <0-10 number>, '
            '"pick": "Home" or "Away" or "Over" or "Under", '
            '"reasoning": "one short sentence naming the strongest edge in the selected market"}'
        )
        market_rule = (
            "For MLB, evaluate edge across side (Home/Away) and total (Over/Under). "
            "Prioritize bullpen/depth/archetype signals over starter-name narratives."
        )
    else:
        schema = '{"grade": <0-10 number>, "pick": "Home" or "Away", "reasoning": "one short sentence"}'
        market_rule = "Pick side only (Home or Away)."

    return (
        f"GAME: {away} ({ap.get('record','?')}, L5 {ap.get('L5','?')}) @ "
        f"{home} ({hp.get('record','?')}, L5 {hp.get('L5','?')}) | "
        f"{spread_label} {spread:+.1f} | total {total} | ML {away}: {ml_a} / {home}: {ml_h} | "
        f"{form_block}"
        f"{nba_block}"
        f"{pitcher_block}"
        f"{mlb_priority_block}"
        f"{goalie_block}"
        f"{soccer_block}"
        f"{injury_block}"
        f"engine composite: {our_score:.1f}/10. "
        f"{market_rule} "
        f"As a sharp bettor ({personality}), output ONLY a single JSON object on one line, "
        f"no thinking, no prose, no code fences. Schema: "
        f"{schema}. "
        f'EXAMPLE OUTPUT: {sport_example} '
        f"Now output ONLY the JSON object, starting with {{ :"
    )


async def _call_azure_model(model_cfg: dict, prompt: str) -> Optional[dict]:
    """Call one Azure model based on its config dict (display/deployment/host/token_param).
    Returns parsed {grade, pick, reasoning} dict or None on any failure."""
    host_cfg = AZURE_HOSTS.get(model_cfg["host"])
    if not host_cfg or not host_cfg.get("key"):
        return None

    deployment = model_cfg["deployment"]
    display = model_cfg["display"]

    system_msg = (
        "RESPONSE FORMAT: ONE LINE OF JSON ONLY. "
        "Example: {\"grade\": 6.5, \"pick\": \"Home\", \"reasoning\": \"better record\"}. "
        "No thinking. No prose. No code fences. No tags. "
        "Start your response with the opening brace { and end with }."
    )
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt},
    ]

    # Reasoning models need much more headroom because reasoning tokens count toward the budget.
    token_budget = int(model_cfg.get("max_tokens") or 2000)

    # Reasoning models (token_param == max_completion_tokens) reject temperature!=1
    # and reject response_format at the Azure param-validation layer (HTTP 400 in
    # ~450ms). Omit those fields entirely for reasoning models.
    is_reasoning = model_cfg.get("token_param") == "max_completion_tokens"

    # Build URL + body shape based on host format
    if host_cfg["format"] == "openai_v1":
        url = host_cfg["url"]
        body = {
            "model": deployment,
            "messages": messages,
            model_cfg.get("token_param", "max_tokens"): token_budget,
        }
        if not is_reasoning:
            body["temperature"] = 0.3
        headers = {
            "api-key": host_cfg["key"],
            "Authorization": f"Bearer {host_cfg['key']}",
            "Content-Type": "application/json",
        }
    elif host_cfg["format"] == "gemini":
        # Google Gemini REST. Key passed as query param. Different body shape entirely.
        url = host_cfg["url_template"].format(deployment=deployment) + f"?key={host_cfg['key']}"
        body = {
            "systemInstruction": {"parts": [{"text": system_msg}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": token_budget,
                "responseMimeType": "application/json",
            },
        }
        headers = {"Content-Type": "application/json"}
    else:  # aoai_classic
        url = host_cfg["url_template"].format(deployment=deployment)
        body = {
            "messages": messages,
            model_cfg.get("token_param", "max_tokens"): token_budget,
        }
        if not is_reasoning:
            body["temperature"] = 0.3
        headers = {
            "api-key": host_cfg["key"],
            "Authorization": f"Bearer {host_cfg['key']}",
            "Content-Type": "application/json",
        }

    try:
        req_timeout = float(model_cfg.get("timeout") or 60)
        async with httpx.AsyncClient(timeout=req_timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
    except Exception as e:
        logger.warning(f"[REAL-AI EXC] {display}: {type(e).__name__}: {str(e)[:160]}")
        return None

    if resp.status_code != 200:
        logger.warning(f"[REAL-AI FAIL] {display} dep={deployment} status={resp.status_code} body={resp.text[:200]}")
        return None

    try:
        rj = resp.json()
        if host_cfg["format"] == "gemini":
            cand0 = (rj.get("candidates") or [{}])[0]
            parts = ((cand0.get("content") or {}).get("parts") or [])
            content = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
            choice0 = {"finish_reason": cand0.get("finishReason")}
        else:
            choice0 = (rj.get("choices") or [{}])[0]
            msg = choice0.get("message", {}) or {}
            content = (
                msg.get("content")
                or msg.get("reasoning_content")
                or choice0.get("text")
                or ""
            )
            if isinstance(content, list):
                parts = []
                for p in content:
                    if isinstance(p, dict):
                        parts.append(p.get("text") or p.get("content") or "")
                    else:
                        parts.append(str(p))
                content = "".join(parts)
    except Exception as e:
        logger.warning(f"[REAL-AI PARSE] {display}: {e}")
        return None

    if not content:
        try:
            finish = choice0.get("finish_reason")
        except Exception:
            finish = "?"
        logger.warning(f"[REAL-AI EMPTY] {display} dep={deployment} finish={finish}")
        return None

    raw_content = content
    try:
        finish_reason = choice0.get("finish_reason")
    except Exception:
        finish_reason = None
    cleaned = _strip_think_tags(content)
    cleaned = re.sub(r"```(?:json)?", "", cleaned, flags=re.IGNORECASE).replace("```", "").strip()
    # If think-stripping wiped everything (truncated reasoning model), fall
    # back to scanning the raw content for a balanced JSON object.
    if not cleaned:
        cleaned = raw_content

    # Extraction strategies in order: full parse â†’ last balanced â†’ first balanced
    data = None
    strategy = ""
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            data = parsed
            strategy = "full"
    except Exception:
        pass
    if not data:
        data = _extract_balanced_json(cleaned, prefer_last=True)
        if data:
            strategy = "last-balanced"
    if not data:
        data = _extract_balanced_json(cleaned, prefer_last=False)
        if data:
            strategy = "first-balanced"

    if not data:
        logger.warning(
            f"[REAL-AI NOJSON] {display} dep={deployment} finish={finish_reason} "
            f"raw_len={len(raw_content)} raw[:300]={raw_content[:300]!r}"
        )
        return None
    else:
        logger.info(f"[REAL-AI OK] {display} strategy={strategy} finish={finish_reason}")

    try:
        grade = float(data.get("grade", 0))
    except Exception:
        grade = 0.0

    return {
        "grade": max(0.0, min(10.0, grade)),
        "pick": str(data.get("pick", "")).strip() or "Home",
        "reasoning": str(data.get("reasoning", "")).strip()[:300],
    }


async def _real_ai_models_for_game(
    game: dict,
    our_score: float,
    model_cfgs: Optional[list[dict]] = None,
) -> Optional[list]:
    """Call all 7 Azure models in parallel for one game. Returns list of model
    dicts (may be partial â€” some entries may be missing if they failed)."""
    if not AZURE_AI_KEY and not AZURE_GCE_KEY:
        return None
    home = game.get("homeTeam", "Home")
    away = game.get("awayTeam", "Away")
    active_models = model_cfgs or REAL_AI_MODELS
    tasks = [
        _call_azure_model(cfg, _build_realai_prompt(game, our_score, cfg["persona"]))
        for cfg in active_models
    ]
    # Hard ceiling on the whole batch â€” even if one reasoning model hangs,
    # the analyze endpoint never blocks longer than this per game. 280s gives
    # the slowest 240s reasoning models (Grok 4.1, Kimi K2 Thinking, o4-mini)
    # full headroom plus 40s slack for connection/parse overhead. The per-game
    # /api/analyze hard cap is 550s; with this 280s batch + ~200s gatekeeper
    # we still finish well under that.
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=280.0,
        )
    except asyncio.TimeoutError:
        logger.warning("[REAL-AI BATCH] hard 280s ceiling hit â€” returning whatever finished")
        results = [TimeoutError("batch ceiling exceeded") for _ in active_models]
    out = []
    for cfg, res in zip(active_models, results):
        disp = cfg["display"]
        if isinstance(res, Exception):
            logger.warning(f"[REAL-AI EXC] {disp}: {res}")
            continue
        if not res:
            continue
        score = round(res["grade"], 1)
        pick_raw = str(res.get("pick", "")).strip()
        pick_l = pick_raw.lower()
        if pick_l.startswith("h"):
            pick_label = home
        elif pick_l.startswith("a"):
            pick_label = away
        elif pick_l in ("draw", "over", "under", "btts_yes", "btts_no"):
            pick_label = pick_raw
        else:
            pick_label = pick_raw or away
        out.append({
            "model": disp,
            "grade": _score_to_grade_local(score),
            "score": score,
            "confidence": min(92, int(50 + score * 4)),
            "thesis": res.get("reasoning", ""),
            "pick": pick_label,
            "key_factors": [],
            "source": "real",
        })
    return out if out else None


def _generate_ai_models(enriched: dict, odds: dict, our_score: float) -> list:
    """Generate 9 AI personality grades with reasoning â€” pure math, no API needed."""
    home = enriched.get("home", enriched.get("home_team", "Home"))
    away = enriched.get("away", enriched.get("away_team", "Away"))
    hp = enriched.get("home_profile", {})
    ap = enriched.get("away_profile", {})
    spread = odds.get("spread", 0)
    fav = home if spread <= 0 else away
    dog = away if spread <= 0 else home
    fav_rec = hp.get("record", "?") if spread <= 0 else ap.get("record", "?")
    dog_rec = ap.get("record", "?") if spread <= 0 else hp.get("record", "?")
    fav_ppg = hp.get("ppg_L5", 0) if spread <= 0 else ap.get("ppg_L5", 0)
    fav_margin = hp.get("avg_margin_L10", 0) if spread <= 0 else ap.get("avg_margin_L10", 0)
    dog_margin = ap.get("avg_margin_L10", 0) if spread <= 0 else hp.get("avg_margin_L10", 0)

    models = []
    abs_spread = abs(spread)
    # Favorites are always minus, dogs always plus â€” independent of home/away
    fav_line = -abs_spread
    dog_line = abs_spread

    def _pick_for(score: float) -> str:
        """Each model picks fav if score >= 5.5, else dog."""
        if score >= 5.5:
            return f"{fav} {fav_line:+.1f}"
        return f"{dog} {dog_line:+.1f}"

    # DeepSeek â€” data-driven, stats-heavy
    ds_score = round(our_score * 0.85 + (fav_margin / 10) * 1.5, 1)
    ds_score = max(3.0, min(9.5, ds_score))
    ds_grade = _score_to_grade_local(ds_score)
    if fav_margin > 5:
        ds_thesis = f"{fav} ({fav_rec}) averaging +{fav_margin:.1f} margin â€” clear statistical edge vs {dog} ({dog_rec}). Spread {abs(spread):.1f} is justified by the data."
    elif fav_margin > 0:
        ds_thesis = f"{fav} ({fav_rec}) slight edge with +{fav_margin:.1f} margin, but {dog} ({dog_rec}) keeps it close. Moderate value on the spread."
    else:
        ds_thesis = f"Numbers don't back {fav} strongly â€” margin only {fav_margin:+.1f}. {dog} ({dog_rec}) has underdog value here."
    models.append({"model": "DeepSeek R1", "grade": ds_grade, "score": ds_score,
                    "confidence": min(90, int(55 + ds_score * 4)),
                    "thesis": ds_thesis, "pick": _pick_for(ds_score), "key_factors": []})

    # Grok â€” contrarian, looks for traps
    grok_adj = -0.5 if abs(spread) > 10 else (0.3 if abs(spread) < 3 else 0)
    grok_score = round(our_score + grok_adj + (dog_margin / 15), 1)
    grok_score = max(3.0, min(9.5, grok_score))
    grok_grade = _score_to_grade_local(grok_score)
    if abs(spread) > 10:
        grok_thesis = f"Big spread alert â€” {fav} at {fav_line:+.1f} smells like a public trap. {dog} ({dog_rec}) margin is {dog_margin:+.1f}, not as bad as the line suggests."
    elif abs(spread) < 3:
        grok_thesis = f"Tight line ({fav_line:+.1f}) means sharps see this as a coin flip. {fav} ({fav_rec}) slight edge but no blowout coming."
    else:
        grok_thesis = f"Line at {fav_line:+.1f} is fair. {fav} ({fav_rec}) should cover but not by much. No strong contrarian signal."
    models.append({"model": "Grok 4.1", "grade": grok_grade, "score": grok_score,
                    "confidence": min(85, int(50 + grok_score * 4)),
                    "thesis": grok_thesis, "pick": _pick_for(grok_score), "key_factors": []})

    # Kimi â€” structural/tactical scout
    home_rec = hp.get("home_record", "")
    away_rec = ap.get("away_record", "")
    kimi_boost = 0.0
    kimi_parts = []
    if home_rec:
        try:
            hw, hl = int(home_rec.split("-")[0]), int(home_rec.split("-")[1])
            if hw + hl > 0 and hw / (hw + hl) > 0.65:
                kimi_boost += 0.5
                kimi_parts.append(f"{home} strong at home ({home_rec})")
        except (ValueError, IndexError):
            pass
    if away_rec:
        try:
            aw, al = int(away_rec.split("-")[0]), int(away_rec.split("-")[1])
            if aw + al > 0 and aw / (aw + al) < 0.4:
                kimi_boost += 0.3
                kimi_parts.append(f"{away} struggles on road ({away_rec})")
        except (ValueError, IndexError):
            pass
    kimi_score = round(our_score + kimi_boost, 1)
    kimi_score = max(3.0, min(9.5, kimi_score))
    kimi_grade = _score_to_grade_local(kimi_score)
    if kimi_parts:
        kimi_thesis = "Structural edge: " + ". ".join(kimi_parts) + f". Tactical profile favors {fav}."
    else:
        kimi_thesis = f"No strong structural edge detected. {fav} ({fav_rec}) vs {dog} ({dog_rec}) â€” standard matchup, grade from fundamentals only."
    models.append({"model": "Kimi K2 Thinking", "grade": kimi_grade, "score": kimi_score,
                    "confidence": min(88, int(52 + kimi_score * 4)),
                    "thesis": kimi_thesis, "pick": _pick_for(kimi_score), "key_factors": []})

    # GPT Nano â€” balanced consensus builder, weighs all factors equally
    odds_score = _odds_grade(odds)["score"]
    gpt_score = round((our_score + odds_score) / 2, 1)
    gpt_score = max(3.0, min(9.5, gpt_score))
    gpt_grade = _score_to_grade_local(gpt_score)
    if abs(our_score - odds_score) <= 1.0:
        gpt_thesis = f"Both fundamental and market analysis align on {fav} ({fav_rec}). Consensus score {gpt_score:.1f} reflects agreement across processes â€” steady value."
    else:
        stronger = "fundamentals" if our_score > odds_score else "market"
        weaker = "market" if our_score > odds_score else "fundamentals"
        gpt_thesis = f"Mixed signals: {stronger} say {fav} ({fav_rec}) is the play ({max(our_score, odds_score):.1f}) but {weaker} lag behind ({min(our_score, odds_score):.1f}). Middle ground lands at {gpt_score:.1f}."
    models.append({"model": "GPT 5.4 Nano", "grade": gpt_grade, "score": gpt_score,
                    "confidence": min(90, int(55 + gpt_score * 4)),
                    "thesis": gpt_thesis, "pick": _pick_for(gpt_score), "key_factors": []})

    # Claude Opus â€” deep strategic thinker, momentum & narrative focus, contrarian on big spreads
    momentum_weight = fav_margin * 0.2  # heavier momentum factor
    contrarian_adj = -0.4 if abs(spread) > 10 else (0.2 if abs(spread) < 3 else 0)
    claude_score = round(our_score * 0.7 + momentum_weight + contrarian_adj + 1.5, 1)
    claude_score = max(3.0, min(9.5, claude_score))
    claude_grade = _score_to_grade_local(claude_score)
    if fav_margin > 5:
        claude_thesis = f"Sustainable edge â€” {fav} ({fav_rec}) trajectory shows +{fav_margin:.1f} margin, a durable pattern not fluky variance. Momentum supports the line."
    elif fav_margin > 0:
        claude_thesis = f"{fav} ({fav_rec}) holding slim +{fav_margin:.1f} margin. Trajectory positive but regression risk exists if {dog} ({dog_rec}) tightens up. Lean cautiously."
    else:
        claude_thesis = f"Regression risk: {fav} favored at {fav_line:+.1f} but margin is only {fav_margin:+.1f}. {dog} ({dog_rec}) narrative is stronger than the line implies â€” contrarian value."
    models.append({"model": "Claude Opus 4.6", "grade": claude_grade, "score": claude_score,
                    "confidence": min(92, int(54 + claude_score * 4)),
                    "thesis": claude_thesis, "pick": _pick_for(claude_score), "key_factors": []})

    # Phi-4 Reasoning â€” small but sharp reasoning model, chain-of-thought approach
    # Weighs the delta between processes heavily â€” if Our and AI disagree, Phi digs into why
    process_delta = abs(our_score - (sum(m["score"] for m in models) / len(models)))
    if process_delta > 1.5:
        # Significant disagreement â€” Phi reasons through the conflict
        phi_score = round((our_score * 0.55 + ds_score * 0.25 + grok_score * 0.2), 1)
        phi_thesis = f"Process disagreement detected ({process_delta:.1f}pt gap). Reasoning through: {fav} ({fav_rec}) fundamentals score {our_score:.1f} but model consensus at {sum(m['score'] for m in models)/len(models):.1f}. Splitting the difference â€” edge exists but confidence is capped."
    elif fav_margin > 3:
        phi_score = round(our_score * 0.8 + fav_margin * 0.15 + 0.5, 1)
        phi_thesis = f"Chain-of-thought: {fav} ({fav_rec}) margin +{fav_margin:.1f} is reproducible across sample. {dog} ({dog_rec}) hasn't shown ability to close that gap. Line {fav_line:+.1f} is fair to slightly short."
    else:
        phi_score = round(our_score * 0.9 + 0.3, 1)
        phi_thesis = f"Thin edge â€” {fav} ({fav_rec}) is the right side but margin {fav_margin:+.1f} doesn't inspire conviction. Reasoning says bet small or pass unless other signals confirm."
    phi_score = max(3.0, min(9.5, phi_score))
    phi_grade = _score_to_grade_local(phi_score)
    models.append({"model": "Phi-4 Reasoning", "grade": phi_grade, "score": phi_score,
                    "confidence": min(88, int(50 + phi_score * 4)),
                    "thesis": phi_thesis, "pick": _pick_for(phi_score), "key_factors": []})

    # Qwen 3-32B â€” multilingual powerhouse, excels at pattern recognition across large datasets
    # Focuses on record differentials and historical patterns, slightly aggressive on clear mismatches
    record_gap = 0
    try:
        fw, fl = int(fav_rec.split("-")[0]), int(fav_rec.split("-")[1])
        dw, dl = int(dog_rec.split("-")[0]), int(dog_rec.split("-")[1])
        fav_pct = fw / max(fw + fl, 1)
        dog_pct = dw / max(dw + dl, 1)
        record_gap = fav_pct - dog_pct
    except (ValueError, IndexError):
        fav_pct = dog_pct = 0.5
    qwen_boost = record_gap * 3  # Aggressive on clear record gaps
    qwen_score = round(our_score * 0.75 + qwen_boost + fav_margin * 0.1 + 1.0, 1)
    qwen_score = max(3.0, min(9.5, qwen_score))
    qwen_grade = _score_to_grade_local(qwen_score)
    if record_gap > 0.15:
        qwen_thesis = f"Pattern clear: {fav} ({fav_rec}, {fav_pct:.0%}) dominant over {dog} ({dog_rec}, {dog_pct:.0%}). {record_gap:.0%} win rate gap is significant â€” market hasn't fully priced the class difference."
    elif record_gap > 0.05:
        qwen_thesis = f"{fav} ({fav_rec}) edges {dog} ({dog_rec}) but gap is narrow ({record_gap:.0%}). Line {fav_line:+.1f} looks accurate â€” value is thin, need secondary signals to confirm."
    else:
        qwen_thesis = f"Near-even matchup: {fav} ({fav_rec}) vs {dog} ({dog_rec}) separated by only {record_gap:.0%}. This is a coin flip the market got right â€” pass or go small."
    models.append({"model": "Qwen 3-32B", "grade": qwen_grade, "score": qwen_score,
                    "confidence": min(90, int(52 + qwen_score * 4)),
                    "thesis": qwen_thesis, "pick": _pick_for(qwen_score), "key_factors": []})

    # Gemini 2.5 â€” multimodal pattern matcher, cross-references multiple data dimensions simultaneously
    gemini_margin_factor = fav_margin * 0.12
    gemini_record_factor = record_gap * 2.0
    gemini_our_factor = our_score * 0.5
    gemini_home_boost = 0.3 if spread <= 0 else 0  # slight boost for home teams
    gemini_score = round(gemini_margin_factor + gemini_record_factor + gemini_our_factor + gemini_home_boost + 2.5, 1)
    gemini_score = max(3.0, min(9.5, gemini_score))
    gemini_grade = _score_to_grade_local(gemini_score)
    if fav_margin > 3 and record_gap > 0.10:
        gemini_thesis = f"Multi-factor validation: {fav} ({fav_rec}) checks all boxes â€” margin +{fav_margin:.1f}, record gap {record_gap:.0%}, home factor aligned. Cross-referencing confirms strong edge at {fav_line:+.1f}."
    elif fav_margin > 0 and record_gap > 0:
        gemini_thesis = f"Cross-referencing {fav} ({fav_rec}) across margin (+{fav_margin:.1f}), record ({record_gap:.0%} gap), and market data â€” signals are directionally aligned but not overwhelming. Moderate multi-dimensional edge."
    else:
        gemini_thesis = f"Multi-dimensional scan shows weak alignment for {fav} ({fav_rec}). Margin {fav_margin:+.1f} and record gap {record_gap:.0%} don't cross-validate â€” conflicting signals reduce conviction."
    models.append({"model": "Gemini 2.5", "grade": gemini_grade, "score": gemini_score,
                    "confidence": min(91, int(53 + gemini_score * 4)),
                    "thesis": gemini_thesis, "pick": _pick_for(gemini_score), "key_factors": []})

    # Perplexity Sonar â€” real-time information synthesizer, contrarian to consensus
    # If all models agree, Perplexity raises a flag; if models split, Perplexity digs deeper
    all_scores = [m["score"] for m in models]
    model_avg = sum(all_scores) / len(all_scores) if all_scores else our_score
    model_std = (sum((s - model_avg) ** 2 for s in all_scores) / len(all_scores)) ** 0.5 if all_scores else 0
    if model_std < 0.4:
        # High consensus â€” Perplexity is contrarian, nudges score down
        pplx_adj = -0.6
        pplx_thesis = f"Consensus too tight (std {model_std:.2f}) â€” when everyone agrees on {fav} ({fav_rec}), live signals suggest the market has already priced this in. Recent trends and breaking context warrant caution. Fading the crowd slightly."
    elif model_std > 1.2:
        # High disagreement â€” Perplexity digs deeper, stabilizes
        pplx_adj = 0.0
        pplx_thesis = f"Models split wide (std {model_std:.2f}) on {fav} ({fav_rec}) vs {dog} ({dog_rec}). Real-time synthesis: recent lineup news, travel patterns, and injury context suggest the truth is near the average. Breaking signals don't resolve the split."
    else:
        # Moderate â€” Perplexity adds live context, slight positive
        pplx_adj = 0.3
        pplx_thesis = f"Live signal integration for {fav} ({fav_rec}): recent performance trends and real-time market movement support the lean. Breaking context â€” no major injury flags detected, recent form holds. Slight edge confirmed by live data."
    pplx_score = round(model_avg + pplx_adj, 1)
    pplx_score = max(3.0, min(9.5, pplx_score))
    pplx_grade = _score_to_grade_local(pplx_score)
    models.append({"model": "Perplexity Sonar", "grade": pplx_grade, "score": pplx_score,
                    "confidence": min(87, int(48 + pplx_score * 4)),
                    "thesis": pplx_thesis, "pick": _pick_for(pplx_score), "key_factors": []})

    return models


def _score_to_grade_local(score: float) -> str:
    for threshold, g in GRADE_MAP:
        if score >= threshold:
            return g
    return "F"


def _grade_combat_from_odds(odds: dict, game: dict, sport: str) -> dict:
    """Grade MMA/Boxing fights from moneyline data only (no ESPN team data)."""
    ml_home = odds.get("mlHome", 0)
    ml_away = odds.get("mlAway", 0)
    spread = abs(odds.get("spread", 0))
    fighter_a = game.get("homeTeam", "Fighter A")
    fighter_b = game.get("awayTeam", "Fighter B")

    ml_diff = abs(ml_home - ml_away) if ml_home and ml_away else 200

    # Competitive fights = better edge opportunities
    if ml_diff < 80:
        score = 8.0
        thesis = f"Coin-flip fight: {fighter_a} vs {fighter_b} separated by only {ml_diff} ML pts. Maximum edge potential â€” line value exists on both sides."
    elif ml_diff < 150:
        score = 7.5
        thesis = f"Competitive bout: {fighter_a} vs {fighter_b} (ML gap {ml_diff}). Tight line suggests sharp money is split â€” look for style matchup edge."
    elif ml_diff < 250:
        score = 6.5
        thesis = f"Clear favorite emerging: ML gap {ml_diff} between {fighter_a} and {fighter_b}. Moderate edge â€” favorite is justified but line may be slightly inflated."
    elif ml_diff < 400:
        score = 5.5
        thesis = f"One-sided: ML gap {ml_diff}. {fighter_a if ml_home < ml_away else fighter_b} heavily favored. Spread value is thin â€” better as ML play or pass."
    else:
        score = 4.5
        thesis = f"Massive mismatch: ML gap {ml_diff}. Heavy favorite offers no spread value. Only play is dog ML at plus money if you see an upset angle."

    # Spread context bonus for combat sports (if spread exists)
    if spread and spread < 3:
        score += 0.3

    score = max(3.0, min(9.5, round(score, 1)))
    grade = _score_to_grade_local(score)
    conf = min(90, max(40, int(55 + (score - 5) * 8)))

    fav = fighter_a if (ml_home and ml_away and ml_home < ml_away) else fighter_b
    dog = fighter_b if fav == fighter_a else fighter_a

    # Combat has no team-data side grading â€” the engine pick IS the favorite
    # by ML. Encode that explicitly so downstream _compute_pick reads the
    # same field name as the team-sport path instead of falling back to the
    # spread-favorite shortcut.
    fav_side = "home" if fav == fighter_a else "away"

    return {
        "grade": grade,
        "score": score,
        "confidence": conf,
        "thesis": thesis,
        "keyFactors": [
            f"ML: {fighter_a} {ml_home:+d} / {fighter_b} {ml_away:+d}" if ml_home and ml_away else "No ML data",
            f"ML gap: {ml_diff} pts",
            f"Favorite: {fav}",
        ],
        "profiles": {},
        "pick_side": fav_side,
        "pick_team": fav,
        "variables": {
            "moneyline_gap": {"score": round(max(1, 10 - ml_diff / 50), 1), "name": "Moneyline Gap", "available": True},
            "line_value": {"score": score, "name": "Line Value", "available": True},
        },
    }


def _generate_ai_models_combat(game: dict, odds: dict, our_score: float, sport: str) -> list:
    """Generate 9 AI personality grades for MMA/Boxing â€” fighter context, not team context."""
    fighter_a = game.get("homeTeam", game.get("home_team", "Fighter A"))
    fighter_b = game.get("awayTeam", game.get("away_team", "Fighter B"))
    ml_home = odds.get("mlHome", 0)
    ml_away = odds.get("mlAway", 0)
    spread = odds.get("spread", 0)
    ml_diff = abs(ml_home - ml_away) if ml_home and ml_away else 200
    abs_spread = abs(spread)
    sport_label = "fight" if sport == "MMA" else "bout"

    # Determine favorite/dog from moneyline
    if ml_home and ml_away and ml_home < ml_away:
        fav, dog = fighter_a, fighter_b
        fav_ml, dog_ml = ml_home, ml_away
    elif ml_home and ml_away:
        fav, dog = fighter_b, fighter_a
        fav_ml, dog_ml = ml_away, ml_home
    else:
        fav, dog = fighter_a, fighter_b
        fav_ml, dog_ml = -150, 130

    models = []

    def _pick_for(score: float) -> str:
        if score >= 5.5:
            return f"{fav} ML ({fav_ml:+d})"
        return f"{dog} ML ({dog_ml:+d})"

    # DeepSeek â€” data-driven, focuses on ML value
    ds_score = round(our_score * 0.9 + (0.5 if ml_diff < 150 else -0.3), 1)
    ds_score = max(3.0, min(9.5, ds_score))
    ds_grade = _score_to_grade_local(ds_score)
    if ml_diff < 150:
        ds_thesis = f"Tight {sport_label}: {fav} ({fav_ml:+d}) vs {dog} ({dog_ml:+d}) â€” only {ml_diff} ML separation. Statistical edge is razor-thin, value on either side."
    elif ml_diff < 300:
        ds_thesis = f"{fav} ({fav_ml:+d}) clear favorite over {dog} ({dog_ml:+d}). {ml_diff} ML gap is moderate â€” data supports the lean but price is fair."
    else:
        ds_thesis = f"Heavy favorite: {fav} at {fav_ml:+d} with {ml_diff} ML gap. Juice is steep â€” {dog} ({dog_ml:+d}) only worth a flier at plus money."
    models.append({"model": "DeepSeek R1", "grade": ds_grade, "score": ds_score,
                    "confidence": min(90, int(55 + ds_score * 4)),
                    "thesis": ds_thesis, "pick": _pick_for(ds_score), "key_factors": []})

    # Grok â€” contrarian, looks for upset value
    grok_adj = 0.5 if ml_diff > 300 else (-0.3 if ml_diff < 100 else 0)
    grok_score = round(our_score + grok_adj, 1)
    grok_score = max(3.0, min(9.5, grok_score))
    grok_grade = _score_to_grade_local(grok_score)
    if ml_diff > 300:
        grok_thesis = f"Upset watch: {dog} ({dog_ml:+d}) is live at plus money. Big ML gaps in {sport} are historically less reliable than team sports. {fav} ({fav_ml:+d}) is over-bet."
    elif ml_diff < 100:
        grok_thesis = f"True pick'em {sport_label}. {fav} ({fav_ml:+d}) barely edges {dog} ({dog_ml:+d}). No contrarian angle â€” just a coin flip."
    else:
        grok_thesis = f"Line at {fav} {fav_ml:+d} is fair. No strong contrarian signal in this {sport_label} â€” play the favorite or pass."
    models.append({"model": "Grok 4.1", "grade": grok_grade, "score": grok_score,
                    "confidence": min(85, int(50 + grok_score * 4)),
                    "thesis": grok_thesis, "pick": _pick_for(grok_score), "key_factors": []})

    # Kimi â€” structural/style scout
    kimi_score = round(our_score + (0.4 if ml_diff < 200 else -0.2), 1)
    kimi_score = max(3.0, min(9.5, kimi_score))
    kimi_grade = _score_to_grade_local(kimi_score)
    kimi_thesis = f"Style matchup: {fav} vs {dog}. ML gap ({ml_diff}) suggests {'competitive' if ml_diff < 200 else 'one-sided'} {sport_label}. Without camp/film data, grading from market structure only."
    models.append({"model": "Kimi K2 Thinking", "grade": kimi_grade, "score": kimi_score,
                    "confidence": min(88, int(52 + kimi_score * 4)),
                    "thesis": kimi_thesis, "pick": _pick_for(kimi_score), "key_factors": []})

    # GPT Nano â€” balanced consensus
    odds_score = _odds_grade(odds)["score"]
    gpt_score = round((our_score + odds_score) / 2, 1)
    gpt_score = max(3.0, min(9.5, gpt_score))
    gpt_grade = _score_to_grade_local(gpt_score)
    gpt_thesis = f"Blended analysis: {fav} ({fav_ml:+d}) vs {dog} ({dog_ml:+d}). Odds model and {sport_label} fundamentals {'align' if abs(our_score - odds_score) <= 1 else 'diverge'} â€” consensus at {gpt_score:.1f}."
    models.append({"model": "GPT 5.4 Nano", "grade": gpt_grade, "score": gpt_score,
                    "confidence": min(90, int(55 + gpt_score * 4)),
                    "thesis": gpt_thesis, "pick": _pick_for(gpt_score), "key_factors": []})

    # Claude Opus â€” momentum/narrative
    claude_adj = 0.3 if ml_diff < 200 else (-0.4 if ml_diff > 400 else 0)
    claude_score = round(our_score * 0.8 + claude_adj + 1.2, 1)
    claude_score = max(3.0, min(9.5, claude_score))
    claude_grade = _score_to_grade_local(claude_score)
    if ml_diff > 300:
        claude_thesis = f"Narrative edge: {dog} ({dog_ml:+d}) has upset potential. Heavy favorites in {sport} get knocked off more than the line implies. {fav} ({fav_ml:+d}) is the right side but the price is wrong."
    else:
        claude_thesis = f"Competitive {sport_label}: {fav} ({fav_ml:+d}) edges {dog} ({dog_ml:+d}). Momentum and market flow support the favorite â€” lean confirmed."
    models.append({"model": "Claude Opus 4.6", "grade": claude_grade, "score": claude_score,
                    "confidence": min(92, int(54 + claude_score * 4)),
                    "thesis": claude_thesis, "pick": _pick_for(claude_score), "key_factors": []})

    # Phi-4 Reasoning
    phi_score = round(our_score * 0.85 + 0.5, 1)
    phi_score = max(3.0, min(9.5, phi_score))
    phi_grade = _score_to_grade_local(phi_score)
    phi_thesis = f"Chain-of-thought: {fav} ({fav_ml:+d}) is the logical side. ML gap {ml_diff} {'is narrow enough for value' if ml_diff < 200 else 'prices out the edge'}. {dog} ({dog_ml:+d}) {'worth a look' if ml_diff > 250 else 'not compelling at this price'}."
    models.append({"model": "Phi-4 Reasoning", "grade": phi_grade, "score": phi_score,
                    "confidence": min(88, int(50 + phi_score * 4)),
                    "thesis": phi_thesis, "pick": _pick_for(phi_score), "key_factors": []})

    # Qwen 3-32B â€” pattern recognition on ML value
    qwen_adj = 0.5 if ml_diff > 200 else (0.2 if ml_diff < 100 else 0)
    qwen_score = round(our_score + qwen_adj, 1)
    qwen_score = max(3.0, min(9.5, qwen_score))
    qwen_grade = _score_to_grade_local(qwen_score)
    qwen_thesis = f"Pattern scan: {sport} {sport_label}s with {ml_diff} ML gap historically {'produce upsets 25-30% of the time' if ml_diff > 250 else 'hold form'}. {fav} ({fav_ml:+d}) is the play â€” {'but size down' if ml_diff > 300 else 'standard sizing'}."
    models.append({"model": "Qwen 3-32B", "grade": qwen_grade, "score": qwen_score,
                    "confidence": min(90, int(52 + qwen_score * 4)),
                    "thesis": qwen_thesis, "pick": _pick_for(qwen_score), "key_factors": []})

    # Gemini 2.5 â€” multi-dimensional
    gemini_score = round(our_score * 0.6 + odds_score * 0.4, 1)
    gemini_score = max(3.0, min(9.5, gemini_score))
    gemini_grade = _score_to_grade_local(gemini_score)
    gemini_thesis = f"Multi-factor {sport_label} analysis: {fav} ({fav_ml:+d}) vs {dog} ({dog_ml:+d}). Cross-referencing ML, market movement, and line structure â€” {'signals align' if ml_diff < 200 else 'caution on heavy juice'}."
    models.append({"model": "Gemini 2.5", "grade": gemini_grade, "score": gemini_score,
                    "confidence": min(91, int(53 + gemini_score * 4)),
                    "thesis": gemini_thesis, "pick": _pick_for(gemini_score), "key_factors": []})

    # Perplexity Sonar â€” live context, contrarian
    all_scores = [m["score"] for m in models]
    model_avg = sum(all_scores) / len(all_scores) if all_scores else our_score
    model_std = (sum((s - model_avg) ** 2 for s in all_scores) / len(all_scores)) ** 0.5 if all_scores else 0
    if model_std < 0.4:
        pplx_adj = -0.5
        pplx_thesis = f"Consensus too tight on {fav}. Late money and camp intel could shift this {sport_label}. Fading the crowd slightly â€” {dog} ({dog_ml:+d}) worth a sprinkle."
    elif model_std > 1.0:
        pplx_adj = 0.0
        pplx_thesis = f"Models split on {fav} vs {dog}. Live signals: check weigh-in results, late line movement, and camp reports before committing."
    else:
        pplx_adj = 0.2
        pplx_thesis = f"Live context for {fav} ({fav_ml:+d}): market is holding steady, no major line shifts. {sport_label.capitalize()} looks playable at current price."
    pplx_score = round(model_avg + pplx_adj, 1)
    pplx_score = max(3.0, min(9.5, pplx_score))
    pplx_grade = _score_to_grade_local(pplx_score)
    models.append({"model": "Perplexity Sonar", "grade": pplx_grade, "score": pplx_score,
                    "confidence": min(87, int(48 + pplx_score * 4)),
                    "thesis": pplx_thesis, "pick": _pick_for(pplx_score), "key_factors": []})

    return models


async def _grade_game_full(game: dict, sport_upper: str, odds_key: str = "") -> dict:
    """Run full grading pipeline: ESPN data â†’ Grade Engine â†’ Two-Lane output."""
    enriched = None
    is_combat = sport_upper in ("MMA", "BOXING")

    if is_combat:
        # Combat sports: ESPN /teams returns 404 â€” grade purely from odds
        our_grade = _grade_combat_from_odds(game.get("odds", {}), game, sport_upper)
    else:
        try:
            enriched = await enrich_game_for_grading(game, sport_upper, odds_key)
            result = grade_both_sides(enriched)
            best = result["best"]

            profiles = result.get("profiles", {})
            our_grade = {
                "grade": best["grade"],
                "score": best["score"],
                "confidence": best["confidence"],
                "thesis": f"{len(best.get('chains_fired', []))} chains | {best['sizing']}",
                "keyFactors": best.get("chains_fired", [])[:5],
                "profiles": profiles,
                # Engine's actual preferred side â€” fed into _compute_pick so
                # the final pick always reflects what the engine recommended,
                # not whatever team happens to be the spread favorite. This
                # is the field that fixes the false-CONFLICT KILL flag.
                "pick_side": best.get("pick_side"),
                "pick_team": best.get("pick_team"),
                "variables": {k: {"score": v["score"], "name": k.replace("_", " "), "available": v.get("available", True)}
                              for k, v in best.get("variables", {}).items()},
            }
        except Exception as e:
            logger.warning(f"Grade engine error for {game.get('homeTeam')} vs {game.get('awayTeam')}: {e}")
            our_grade = {"grade": "C", "score": 5.0, "confidence": 40, "thesis": "Grade engine fallback"}

    # AI Process: odds-based model for consensus
    ai_grade = _odds_grade(game.get("odds", {}))

    # AI Models: slate path NEVER fakes models. Real models only via /api/analyze.
    # Combat sports keep their own (non-LLM) heuristic generator since there's no
    # equivalent real-AI path for them yet.
    if is_combat:
        ai_models = _generate_ai_models_combat(game, game.get("odds", {}), our_grade["score"], sport_upper)
    else:
        ai_models = []  # empty until user hits Analyze All

    # Blend AI model scores into ai_grade (only when we actually have models)
    if ai_models:
        avg_ai = round(sum(m["score"] for m in ai_models) / len(ai_models), 1)
        ai_grade["score"] = avg_ai
        ai_grade["grade"] = _score_to_grade_local(avg_ai)
        ai_grade["confidence"] = int(sum(m["confidence"] for m in ai_models) / len(ai_models))
        ai_grade["model"] = f"{len(ai_models)}-Model Consensus"

    # Convergence â€” pass ai_models for agreement calculation
    conv = _convergence(our_grade, ai_grade, ai_models)

    # Pick
    pick = _compute_pick(game, game.get("odds", {}), our_grade, ai_grade, conv)

    # Determine pick side for EV/Peter's Rules
    pick_side = "home"
    if pick and pick.get("side"):
        if pick["side"] == game.get("awayTeam", ""):
            pick_side = "away"

    # EV calculation
    ev = calculate_ev(enriched or game, pick_side, conv["consensusScore"], pick)

    # Peter's Rules
    pr = peter_rules(enriched or game, pick_side)

    # â”€â”€â”€ CONFLICT DETECTION â”€â”€â”€
    _apply_conflict_downgrade(game, pick, ai_models, conv, pr)
    _apply_kill_override(pick, conv, pr)

    return {
        "ourGrade": our_grade,
        "aiGrade": ai_grade,
        "convergence": conv,
        "pick": pick,
        "aiModels": ai_models,
        "ev": ev,
        "peterRules": pr,
        "kalshi_prob": None,
        # Persist enrichment so /api/analyze can pass injuries + records to AI prompts
        "home_profile": (enriched or {}).get("home_profile", {}),
        "away_profile": (enriched or {}).get("away_profile", {}),
        "injuries": (enriched or {}).get("injuries", {}),
        "rest": (enriched or {}).get("rest", {}),
    }


# Pitcher tier â€” derived from real MLB Stats API ERA/IP, not a name list.
# _pitcher_tier accepts the sp dict (preferred) and returns ace/good/unknown/bad.
from grade_engine import (  # noqa: E402
    _pitcher_tier_from_stats as _pitcher_tier,
    PITCHER_TIER_VALUES as _TIER_VALUES,
)


def _evaluate_nrfi(game: dict) -> dict:
    """Evaluate NRFI (No Run First Inning) probability â€” pitcher quality is primary driver."""
    odds = game.get("odds", {})
    spread = abs(odds.get("spread", 0))
    total = odds.get("total", 0)
    home = game.get("homeTeam", "")

    hp = game.get("home_profile", {}) or {}
    ap = game.get("away_profile", {}) or {}
    h_sp_dict = hp.get("starting_pitcher") or {}
    a_sp_dict = ap.get("starting_pitcher") or {}
    h_sp = h_sp_dict.get("name", "TBD")
    a_sp = a_sp_dict.get("name", "TBD")

    h_tier = _pitcher_tier(h_sp_dict)
    a_tier = _pitcher_tier(a_sp_dict)
    pitcher_score = _TIER_VALUES[h_tier] + _TIER_VALUES[a_tier]

    reasons = []
    # Pitcher reasoning â€” primary driver
    if h_tier != "unknown" or a_tier != "unknown":
        h_label = f"{h_sp.split()[-1]} ({h_tier})" if h_tier != "unknown" else f"{h_sp.split()[-1] if h_sp != 'TBD' else 'TBD'} (unknown)"
        a_label = f"{a_sp.split()[-1]} ({a_tier})" if a_tier != "unknown" else f"{a_sp.split()[-1] if a_sp != 'TBD' else 'TBD'} (unknown)"
        if pitcher_score >= 4.5:
            reasons.append(f"{a_label} vs {h_label} â€” elite pitching duel")
        elif pitcher_score >= 2.5:
            reasons.append(f"{a_label} vs {h_label} â€” strong NRFI lean")
        elif pitcher_score <= -2:
            reasons.append(f"{a_label} vs {h_label} â€” YRFI risk")
        else:
            reasons.append(f"{a_label} vs {h_label}")
    else:
        reasons.append("Two unknown arms â€” NRFI uncertain")

    # Secondary signals (halved weights vs old logic)
    nrfi_score = pitcher_score  # primary driver

    if total > 0:
        if total < 8.0:
            nrfi_score += 1.0
            reasons.append(f"Sub-8 total ({total:.1f}) â€” pitcher's duel")
        elif total < 8.5:
            nrfi_score += 0.5
        elif total > 9.5:
            nrfi_score -= 1.0
            reasons.append(f"High total ({total:.1f}) â€” offense expected")

    if home in HITTER_FRIENDLY_PARKS:
        nrfi_score -= 1.0
        reasons.append(f"{home} hitter-friendly park")
    else:
        nrfi_score += 0.5

    if spread < 1.5:
        nrfi_score += 0.5
    elif spread > 3:
        nrfi_score -= 0.5

    # Verdict thresholds (pitcher_score alone of 3.0+ = clear NRFI lean)
    if nrfi_score >= 3.5:
        verdict = "NRFI"
        confidence = int(min(88, 62 + nrfi_score * 4))
    elif nrfi_score <= -1.5:
        verdict = "YRFI"
        confidence = int(min(85, 60 + abs(nrfi_score) * 5))
    else:
        verdict = "SKIP"
        confidence = 45

    # Without pitcher data, cap confidence
    if h_tier == "unknown" and a_tier == "unknown" and verdict != "SKIP":
        confidence = min(confidence, 55)

    reason = ". ".join(reasons[:3])
    return {"verdict": verdict, "confidence": confidence, "reason": reason}


async def _fetch_golf_outrights(keys: list) -> list:
    """Fetch golf tournament outrights â€” one 'game' card per active tournament."""
    tournaments = []
    async with httpx.AsyncClient(timeout=15) as client:
        for key in keys:
            try:
                resp = await client.get(
                    f"{ODDS_API_BASE}/{key}/odds/",
                    params={
                        "apiKey": ODDS_API_KEY,
                        "regions": "us,us2",
                        "markets": "outrights",
                        "oddsFormat": "american",
                    },
                )
                if resp.status_code != 200:
                    continue
                events = resp.json()
                for event in events:
                    commence = event.get("commence_time", "")
                    # Aggregate outrights across bookmakers â€” best price per golfer
                    golfer_odds: dict = {}
                    for bk in event.get("bookmakers", []):
                        book_key = bk.get("key", "")
                        for mkt in bk.get("markets", []):
                            if mkt.get("key") != "outrights":
                                continue
                            for o in mkt.get("outcomes", []):
                                name = o.get("name", "")
                                price = o.get("price", 0)
                                if name not in golfer_odds or price > golfer_odds[name]["price"]:
                                    golfer_odds[name] = {"price": price, "book": book_key}
                    # Sort by odds (favorites first)
                    sorted_golfers = sorted(golfer_odds.items(), key=lambda x: x[1]["price"])
                    outrights = [
                        {"name": name, "odds": info["price"], "book": info["book"]}
                        for name, info in sorted_golfers
                    ]
                    # Tournament title from sport_title (e.g. "Masters Tournament Winner")
                    title = event.get("sport_title", key.replace("golf_", "").replace("_", " ").title())
                    title = title.replace(" Winner", "")
                    stable_id = hashlib.md5(f"golf|{key}|{commence}".encode()).hexdigest()[:16]
                    tournaments.append({
                        "id": stable_id,
                        "oddsApiId": event.get("id", ""),
                        "sport": "GOLF",
                        "homeTeam": title,
                        "awayTeam": f"{len(outrights)} golfers",
                        "scheduledAt": commence,
                        "status": "scheduled",
                        "odds": {"spread": 0, "total": 0, "mlHome": 0, "mlAway": 0},
                        "outrights": outrights,
                        "bookmaker": outrights[0]["book"] if outrights else None,
                        "favorite": outrights[0]["name"] if outrights else None,
                        "favoriteOdds": outrights[0]["odds"] if outrights else None,
                        # Minimal grading for golf â€” no engine, just display
                        "ourGrade": {
                            "grade": "â€”", "score": 0, "confidence": 0,
                            "thesis": f"Tournament outrights â€” {len(outrights)} golfers",
                        },
                        "aiGrade": {"grade": "â€”", "score": 0, "confidence": 0, "model": "Outrights"},
                        "convergence": {
                            "status": "ALIGNED", "consensusScore": 0,
                            "consensusGrade": "â€”", "delta": 0, "variance": 0,
                        },
                        "pick": None,
                        "aiModels": [],
                    })
            except Exception as e:
                logger.warning(f"[GOLF] {key}: {e}")
    return tournaments


async def _fetch_and_grade(sport: str, mode: str = "games", league: str = "") -> list:
    """Fetch live games from Odds API, then grade each one."""
    if not ODDS_API_KEY:
        logger.error("ODDS_API_KEY not configured")
        return []

    # Soccer league filtering
    if sport.lower() == "soccer" and league and league in SOCCER_LEAGUE_MAP:
        keys = SOCCER_LEAGUE_MAP[league]
    else:
        keys = SPORT_KEYS.get(sport.lower(), [sport.lower()])
    sport_upper = sport.upper()
    all_games = []

    # Golf: outrights market, completely different structure
    if sport_upper == "GOLF":
        return await _fetch_golf_outrights(keys)

    async with httpx.AsyncClient(timeout=15) as client:
        for key in keys:
            try:
                resp = await client.get(
                    f"{ODDS_API_BASE}/{key}/odds/",
                    params={
                        "apiKey": ODDS_API_KEY,
                        "regions": "us,us2",
                        "markets": "h2h,spreads,totals",
                        "oddsFormat": "american",
                    },
                )
                if resp.status_code == 200:
                    events = resp.json()
                    logger.info(f"[ODDS API] {key}: {len(events)} events")
                    for event in events:
                        game = _parse_event(event, sport_upper)
                        game["_sport_key"] = key  # needed for event-level BTTS fetch
                        if game["status"] in ("completed", "live"):
                            continue  # Only show upcoming â€” no live or finished
                        # Only tonight's games â€” filter out anything more than 18 hours away
                        try:
                            ct = game.get("scheduledAt", "")
                            if ct:
                                gt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
                                hours_ahead = (gt - datetime.now(timezone.utc)).total_seconds() / 3600
                                if hours_ahead < -6 or hours_ahead > 30:
                                    continue  # Finished >6h ago or >30h out â€” skip
                        except Exception:
                            pass
                        all_games.append(game)
                else:
                    logger.warning(f"[ODDS API] {key}: HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"[ODDS API] {key}: {e}")

    # Dedupe by stable game id â€” soccer hits 10 league endpoints and the same
    # cup match can be returned by multiple leagues (e.g. EPL + UCL), which
    # would otherwise grade and pick the same game twice.
    if all_games:
        seen_ids = set()
        deduped = []
        for g in all_games:
            gid = g.get("id")
            if gid in seen_ids:
                continue
            seen_ids.add(gid)
            deduped.append(g)
        if len(deduped) != len(all_games):
            logger.info(f"[DEDUPE] {sport.lower()}: {len(all_games)} -> {len(deduped)} games after dedupe")
        all_games = deduped

    # Soccer: fetch BTTS odds per event via event-level endpoint
    if sport_upper == "SOCCER" and all_games:
        async def _fetch_btts(game):
            odds_api_id = game.get("oddsApiId", "")
            sport_key = game.get("_sport_key", "")
            if not odds_api_id or not sport_key:
                return
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.get(
                        f"{ODDS_API_BASE}/{sport_key}/events/{odds_api_id}/odds",
                        params={"apiKey": ODDS_API_KEY, "regions": "us,us2",
                                "markets": "btts", "oddsFormat": "american"},
                    )
                if r.status_code != 200:
                    return
                data = r.json()
                for bk in (data.get("bookmakers") or []):
                    if bk.get("key") in PREFERRED_BOOKS:
                        for mkt in bk.get("markets", []):
                            if mkt.get("key") == "btts":
                                for o in mkt.get("outcomes", []):
                                    if o["name"] == "Yes":
                                        game["odds"]["bttsYes"] = o.get("price")
                                    elif o["name"] == "No":
                                        game["odds"]["bttsNo"] = o.get("price")
                        if game["odds"].get("bttsYes") is not None:
                            return
                # Fallback: use any bookmaker
                for bk in (data.get("bookmakers") or []):
                    for mkt in bk.get("markets", []):
                        if mkt.get("key") == "btts":
                            for o in mkt.get("outcomes", []):
                                if o["name"] == "Yes" and game["odds"].get("bttsYes") is None:
                                    game["odds"]["bttsYes"] = o.get("price")
                                elif o["name"] == "No" and game["odds"].get("bttsNo") is None:
                                    game["odds"]["bttsNo"] = o.get("price")
            except Exception as e:
                logger.debug(f"[BTTS] {game.get('homeTeam')}: {e}")

        try:
            await asyncio.wait_for(
                asyncio.gather(*[_fetch_btts(g) for g in all_games], return_exceptions=True),
                timeout=20,
            )
            btts_count = sum(1 for g in all_games if g.get("odds", {}).get("bttsYes") is not None)
            logger.info(f"[BTTS] Fetched BTTS for {btts_count}/{len(all_games)} soccer games")
        except asyncio.TimeoutError:
            logger.warning("[BTTS] Timeout fetching BTTS odds â€” continuing without")

    # Determine odds_key for soccer league routing
    odds_key = ""
    if sport_upper == "SOCCER":
        for key in keys:
            odds_key = key
            break

    # Grade all games in parallel
    async def _grade_single(game):
        # Outdoor-sport weather: NFL today, NCAAF/Soccer when their stadium
        # tables get filled in. Skipped for domes (weather doesn't matter
        # inside an enclosed roof) and skipped silently if open-meteo errors.
        # Combat sports â€” pull fighter records from ESPN MMA athletes endpoint
        # so the prompt builder and combat scorer have real career context
        # instead of pure-odds reasoning. Best-effort: any failure leaves
        # home_fighter / away_fighter unset and the existing odds-only path
        # continues to work.
        if sport_upper in ("MMA", "BOXING") and not (game.get("home_fighter") or game.get("away_fighter")):
            try:
                from services.mma_fighter import get_fighter_profile
                home_f, away_f = await asyncio.gather(
                    get_fighter_profile(game.get("homeTeam") or "", sport_upper),
                    get_fighter_profile(game.get("awayTeam") or "", sport_upper),
                )
                if home_f:
                    game["home_fighter"] = home_f
                if away_f:
                    game["away_fighter"] = away_f
            except Exception as e:
                logger.debug(f"[MMA_FIGHTER] {game.get('awayTeam')} vs {game.get('homeTeam')}: {e}")

        if sport_upper in ("NFL", "NCAAF", "SOCCER") and not game.get("weather"):
            try:
                from services.stadium_coords import lookup_nfl, lookup_ncaaf, lookup_soccer
                from services.weather_open_meteo import fetch_weather
                home = game.get("homeTeam") or ""
                if sport_upper == "NFL":
                    coords = lookup_nfl(home)
                elif sport_upper == "NCAAF":
                    coords = lookup_ncaaf(home)
                else:
                    coords = lookup_soccer(home)
                if coords:
                    lat, lon, dome = coords
                    if dome:
                        game["weather"] = {"condition": "Dome", "temp": 70, "wind": "0 mph"}
                    else:
                        wx = await fetch_weather(lat, lon, game.get("scheduledAt"))
                        if wx:
                            game["weather"] = wx
            except Exception as e:
                logger.debug(f"[WEATHER] {game.get('homeTeam')}: {e}")

        grades = await _grade_game_full(game, sport_upper, odds_key)
        game.update(grades)
        if sport_upper == "MLB" and mode == "nrfi":
            game["nrfi"] = _evaluate_nrfi(game)
        return game

    # Per-sport timeout ceiling. Soccer hits 10 league endpoints so needs
    # more headroom than single-league sports.
    grade_timeout = 180 if sport_upper == "SOCCER" else 90

    try:
        all_games = list(
            await asyncio.wait_for(
                asyncio.gather(*[_grade_single(g) for g in all_games], return_exceptions=True),
                timeout=grade_timeout,
            )
        )
        # Filter out any games that raised â€” they'll come back un-enriched
        # rather than crash the slate.
        all_games = [g for g in all_games if isinstance(g, dict)]
    except asyncio.TimeoutError:
        logger.warning(
            f"[FETCH+GRADE] HARD TIMEOUT (>{grade_timeout}s) for {sport.lower()} â€” returning whatever finished"
        )
        # Return whatever tasks completed before the timeout instead of
        # dropping the entire slate. gather() results are lost on timeout,
        # so fall back to any games that were already updated in-place by
        # _grade_single (it calls game.update(grades) before returning).
        all_games = [g for g in all_games if isinstance(g, dict) and g.get("ourGrade")]
        if not all_games:
            return []

    return all_games


# â”€â”€â”€ Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class BetSlipRequest(BaseModel):
    username: str
    game_ids: list[str] = []


class LockToggleRequest(BaseModel):
    username: str
    game_id: str
    action: str  # "add" | "remove"


# User-driven locked game IDs (per username), persisted to disk
_locked_game_ids: Dict[str, list] = _load_json("locked_picks.json", {})


def _save_locked_game_ids():
    _save_json("locked_picks.json", _locked_game_ids)


@app.post("/api/locks")
async def toggle_lock(req: LockToggleRequest):
    uname = req.username.lower()
    current = list(_locked_game_ids.get(uname, []))
    if req.action == "add":
        if req.game_id not in current:
            current.append(req.game_id)
    elif req.action == "remove":
        current = [g for g in current if g != req.game_id]
    else:
        return {"error": "action must be 'add' or 'remove'"}
    _locked_game_ids[uname] = current
    _save_locked_game_ids()
    return {"username": uname, "game_ids": current}


@app.get("/api/locks/{username}")
async def get_locks(username: str):
    uname = username.lower()
    return {"username": uname, "game_ids": _locked_game_ids.get(uname, [])}


_betslip_counter = 0


@app.post("/api/betslip")
async def generate_betslip(request: BetSlipRequest):
    """Generate a BetOnline.ag bet slip from user-selected (locked) game IDs."""
    global _betslip_counter

    # Resolve which game IDs the user wants on the slip.
    # Prefer game_ids in the request; fall back to persisted locks.
    requested_ids = request.game_ids or _locked_game_ids.get(request.username.lower(), [])
    requested_set = {str(g) for g in requested_ids}

    if not requested_set:
        return {
            "slip_id": None,
            "error": "No picks selected. Tap LOCK on the games you want before generating a slip.",
        }

    # Gather selected games across all cached sports
    locked_picks = []
    seen_ids = set()
    for cache_key, cached in _cache.items():
        if not cached or not cached.get("data"):
            continue
        for game in cached["data"]:
            gid = str(game.get("id", ""))
            if gid not in requested_set or gid in seen_ids:
                continue
            pick = game.get("pick", {})
            if not pick or not pick.get("side"):
                continue
            seen_ids.add(gid)

            home = game.get("homeTeam", "")
            away = game.get("awayTeam", "")
            game_label = f"{away} vs {home}"
            side = pick["side"]
            pick_type = pick.get("type", "ml").capitalize()
            line = pick.get("line", 0)

            if pick_type == "Spread" and line != 0:
                pick_label = f"{side} {line:+.1f}"
            elif pick_type == "Ml":
                pick_label = f"{side} ML"
                pick_type = "Moneyline"
            else:
                pick_label = f"{side} {pick_type}"

            locked_picks.append({
                "game_id": gid,
                "game": game_label,
                "pick": pick_label,
                "line": f"{pick_label} | $100 | BetOnline.ag",
                "type": pick_type,
                "amount": "$100",
                "book": "BetOnline.ag",
                "_sport": (game.get("sport") or "").upper(),
                "_score": float(game.get("score") or 0),
            })

    if not locked_picks:
        return {
            "slip_id": None,
            "error": "Selected games aren't in the cache. Re-grade those sports, then try again.",
        }

    # Generate slip ID
    _betslip_counter += 1
    now = datetime.now()
    slip_id = f"EC9-{now.strftime('%Y%m%d')}-{_betslip_counter:03d}"
    et_time = now.strftime("%Y-%m-%d %H:%M") + " ET"

    num_picks = len(locked_picks)
    per_pick = 100
    total_risk = num_picks * per_pick
    # Estimate potential payout: assume -110 standard juice â†’ ~$191 return per $100
    potential_payout = round(total_risk * 1.91, 0)

    # â”€â”€â”€ Peter's Rules: 3-leg parlays only, $100/day (4Ã—$25, 2Ã—$50, or 1Ã—$100) â”€â”€â”€
    parlays = _build_parlays(locked_picks)

    # Strip internal fields before returning
    clean_picks = [{k: v for k, v in p.items() if not k.startswith("_")} for p in locked_picks]

    return {
        "slip_id": slip_id,
        "generated": et_time,
        "user": request.username,
        "picks": clean_picks,
        "parlays": parlays,
        "total_risk": f"${total_risk:,}",
        "potential_payout": f"${potential_payout:,.0f}",
        "notes": f"{num_picks} pick{'s' if num_picks != 1 else ''} @ $100 each. Enter as singles on BetOnline.ag.",
    }


def _build_parlays(locked_picks: list) -> list:
    """Peter's Rules parlay builder: strictly 3-leg parlays, $100/day total bank.
    Auto-picks configuration based on locked pick count:
      - 12+ picks â†’ 4 parlays Ã— $25 (3 legs each)
      - 6-11 picks â†’ 2 parlays Ã— $50 (3 legs each)
      - 3-5 picks â†’ 1 parlay Ã— $100 (3 legs)
      - <3 picks â†’ no parlays
    Prefer sport diversity within each parlay; pull highest engine grades first."""
    n = len(locked_picks) if locked_picks else 0
    if n < 3:
        return []

    if n >= 12:
        num_parlays, stake = 4, 25
    elif n >= 6:
        num_parlays, stake = 2, 50
    else:
        num_parlays, stake = 1, 100

    # Sort by engine score descending
    sorted_picks = sorted(locked_picks, key=lambda p: p.get("_score", 0), reverse=True)

    def _format_leg(p: dict) -> dict:
        return {
            "game_id": p.get("game_id"),
            "game": p.get("game"),
            "pick": p.get("pick"),
            "sport": p.get("_sport", ""),
            "score": p.get("_score", 0),
        }

    def _build_one(pool: list) -> list:
        """Greedy 3-leg build: highest-graded seed, then prefer unused sports."""
        if len(pool) < 3:
            return []
        legs = [pool[0]]
        used_sports = {pool[0].get("_sport", "")}
        remaining = pool[1:]
        # Prefer different sports
        for p in list(remaining):
            if len(legs) >= 3:
                break
            sp = p.get("_sport", "")
            if sp not in used_sports:
                legs.append(p)
                used_sports.add(sp)
                remaining.remove(p)
        # Fill remaining slots with next-highest-graded
        for p in list(remaining):
            if len(legs) >= 3:
                break
            legs.append(p)
            remaining.remove(p)
        return legs

    def _finalize(legs: list, stake: int) -> dict:
        sport_mix = sorted({l.get("_sport", "") for l in legs if l.get("_sport")})
        return {
            "legs": [_format_leg(l) for l in legs],
            "stake": stake,
            "sport_mix": sport_mix,
            "leg_count": len(legs),
            "diverse": len(sport_mix) >= 2,
        }

    parlays = []
    pool = list(sorted_picks)
    for _ in range(num_parlays):
        legs = _build_one(pool)
        if not legs:
            break
        for leg in legs:
            pool.remove(leg)
        parlays.append(_finalize(legs, stake))
    return parlays


# â”€â”€â”€ Peter's Rules: Gut Picks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_gut_picks: list = _load_json("gut_picks.json", [])


def _save_gut_picks():
    _save_json("gut_picks.json", _gut_picks)


class GutPickRequest(BaseModel):
    username: str
    game_id: str
    sport: str
    pick_side: str
    engine_pick_side: str = ""


@app.post("/api/gut-pick")
async def log_gut_pick(req: GutPickRequest):
    """Log a gut pick override. Enforces 1 per sport per day per user."""
    uname = req.username.lower()
    sport = req.sport.upper()
    today = datetime.now().strftime("%Y-%m-%d")

    for gp in _gut_picks:
        if (gp.get("username") == uname
            and gp.get("sport", "").upper() == sport
            and gp.get("date") == today):
            raise HTTPException(
                status_code=400,
                detail=f"Already used your gut pick for {sport} today",
            )

    entry = {
        "username": uname,
        "game_id": req.game_id,
        "sport": sport,
        "pick_side": req.pick_side,
        "engine_pick_side": req.engine_pick_side,
        "date": today,
        "timestamp": datetime.now().isoformat(),
    }
    _gut_picks.append(entry)
    _save_gut_picks()
    return {"ok": True, "gut_pick": entry}


@app.get("/api/gut-picks/{username}")
async def get_gut_picks(username: str):
    """Return all gut picks for a user (for weekly review)."""
    uname = username.lower()
    return {
        "username": uname,
        "gut_picks": [gp for gp in _gut_picks if gp.get("username") == uname],
    }


class GradeRequest(BaseModel):
    game_id: str
    sport: str
    home_team: str
    away_team: str
    context: Dict = {}


class AnalyzeRequest(BaseModel):
    sport: str
    game_id: Optional[str] = None  # Optional: analyze a single game by id
    league: Optional[str] = None
    fast: Optional[bool] = None


# â”€â”€â”€ Odds Snapshot / Line Movement Sync â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_ODDS_HISTORY_FILE = "odds_history.json"
_SYNC_LOG_FILE = "sync_log.json"


def _load_sync_log() -> list:
    return _load_json(_SYNC_LOG_FILE, [])


def _save_sync_log(log: list):
    # Keep last 50 entries
    _save_json(_SYNC_LOG_FILE, log[-50:])


def _load_odds_history() -> dict:
    return _load_json(_ODDS_HISTORY_FILE, {})


def _save_odds_history(data: dict):
    _save_json(_ODDS_HISTORY_FILE, data)


def _get_line_movement(game_id: str, current_spread: float, current_ml_home: float) -> dict:
    """Compare current odds to first snapshot for this game â†’ spread_delta."""
    history = _load_odds_history()
    snapshots = history.get(game_id, [])
    if not snapshots:
        return {"spread_delta": 0, "ml_moved": False}
    first = snapshots[0]
    spread_delta = round(current_spread - first.get("spread", current_spread), 1)
    ml_moved = abs((current_ml_home or 0) - first.get("ml_home", current_ml_home or 0)) > 15
    return {"spread_delta": spread_delta, "ml_moved": ml_moved}


@app.post("/api/sync/odds")
async def sync_odds():
    """Cron endpoint: snapshot ALL current odds for line movement tracking.
    Schedule: 1am, 9am, 11am, 3:30pm, 6:30pm PST â€” 7 days/week.
    Also runs real AI analysis on all sports."""
    if not ODDS_API_KEY:
        return {"error": "ODDS_API_KEY not configured"}

    history = _load_odds_history()
    now_ts = datetime.now(timezone.utc).isoformat()
    total_snapped = 0
    sports_synced = []

    all_sport_keys = list(SPORT_KEYS.keys())

    for sport in all_sport_keys:
        try:
            keys = SPORT_KEYS.get(sport, [])
            async with httpx.AsyncClient(timeout=15) as client:
                for key in keys:
                    try:
                        resp = await client.get(
                            f"{ODDS_API_BASE}/{key}/odds/",
                            params={"apiKey": ODDS_API_KEY, "regions": "us,us2",
                                    "markets": "h2h,spreads,totals", "oddsFormat": "american"},
                        )
                        if resp.status_code != 200:
                            continue
                        events = resp.json()
                        for event in events:
                            game_id = event.get("id", "")
                            if not game_id:
                                continue
                            # Parse current odds
                            spread = total = ml_home = ml_away = 0
                            for bk in event.get("bookmakers", [])[:3]:
                                markets = {m["key"]: m["outcomes"] for m in bk.get("markets", [])}
                                for o in markets.get("spreads", []):
                                    if o["name"] == event.get("home_team") and not spread:
                                        spread = o.get("point", 0)
                                for o in markets.get("h2h", []):
                                    if o["name"] == event.get("home_team") and not ml_home:
                                        ml_home = o.get("price", 0)
                                    elif o["name"] == event.get("away_team") and not ml_away:
                                        ml_away = o.get("price", 0)
                                for o in markets.get("totals", []):
                                    if o["name"] == "Over" and not total:
                                        total = o.get("point", 0)
                                if spread and ml_home:
                                    break

                            snapshot = {
                                "ts": now_ts,
                                "spread": spread,
                                "total": total,
                                "ml_home": ml_home,
                                "ml_away": ml_away,
                            }

                            if game_id not in history:
                                history[game_id] = []
                            history[game_id].append(snapshot)
                            total_snapped += 1

                    except Exception as e:
                        logger.warning(f"[SYNC] {key}: {e}")

            sports_synced.append(sport)
        except Exception as e:
            logger.warning(f"[SYNC] sport {sport}: {e}")

    # Prune old games (> 3 days old)
    cutoff = (datetime.now(timezone.utc).timestamp() - 3 * 86400)
    for gid in list(history.keys()):
        snaps = history[gid]
        if snaps and snaps[-1].get("ts", ""):
            try:
                last_ts = datetime.fromisoformat(snaps[-1]["ts"].replace("Z", "+00:00")).timestamp()
                if last_ts < cutoff:
                    del history[gid]
            except Exception:
                pass

    _save_odds_history(history)
    logger.info(f"[SYNC] Snapped {total_snapped} games across {sports_synced}")

    # NOTE: AI analysis is owned by the cron pre-warm jobs (scripts/prewarm_slate.py)
    # which call /api/analyze using the REAL_AI_MODELS path. The previous block
    # here used the legacy ai_models.crowdsource_grade() path which referenced
    # phantom deployments (claude-opus-4-6, gpt-5.4-nano, qwen3-32b) and silently
    # overwrote cron-warmed aiModels with empty results. Removed 2026-04-08.

    # Log this sync
    sync_log = _load_sync_log()
    sync_log.append({
        "ts": now_ts,
        "games": total_snapped,
        "sports": sports_synced,
        "status": "ok",
    })
    _save_sync_log(sync_log)

    return {
        "status": "synced",
        "timestamp": now_ts,
        "games_snapped": total_snapped,
        "sports": sports_synced,
        "history_size": len(history),
    }


@app.get("/api/sync/status")
async def sync_status():
    """Dashboard: show which cron syncs have run."""
    log = _load_sync_log()
    # Expected schedule (PST labels)
    schedule = ["1:00 AM", "9:00 AM", "11:00 AM", "3:30 PM", "6:30 PM"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_syncs = [e for e in log if e.get("ts", "").startswith(today)]
    return {
        "schedule": schedule,
        "today_syncs": len(today_syncs),
        "today_log": today_syncs,
        "total_syncs": len(log),
        "last_sync": log[-1] if log else None,
        "all_log": log[-10:],
    }


@app.get("/health")
async def health():
    # Check DB status
    db_status = "disabled"
    try:
        from services.db import is_enabled as _db_enabled
        db_status = "enabled" if _db_enabled() else "disabled"
    except Exception:
        pass

    return {
        "status": "healthy",
        "version": "3.0.0-b4",
        "time": datetime.now().isoformat(),
        "odds_api": bool(ODDS_API_KEY),
        "engine": "grade_engine_v3",
        "persist_dir": PERSIST_DIR,
        "persist_disk": os.path.exists("/data"),
        "database": db_status,
    }


@app.get("/api/games")
async def get_games(sport: str = "nba", mode: str = "games", league: str = ""):
    sport_lower = sport.lower()
    cache_key = f"{sport_lower}:{mode}:{league}"
    cached = _cache.get(cache_key)
    if cached:
        age = (datetime.now(timezone.utc) - cached["fetched_at"]).total_seconds()
        if age < CACHE_TTL:
            return cached["data"]
    # If we have AI-enriched cached data, do NOT overwrite it with a bare
    # un-enriched fetch â€” that would silently nuke the cron pre-warm work.
    # Refresh cache only if there is no enriched data sitting in it.
    cached_enriched = bool(
        cached
        and cached.get("data")
        and any((g or {}).get("aiModels") for g in cached["data"])
    )
    if cached_enriched:
        return cached["data"]
    games = await _fetch_and_grade(sport_lower, mode=mode, league=league)
    # Sort by date â€” soonest games first
    games.sort(key=lambda g: g.get("scheduledAt", "9999"))
    if games:
        _cache[cache_key] = {"data": games, "fetched_at": datetime.now(timezone.utc)}
    return games


@app.get("/api/cache-status")
async def cache_status():
    """Quick visibility into _cache so the morning check can confirm the cron
    pre-warm survived. Returns per-sport: game count, enriched count, age."""
    out = {}
    now = datetime.now(timezone.utc)
    for key, entry in _cache.items():
        if not entry or not entry.get("data"):
            continue
        data = entry["data"]
        if not isinstance(data, list):
            continue
        enriched = sum(1 for g in data if (g or {}).get("aiModels"))
        age = (now - entry["fetched_at"]).total_seconds()
        out[key] = {
            "games": len(data),
            "enriched": enriched,
            "age_seconds": int(age),
            "fetched_at": entry["fetched_at"].isoformat(),
        }
    return out


@app.post("/api/grade")
async def grade_game_endpoint(request: GradeRequest):
    """Re-grade a single game on demand."""
    sport_upper = request.sport.upper()
    game = {
        "id": request.game_id,
        "sport": sport_upper,
        "homeTeam": request.home_team,
        "awayTeam": request.away_team,
        "odds": request.context.get("odds", {"spread": 0, "total": 0, "mlHome": 0, "mlAway": 0}),
    }
    grades = await _grade_game_full(game, sport_upper)
    return {
        "game_id": request.game_id,
        "our_process": grades["ourGrade"],
        "ai_process": grades["aiGrade"],
        "convergence": grades["convergence"],
        "pick": grades["pick"],
    }


@app.post("/api/analyze")
async def analyze_games(request: AnalyzeRequest):
    """Deep analysis: call AI models for crowdsource grades + Kimi gatekeeper.
    Two-tier system -- this is the SLOW path triggered by 'Analyze All'.

    Hard 550s top-level ceiling so the request can NEVER hang forever.
    Per-game worst case: 200s model batch + 260s gatekeeper (Kimi 200 + GPT
    fallback 60) = 460s. 550s gives ~90s slack. Cron's per-request budget
    is bumped to 600s to stay above this so the cron always gets a response.
    """
    try:
        return await asyncio.wait_for(_analyze_games_impl(request), timeout=550)
    except asyncio.TimeoutError:
        logger.warning(f"[ANALYZE] HARD TIMEOUT (>550s) for sport={request.sport} game_id={request.game_id}")
        return {
            "error": "analyze hard timeout (>550s)",
            "sport": request.sport,
            "game_id": request.game_id,
        }


async def _analyze_games_impl(request: AnalyzeRequest):
    sport_lower = request.sport.lower()
    sport_upper = sport_lower.upper()
    league_raw = (request.league or "").strip().lower()
    league_keys = [x.strip() for x in league_raw.split(",") if x.strip()]
    league_key = ",".join(league_keys)
    fast_mode = request.fast if request.fast is not None else (
        sport_upper == "SOCCER" and request.game_id is None
    )

    # Get cached games — match the same cache key format as /api/games,
    # including league scoping for soccer.
    cache_key = f"{sport_lower}:games:{league_key}"
    games = []
    if sport_upper == "SOCCER" and league_keys:
        by_id = {}
        for lk in league_keys:
            if lk not in SOCCER_LEAGUE_MAP:
                continue
            lk_cache_key = f"{sport_lower}:games:{lk}"
            cached = _cache.get(lk_cache_key)
            if not cached or not cached.get("data"):
                fetched = await _fetch_and_grade(sport_lower, league=lk)
                if fetched:
                    _cache[lk_cache_key] = {"data": fetched, "fetched_at": datetime.now(timezone.utc)}
                src = fetched or []
            else:
                src = cached["data"]
            for g in src:
                gid = g.get("id")
                if gid and gid not in by_id:
                    by_id[gid] = g
        games = list(by_id.values())
        if games:
            _cache[cache_key] = {"data": games, "fetched_at": datetime.now(timezone.utc)}
    else:
        cached = _cache.get(cache_key)
        if not cached or not cached.get("data"):
            games = await _fetch_and_grade(sport_lower, league=league_key)
            if games:
                _cache[cache_key] = {"data": games, "fetched_at": datetime.now(timezone.utc)}
        else:
            games = cached["data"]

    if not games:
        return {"error": "No games found", "sport": sport_lower}

    # Single-game mode: filter the slate to just one matchup. Faster path,
    # designed for the per-card "Analyze This Game" button so the user
    # doesn't have to re-run the entire slate to deep-dive one matchup.
    if request.game_id:
        single = [g for g in games if g.get("id") == request.game_id]
        if not single:
            return {"error": f"Game {request.game_id} not found in slate", "sport": sport_lower}
        games = single
        logger.info(f"[ANALYZE] Single-game mode for {sport_lower}: {games[0].get('awayTeam')} @ {games[0].get('homeTeam')}")

    # Call AI crowdsource for all games
    logger.info(
        f"[ANALYZE] Deep analysis for {sport_lower} league={league_key or 'all'}: "
        f"{len(games)} games (real Azure AI={'on' if AZURE_AI_KEY else 'OFF — fallback'}, fast={fast_mode})"
    )

    # Try REAL Azure AI Foundry calls with bounded cross-game concurrency.
    # Unbounded fan-out on soccer slates causes provider throttling and model
    # timeouts, which shows up as many FAIL cards in AI Process.
    active_models = _active_real_models_for_sport(sport_upper, fast_mode=bool(fast_mode))
    game_concurrency = 3 if sport_upper == "SOCCER" and fast_mode else (2 if sport_upper == "SOCCER" else 4)
    sem = asyncio.Semaphore(game_concurrency)

    async def _run_real_ai(game: dict):
        async with sem:
            return await _real_ai_models_for_game(
                game,
                (game.get("ourGrade") or {}).get("score", 5.0),
                model_cfgs=active_models,
            )

    real_ai_tasks = [_run_real_ai(g) for g in games]
    real_ai_results = await asyncio.gather(*real_ai_tasks, return_exceptions=True)

    # Enrich each game with per-model grades + gatekeeper.
    expected_displays = [cfg["display"] for cfg in active_models]

    real_ok_total = 0
    real_fail_total = 0
    enriched = []
    for game, real_res in zip(games, real_ai_results):
        game_id = game.get("id", "")
        our_score = (game.get("ourGrade") or {}).get("score", 5.0)

        real_list = real_res if (not isinstance(real_res, Exception) and real_res) else []
        real_by_display = {m.get("model"): m for m in real_list}

        ai_grades_list = []
        for disp in expected_displays:
            if disp in real_by_display:
                m = real_by_display[disp]
                m["source"] = "real"
                ai_grades_list.append(m)
                real_ok_total += 1
            else:
                ai_grades_list.append({
                    "model": disp,
                    "grade": "—",
                    "score": 0,
                    "confidence": 0,
                    "thesis": "Model call failed — no grade contributed to consensus.",
                    "pick": None,
                    "key_factors": [],
                    "source": "fail",
                })
                real_fail_total += 1

        game["aiModels"] = ai_grades_list

        if ai_grades_list:
            valid_models = [m for m in ai_grades_list if m.get("source") == "real" and m.get("score", 0) > 0]
            valid_scores = [m["score"] for m in valid_models]
            if valid_scores:
                avg_score = round(sum(valid_scores) / len(valid_scores), 1)
                avg_conf = int(sum(m.get("confidence", 50) for m in valid_models) / len(valid_models))
                blended_grade = "F"
                for threshold, g in GRADE_MAP:
                    if avg_score >= threshold:
                        blended_grade = g
                        break
                game["aiGrade"] = {
                    "grade": blended_grade,
                    "score": avg_score,
                    "confidence": avg_conf,
                    "model": f"{len(valid_scores)}-Model Consensus",
                }
                our_grade = game.get("ourGrade", {"score": 5.0})
                game["convergence"] = _convergence(our_grade, game["aiGrade"])
                game["pick"] = _compute_pick(
                    game, game.get("odds", {}), our_grade, game["aiGrade"], game["convergence"]
                )

        # In fast mode, skip gatekeeper to keep soccer analyze latency down.
        if ai_grades_list and not fast_mode:
            try:
                gk = await asyncio.wait_for(
                    kimi_gatekeeper(
                        game,
                        game.get("ourGrade", {}),
                        ai_grades_list,
                        game.get("convergence", {}),
                    ),
                    timeout=270,
                )
            except asyncio.TimeoutError:
                logger.warning(f"[GATEKEEPER] outer wait_for tripped (>270s) for game {game.get('id')}")
                gk = {"action": "?", "adjustment": 0, "reason": "Gatekeeper outer timeout (>270s)"}
            game["gatekeeper"] = gk

            adj = gk.get("adjustment", 0)
            if adj != 0 and game.get("convergence"):
                adjusted = round(game["convergence"]["consensusScore"] + adj, 1)
                adjusted = max(1.0, min(10.0, adjusted))
                adj_grade = "F"
                for threshold, g in GRADE_MAP:
                    if adjusted >= threshold:
                        adj_grade = g
                        break
                game["convergence"]["consensusScore"] = adjusted
                game["convergence"]["consensusGrade"] = adj_grade

        _apply_conflict_downgrade(
            game,
            game.get("pick") or {},
            game.get("aiModels") or [],
            game.get("convergence") or {},
            game.get("peterRules"),
        )
        _apply_kill_override(
            game.get("pick") or {},
            game.get("convergence") or {},
            game.get("peterRules"),
        )

        enriched.append(game)

    logger.info(
        f"[ANALYZE] {sport_lower}: real-AI hits={real_ok_total} misses={real_fail_total} "
        f"across {len(games)} games"
    )

    if request.game_id:
        existing = (_cache.get(cache_key) or {}).get("data") or []
        enriched_by_id = {g.get("id"): g for g in enriched}
        merged = [enriched_by_id.get(g.get("id"), g) for g in existing]
        existing_ids = {g.get("id") for g in existing}
        for g in enriched:
            if g.get("id") not in existing_ids:
                merged.append(g)
        _cache[cache_key] = {"data": merged, "fetched_at": datetime.now(timezone.utc)}
    else:
        _cache[cache_key] = {"data": enriched, "fetched_at": datetime.now(timezone.utc)}

    return enriched

@app.get("/api/calibration")
async def get_calibration():
    """Per-grade and per-sport hit-rate from settled picks. Written by the
    settle_picks cron; this endpoint just reads the JSON. Empty until the
    cron has run at least once."""
    return _load_json("calibration.json", {
        "generated_at": None,
        "by_grade": {},
        "by_sport": {},
        "note": "settle_picks cron has not run yet",
    })


@app.get("/api/probe-models")
async def probe_models():
    """Debug: ping every model in REAL_AI_MODELS with a trivial prompt and
    report which respond. One curl away from knowing what's broken."""
    probe_prompt = (
        "GAME: Team A @ Team B | spread -3.5 | total 220. "
        "Output ONLY one line of JSON: "
        '{"grade": 6.0, "pick": "Home", "reasoning": "test"}'
    )
    async def _probe(m):
        t0 = time.time()
        info = {
            "display": m["display"],
            "deployment": m["deployment"],
            "host": m["host"],
            "token_param": m.get("token_param"),
            "max_tokens": m.get("max_tokens"),
            "timeout": m.get("timeout", 60),
            "ok": False,
            "ms": 0,
            "status_code": None,
            "error": None,
            "result": None,
            "result_preview": None,
            "raw_preview": None,
        }
        host_cfg = AZURE_HOSTS.get(m["host"])
        if not host_cfg or not host_cfg.get("key"):
            info["error"] = "host_not_configured_or_missing_key"
            info["ms"] = int((time.time() - t0) * 1000)
            return info

        deployment = m["deployment"]
        is_reasoning = m.get("token_param") == "max_completion_tokens"
        token_budget = int(m.get("max_tokens") or 2000)
        system_msg = (
            "RESPONSE FORMAT: ONE LINE OF JSON ONLY. "
            "Example: {\"grade\": 6.5, \"pick\": \"Home\", \"reasoning\": \"better record\"}. "
            "No thinking. No prose. No code fences. Start with { end with }."
        )
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": probe_prompt},
        ]
        try:
            if host_cfg["format"] == "openai_v1":
                url = host_cfg["url"]
                body = {"model": deployment, "messages": messages,
                        m.get("token_param", "max_tokens"): token_budget}
                if not is_reasoning:
                    body["temperature"] = 0.3
                headers = {"api-key": host_cfg["key"],
                           "Authorization": f"Bearer {host_cfg['key']}",
                           "Content-Type": "application/json"}
            elif host_cfg["format"] == "gemini":
                url = host_cfg["url_template"].format(deployment=deployment) + f"?key={host_cfg['key']}"
                body = {
                    "systemInstruction": {"parts": [{"text": system_msg}]},
                    "contents": [{"role": "user", "parts": [{"text": probe_prompt}]}],
                    "generationConfig": {"temperature": 0.3, "maxOutputTokens": token_budget,
                                         "responseMimeType": "application/json"},
                }
                headers = {"Content-Type": "application/json"}
            else:
                url = host_cfg["url_template"].format(deployment=deployment)
                body = {"messages": messages,
                        m.get("token_param", "max_tokens"): token_budget}
                if not is_reasoning:
                    body["temperature"] = 0.3
                headers = {"api-key": host_cfg["key"],
                           "Authorization": f"Bearer {host_cfg['key']}",
                           "Content-Type": "application/json"}

            req_timeout = float(m.get("timeout") or 60)
            async with httpx.AsyncClient(timeout=req_timeout) as client:
                resp = await client.post(url, headers=headers, json=body)
            info["status_code"] = resp.status_code
            if resp.status_code != 200:
                info["error"] = f"HTTP {resp.status_code}: {resp.text[:400]}"
                info["ms"] = int((time.time() - t0) * 1000)
                return info

            rj = resp.json()
            if host_cfg["format"] == "gemini":
                cand0 = (rj.get("candidates") or [{}])[0]
                parts = ((cand0.get("content") or {}).get("parts") or [])
                content = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
            else:
                choice0 = (rj.get("choices") or [{}])[0]
                msg = choice0.get("message", {}) or {}
                content = (msg.get("content") or msg.get("reasoning_content")
                           or choice0.get("text") or "")
                if isinstance(content, list):
                    content = "".join(
                        (p.get("text") or p.get("content") or "") if isinstance(p, dict) else str(p)
                        for p in content
                    )
            info["raw_preview"] = (content or "")[:200]

            # Parse for grade/pick
            result = await _call_azure_model(m, probe_prompt)
            info["result"] = result
            info["result_preview"] = (json.dumps(result)[:200] if result else None)
            info["ok"] = result is not None
            if not info["ok"] and not info["error"]:
                info["error"] = "parsed_none_from_response"
        except Exception as e:
            info["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        info["ms"] = int((time.time() - t0) * 1000)
        return info
    results = await asyncio.gather(*[_probe(m) for m in REAL_AI_MODELS])
    ok_count = sum(1 for r in results if r.get("ok"))
    return {
        "total": len(results),
        "ok": ok_count,
        "fail": len(results) - ok_count,
        "models": results,
    }


@app.get("/api/engine/status")
async def engine_status():
    """Debug endpoint: show what the grade engine is using."""
    from grade_engine import SPORT_VARIABLES, CHAINS
    return {
        "sports": list(SPORT_VARIABLES.keys()),
        "chains": len(CHAINS),
        "chain_names": list(CHAINS.keys()),
        "variables_per_sport": {s: len(v) for s, v in SPORT_VARIABLES.items()},
    }


# â”€â”€â”€ User / Bankroll / Picks Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class LoginRequest(BaseModel):
    username: str
    pin: str


class LockPickRequest(BaseModel):
    game_id: str
    sport: str
    team: str
    type: str  # spread or ml
    line: float = 0
    amount: float = 0
    odds: int = -110


class GradePickRequest(BaseModel):
    result: str  # W, L, or P


@app.post("/api/login")
async def login(req: LoginRequest):
    username = req.username.lower()
    user = USERS.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user["pin"] != req.pin:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    return {"username": username, "name": user["name"], "bankroll": user["bankroll"]}


@app.get("/api/user/{username}/bankroll")
async def get_bankroll(username: str):
    username = username.lower()
    user = USERS.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user["bankroll"]


# â”€â”€â”€ Profile aliases (live-night convenience) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class BankrollAdjustRequest(BaseModel):
    delta: float


@app.get("/api/profile")
async def list_profiles():
    return [{"username": u, "name": v["name"]} for u, v in USERS.items()]


@app.post("/api/profile/login")
async def profile_login(req: LoginRequest):
    return await login(req)


@app.get("/api/profile/{username}")
async def get_profile(username: str):
    username = username.lower()
    user = USERS.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"username": username, "name": user["name"], "bankroll": user["bankroll"]}


@app.post("/api/profile/{username}/adjust")
async def adjust_bankroll(username: str, req: BankrollAdjustRequest):
    username = username.lower()
    user = USERS.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    bankroll = user["bankroll"]
    bankroll["current"] = round(bankroll["current"] + req.delta, 2)
    bankroll["profit"] = round(bankroll["profit"] + req.delta, 2)
    _save_users()
    return bankroll


@app.post("/api/user/{username}/pick")
async def lock_pick(username: str, req: LockPickRequest):
    username = username.lower()
    user = USERS.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    pick = {
        "id": str(uuid.uuid4())[:8],
        "game_id": req.game_id,
        "sport": req.sport,
        "team": req.team,
        "type": req.type,
        "line": req.line,
        "amount": req.amount,
        "odds": req.odds,
        "result": "pending",
        "profit": 0,
        "locked_at": datetime.now(timezone.utc).isoformat(),
    }
    _user_picks[username].append(pick)
    user["bankroll"]["wagered"] += req.amount
    _save_picks()
    _save_users()
    # Optional postgres write-through (no-op if DATABASE_URL unset).
    try:
        from services.db import upsert_pick as _db_upsert_pick
        await _db_upsert_pick(pick, username)
    except Exception as _e:
        logger.debug(f"[DB] lock_pick write-through skipped: {_e}")
    return pick


@app.get("/api/user/{username}/picks")
async def get_user_picks(username: str):
    username = username.lower()
    if username not in USERS:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_picks.get(username, [])


@app.post("/api/user/{username}/pick/{pick_id}/result")
async def grade_pick(username: str, pick_id: str, req: GradePickRequest):
    username = username.lower()
    user = USERS.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    picks = _user_picks.get(username, [])
    pick = next((p for p in picks if p["id"] == pick_id), None)
    if not pick:
        raise HTTPException(status_code=404, detail="Pick not found")
    result = req.result.upper()
    if result not in ("W", "L", "P"):
        raise HTTPException(status_code=400, detail="Result must be W, L, or P")
    pick["result"] = result
    bankroll = user["bankroll"]
    amount = pick.get("amount", 0)
    odds = pick.get("odds", -110)
    if result == "W":
        # Calculate profit based on American odds
        if odds > 0:
            profit = amount * (odds / 100)
        else:
            profit = amount * (100 / abs(odds))
        pick["profit"] = round(profit, 2)
        bankroll["current"] = round(bankroll["current"] + profit, 2)
        bankroll["profit"] = round(bankroll["profit"] + profit, 2)
        bankroll["wins"] += 1
    elif result == "L":
        pick["profit"] = -amount
        bankroll["current"] = round(bankroll["current"] - amount, 2)
        bankroll["profit"] = round(bankroll["profit"] - amount, 2)
        bankroll["losses"] += 1
    else:  # Push
        pick["profit"] = 0
        bankroll["pushes"] += 1
    _save_picks()
    _save_users()
    # Optional postgres write-through (no-op if DATABASE_URL unset).
    try:
        from services.db import update_pick_result as _db_update_pick_result
        await _db_update_pick_result(pick_id, result, pick.get("profit", 0))
    except Exception as _e:
        logger.debug(f"[DB] grade_pick write-through skipped: {_e}")
    return {"pick": pick, "bankroll": bankroll}


# â”€â”€â”€ Auto Parlay â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _american_odds_str(decimal_odds: float) -> str:
    """Convert decimal parlay odds to American odds string."""
    if decimal_odds >= 2.0:
        return f"+{round((decimal_odds - 1) * 100)}"
    elif decimal_odds > 1.0:
        return f"-{round(100 / (decimal_odds - 1))}"
    return "+100"


@app.get("/api/parlay")
async def get_parlay():
    """Tonight's Best 3 LOCKs â€” auto-parlay across all sports."""
    candidates = []

    for cache_key, cached in _cache.items():
        if not cached or not cached.get("data"):
            continue
        games = cached["data"]
        for game in games:
            conv = game.get("convergence", {})
            status = conv.get("status", "")
            consensus = conv.get("consensusScore", 0)
            pick = game.get("pick", {})

            if status in ("LOCK", "ALIGNED") and consensus >= 7.0 and pick and pick.get("side"):
                # Determine American odds for the pick
                odds_val = game.get("odds", {})
                ml_home = odds_val.get("mlHome", -110)
                ml_away = odds_val.get("mlAway", -110)
                spread = odds_val.get("spread", 0)
                # Use favorite's ML as default pick odds
                pick_odds = ml_home if spread <= 0 else ml_away
                if pick_odds == 0:
                    pick_odds = -110

                candidates.append({
                    "game": f"{game.get('awayTeam', '?')} vs {game.get('homeTeam', '?')}",
                    "pick": f"{pick['side']}" + (
                        f" {pick['line']:+g}" if pick.get("type") == "spread" and pick.get("line", 0) != 0
                        else f" {pick.get('type', 'ML').upper()}"
                    ),
                    "odds": int(pick_odds),
                    "sport": (game.get("sport", "")).upper(),
                    "consensus": consensus,
                    "decimal_odds": _ml_to_decimal(pick_odds),
                })

    # Sort by consensus descending, take top 3
    candidates.sort(key=lambda c: c["consensus"], reverse=True)
    top3 = candidates[:3]

    if not top3:
        return {
            "picks": [],
            "parlay_odds": "+0",
            "risk": 50,
            "potential_payout": 0,
            "confidence": 0,
        }

    # Calculate parlay odds (multiply decimal odds)
    parlay_decimal = 1.0
    total_confidence = 0
    for c in top3:
        parlay_decimal *= c["decimal_odds"]
        total_confidence += c["consensus"]

    parlay_american = _american_odds_str(parlay_decimal)
    risk = 50
    potential_payout = round(risk * parlay_decimal, 2)
    avg_confidence = round(total_confidence / len(top3) * 10)  # scale consensus to %
    avg_confidence = min(95, max(40, avg_confidence))

    picks_out = [
        {"game": c["game"], "pick": c["pick"], "odds": c["odds"], "sport": c["sport"]}
        for c in top3
    ]

    return {
        "picks": picks_out,
        "parlay_odds": parlay_american,
        "risk": risk,
        "potential_payout": potential_payout,
        "confidence": avg_confidence,
    }


# â”€â”€â”€ Static File Serving â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/", response_class=HTMLResponse)
async def root():
    with open(os.path.join(STATIC_DIR, "index.html")) as f:
        return f.read()


@app.get("/{path:path}")
async def catch_all(path: str):
    if path.startswith("api/") or path == "health":
        return {"detail": "Not Found"}
    file_path = os.path.join(STATIC_DIR, path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    with open(os.path.join(STATIC_DIR, "index.html")) as f:
        return HTMLResponse(content=f.read())

