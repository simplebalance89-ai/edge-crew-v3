#!/usr/bin/env python3
"""
EC(8) Pick Settlement Cron
==========================

Reads picks.json from PERSIST_DIR, fetches recently completed game scores
from the Odds API, matches pending picks against final scores, and writes
W/L/P results back into picks.json. Also computes a per-grade and per-sport
hit-rate calibration table and writes it to calibration.json so the
inflated-grade calibration work has real outcome data to chew on.

Designed for Render Cron — runs once per scheduled time, exits clean.

Match strategy: stable game id derived as md5(home|away|commence_time)[:16],
the same hash _parse_event uses in app/main.py. Picks store this stable id,
the scores endpoint returns the underlying Odds API event so we re-derive.

Usage (local):
    ODDS_API_KEY_PAID=... python scripts/settle_picks.py

Usage (Render Cron):
    Build:  pip install httpx
    Start:  python scripts/settle_picks.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from typing import Any, Optional

try:
    import httpx
except ImportError:
    print("[settle] httpx not installed; pip install httpx", flush=True)
    sys.exit(1)


PERSIST_DIR = "/data" if os.path.exists("/data") else "/tmp/ec8"
ODDS_API_KEY = os.environ.get("ODDS_API_KEY_PAID") or os.environ.get("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports"
DAYS_FROM = int(os.environ.get("SETTLE_DAYS_FROM", "2"))

# Mirror of app/main.py SPORT_KEYS — keep in sync.
SPORT_KEYS = {
    "nba": ["basketball_nba"],
    "nhl": ["icehockey_nhl"],
    "mlb": ["baseball_mlb"],
    "nfl": ["americanfootball_nfl"],
    "ncaab": ["basketball_ncaab"],
    "ncaaf": ["americanfootball_ncaaf"],
    "soccer": [
        "soccer_usa_mls", "soccer_epl", "soccer_spain_la_liga",
        "soccer_italy_serie_a", "soccer_germany_bundesliga",
        "soccer_france_ligue_one", "soccer_uefa_champs_league",
        "soccer_uefa_europa_league", "soccer_brazil_campeonato",
        "soccer_mexico_ligamx",
    ],
    "mma": ["mma_mixed_martial_arts"],
    "boxing": ["boxing_boxing"],
}


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    print(f"[settle {ts}] {msg}", flush=True)


def stable_id(home: str, away: str, commence: str) -> str:
    return hashlib.md5(f"{home}|{away}|{commence}".encode("utf-8")).hexdigest()[:16]


def load_json(name: str, default: Any) -> Any:
    path = os.path.join(PERSIST_DIR, name)
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as e:
        log(f"WARN: failed to load {name}: {e}")
        return default


def save_json(name: str, data: Any) -> None:
    os.makedirs(PERSIST_DIR, exist_ok=True)
    path = os.path.join(PERSIST_DIR, name)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def fetch_completed_scores(sport_key: str) -> list[dict]:
    """Hit the Odds API scores endpoint for one sport key."""
    url = f"{ODDS_API_BASE}/{sport_key}/scores/"
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(url, params={"apiKey": ODDS_API_KEY, "daysFrom": DAYS_FROM})
        if r.status_code != 200:
            log(f"WARN: {sport_key} scores HTTP {r.status_code}: {r.text[:200]}")
            return []
        return r.json() or []
    except Exception as e:
        log(f"WARN: {sport_key} scores fetch failed: {e}")
        return []


def build_score_index(sport: str) -> dict[str, dict]:
    """Return {stable_id: {home_score, away_score, completed, home, away}}."""
    index: dict[str, dict] = {}
    for key in SPORT_KEYS.get(sport, []):
        events = fetch_completed_scores(key)
        for ev in events:
            if not ev.get("completed"):
                continue
            home = ev.get("home_team") or ""
            away = ev.get("away_team") or ""
            commence = ev.get("commence_time") or ""
            scores = ev.get("scores") or []
            score_map = {s.get("name"): s.get("score") for s in scores if s}
            try:
                hs = int(score_map.get(home))
                as_ = int(score_map.get(away))
            except (TypeError, ValueError):
                continue
            sid = stable_id(home, away, commence)
            index[sid] = {
                "home": home, "away": away,
                "home_score": hs, "away_score": as_,
                "commence": commence,
            }
    return index


def settle_pick(pick: dict, score: dict) -> Optional[str]:
    """Return 'W' / 'L' / 'P' based on pick type, line, and final score.
    Supports moneyline, spread, totals. Returns None if pick type unsupported."""
    ptype = (pick.get("type") or "").lower()
    team = pick.get("team") or ""
    line = float(pick.get("line") or 0)
    hs = score["home_score"]
    as_ = score["away_score"]
    home = score["home"]
    away = score["away"]

    if ptype in ("ml", "moneyline", "h2h"):
        if hs == as_:
            return "P"
        winner = home if hs > as_ else away
        return "W" if team == winner else "L"

    if ptype in ("spread", "ats"):
        # team's margin including the spread
        if team == home:
            margin = (hs + line) - as_
        elif team == away:
            margin = (as_ + line) - hs
        else:
            return None
        if abs(margin) < 1e-9:
            return "P"
        return "W" if margin > 0 else "L"

    if ptype in ("total", "totals", "ou", "over", "under"):
        total_pts = hs + as_
        side = team.lower()  # picks store "OVER" / "UNDER" in team for totals
        if abs(total_pts - line) < 1e-9:
            return "P"
        if "over" in side:
            return "W" if total_pts > line else "L"
        if "under" in side:
            return "W" if total_pts < line else "L"
        return None

    return None


def apply_result(user: dict, pick: dict, result: str) -> None:
    """Update bankroll exactly the way /api/user/.../pick/.../result does."""
    pick["result"] = result
    bankroll = user.get("bankroll") or {}
    amount = pick.get("amount", 0) or 0
    odds = pick.get("odds", -110) or -110
    if result == "W":
        if odds > 0:
            profit = amount * (odds / 100)
        else:
            profit = amount * (100 / abs(odds))
        pick["profit"] = round(profit, 2)
        bankroll["current"] = round(bankroll.get("current", 0) + profit, 2)
        bankroll["profit"] = round(bankroll.get("profit", 0) + profit, 2)
        bankroll["wins"] = bankroll.get("wins", 0) + 1
    elif result == "L":
        pick["profit"] = -amount
        bankroll["current"] = round(bankroll.get("current", 0) - amount, 2)
        bankroll["profit"] = round(bankroll.get("profit", 0) - amount, 2)
        bankroll["losses"] = bankroll.get("losses", 0) + 1
    else:  # P (push)
        pick["profit"] = 0
        bankroll["pushes"] = bankroll.get("pushes", 0) + 1
    user["bankroll"] = bankroll


def compute_calibration(picks_by_user: dict) -> dict:
    """Per-grade and per-sport hit rate across all settled picks."""
    by_grade: dict[str, dict] = {}
    by_sport: dict[str, dict] = {}
    for username, picks in picks_by_user.items():
        for p in picks:
            result = (p.get("result") or "").upper()
            if result not in ("W", "L", "P"):
                continue
            grade = p.get("grade") or "?"
            sport = (p.get("sport") or "?").lower()
            for bucket, key in ((by_grade, grade), (by_sport, sport)):
                b = bucket.setdefault(key, {"w": 0, "l": 0, "p": 0})
                if result == "W":
                    b["w"] += 1
                elif result == "L":
                    b["l"] += 1
                else:
                    b["p"] += 1

    def with_rate(bucket: dict) -> dict:
        out = {}
        for k, v in bucket.items():
            decided = v["w"] + v["l"]
            v["hit_rate"] = round(v["w"] / decided, 4) if decided else None
            v["sample"] = decided
            out[k] = v
        return out

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "by_grade": with_rate(by_grade),
        "by_sport": with_rate(by_sport),
    }


def main() -> int:
    if not ODDS_API_KEY:
        log("FATAL: ODDS_API_KEY not set")
        return 2

    log(f"Settlement starting | persist_dir={PERSIST_DIR} days_from={DAYS_FROM}")
    users = load_json("users.json", {})
    picks_by_user = load_json("picks.json", {})
    if not picks_by_user:
        log("No picks file found — nothing to settle")
        save_json("calibration.json", compute_calibration({}))
        return 0

    pending_by_sport: dict[str, list] = {}
    for username, picks in picks_by_user.items():
        for p in picks:
            if (p.get("result") or "pending").lower() != "pending":
                continue
            sport = (p.get("sport") or "").lower()
            if not sport:
                continue
            pending_by_sport.setdefault(sport, []).append((username, p))

    if not pending_by_sport:
        log("No pending picks to settle")
        save_json("calibration.json", compute_calibration(picks_by_user))
        return 0

    settled = 0
    unmatched = 0
    for sport, pairs in pending_by_sport.items():
        log(f"Fetching scores for {sport} ({len(pairs)} pending picks)...")
        index = build_score_index(sport)
        log(f"  {sport}: {len(index)} completed games found")
        for username, pick in pairs:
            sid = pick.get("game_id")
            score = index.get(sid)
            if not score:
                unmatched += 1
                continue
            result = settle_pick(pick, score)
            if result is None:
                log(f"  unsupported pick type for {pick.get('id')}: {pick.get('type')}")
                continue
            user = users.get(username) or {"bankroll": {}}
            apply_result(user, pick, result)
            users[username] = user
            settled += 1
            log(f"  settled pick {pick.get('id')} ({username}) -> {result}")

    save_json("picks.json", picks_by_user)
    save_json("users.json", users)
    save_json("calibration.json", compute_calibration(picks_by_user))
    log(f"Done | settled={settled} still_unmatched={unmatched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
