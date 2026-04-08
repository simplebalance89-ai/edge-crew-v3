#!/usr/bin/env python3
"""
EC(8) Slate Pre-Warm Cron
=========================

Patient sequential analyzer that hits the live edge-crew-v3 API to pre-grade
every game on a sport's slate BEFORE the user wakes up. Wakes the LLM fan-out
on each game, lets it finish, moves to the next, no parallel hammering.

Behavior:
  - Reads SPORT env var (mlb / nba / nhl / soccer / nfl)
  - Reads BASE_URL env var (defaults to https://edge-crew-v3.onrender.com)
  - GET /api/games?sport=<sport> to enumerate the slate
  - For each game id, POST /api/analyze with that game_id
  - Sleeps 30 seconds between games to be polite to the single Uvicorn worker
  - Long per-request timeout (8 minutes) so the slowest reasoning model has
    headroom to think
  - Logs hit/miss/error counts to stdout (Render captures logs)

Designed for Render Cron — runs once per scheduled time, exits clean.

Usage (local):
    SPORT=mlb python scripts/prewarm_slate.py

Usage (Render Cron):
    Build:  pip install httpx
    Start:  python scripts/prewarm_slate.py
    Env:    SPORT=mlb
"""
from __future__ import annotations

import os
import sys
import time
import json
from typing import Optional

try:
    import httpx
except ImportError:
    print("[prewarm] httpx not installed; pip install httpx", flush=True)
    sys.exit(1)


BASE_URL = os.environ.get("BASE_URL", "https://edge-crew-v3.onrender.com").rstrip("/")
SPORT = (os.environ.get("SPORT") or "").strip().lower()
GAME_DELAY_SECONDS = int(os.environ.get("GAME_DELAY_SECONDS", "30"))
PER_REQUEST_TIMEOUT = float(os.environ.get("PER_REQUEST_TIMEOUT", "480"))
SLATE_FETCH_TIMEOUT = 60.0


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    print(f"[prewarm {ts}] {msg}", flush=True)


def fetch_slate(sport: str) -> list[dict]:
    url = f"{BASE_URL}/api/games?sport={sport}"
    log(f"GET {url}")
    with httpx.Client(timeout=SLATE_FETCH_TIMEOUT) as client:
        r = client.get(url)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        log(f"WARN: slate endpoint returned non-list: {type(data).__name__}")
        return []
    return data


def analyze_one(sport: str, game_id: str, label: str) -> tuple[bool, Optional[str]]:
    """POST /api/analyze for a single game id. Returns (ok, summary)."""
    url = f"{BASE_URL}/api/analyze"
    body = {"sport": sport, "game_id": game_id}
    try:
        with httpx.Client(timeout=PER_REQUEST_TIMEOUT) as client:
            r = client.post(url, json=body)
    except httpx.TimeoutException:
        return False, "client timeout"
    except Exception as e:
        return False, f"exception: {type(e).__name__}: {e}"

    if r.status_code != 200:
        return False, f"HTTP {r.status_code} body[:200]={r.text[:200]!r}"

    try:
        payload = r.json()
    except Exception as e:
        return False, f"json parse: {e}"

    if not isinstance(payload, list) or not payload:
        return False, f"unexpected payload shape: {type(payload).__name__}"

    game = payload[0]
    ai_models = game.get("aiModels") or []
    real_count = sum(1 for m in ai_models if (m or {}).get("source") == "real")
    fail_count = sum(1 for m in ai_models if (m or {}).get("source") == "fail")
    pick = (game.get("pick") or {}).get("side") or "?"
    sizing = (game.get("pick") or {}).get("sizing") or "?"
    conv = (game.get("convergence") or {}).get("status") or "?"
    return True, f"{label} -> {real_count} live / {fail_count} fail | pick: {pick} ({sizing}) | conv: {conv}"


def main() -> int:
    if not SPORT:
        log("FATAL: SPORT env var not set (expected one of: mlb nba nhl soccer nfl ncaab ncaaf)")
        return 2

    log(f"Pre-warm starting | sport={SPORT} base={BASE_URL}")
    log(f"Per-game delay: {GAME_DELAY_SECONDS}s | per-request timeout: {PER_REQUEST_TIMEOUT}s")

    try:
        games = fetch_slate(SPORT)
    except Exception as e:
        log(f"FATAL: slate fetch failed: {e}")
        return 1

    if not games:
        log(f"No games on {SPORT.upper()} slate today. Exiting clean.")
        return 0

    log(f"Found {len(games)} games on {SPORT.upper()} slate. Pre-warming sequentially.")

    ok_total = 0
    fail_total = 0
    start = time.monotonic()
    for i, g in enumerate(games, start=1):
        gid = g.get("id") or ""
        away = g.get("awayTeam") or "?"
        home = g.get("homeTeam") or "?"
        label = f"[{i}/{len(games)}] {away} @ {home}"
        if not gid:
            log(f"{label} -- missing id, skipping")
            fail_total += 1
            continue

        log(f"{label} firing analyze...")
        t0 = time.monotonic()
        ok, summary = analyze_one(SPORT, gid, label)
        elapsed = time.monotonic() - t0
        if ok:
            ok_total += 1
            log(f"{summary} | took {elapsed:.1f}s")
        else:
            fail_total += 1
            log(f"{label} FAIL after {elapsed:.1f}s -- {summary}")

        if i < len(games):
            log(f"sleeping {GAME_DELAY_SECONDS}s before next game...")
            time.sleep(GAME_DELAY_SECONDS)

    total_elapsed = time.monotonic() - start
    log(f"Pre-warm complete | sport={SPORT} | ok={ok_total} fail={fail_total} | total {total_elapsed:.1f}s ({total_elapsed/60:.1f}m)")
    return 0 if fail_total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
