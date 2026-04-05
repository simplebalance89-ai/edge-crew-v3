"""
Edge Crew v3.0 - Combined API + Frontend
Live odds from The Odds API -> frontend game cards
"""

import logging
import os
from datetime import datetime, timezone
from typing import Dict

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

logger = logging.getLogger("edge-crew-v3")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Edge Crew v3.0", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

ODDS_API_KEY = os.environ.get("ODDS_API_KEY_PAID", "") or os.environ.get("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports"

SPORT_KEYS = {
    "nba": ["basketball_nba"],
    "nhl": ["icehockey_nhl"],
    "mlb": ["baseball_mlb"],
    "nfl": ["americanfootball_nfl"],
    "ncaab": ["basketball_ncaab"],
    "soccer": ["soccer_usa_mls", "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a"],
}

PREFERRED_BOOKS = ["fanduel", "draftkings", "betmgm", "caesars", "bovada"]

_cache: Dict[str, dict] = {}
CACHE_TTL = 300


def _parse_event(event: dict, sport_label: str) -> dict:
    spread = None
    total = None
    ml_home = None
    ml_away = None
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
        bookmaker_used = book_key
        for outcome in markets.get("h2h", []):
            if outcome["name"] == event["home_team"]:
                ml_home = outcome.get("price")
            elif outcome["name"] == event["away_team"]:
                ml_away = outcome.get("price")
        for outcome in markets.get("spreads", []):
            if outcome["name"] == event["home_team"]:
                spread = outcome.get("point")
        for outcome in markets.get("totals", []):
            if outcome["name"] == "Over":
                total = outcome.get("point")
        if ml_home is not None:
            break
    commence = event.get("commence_time", "")
    status = "scheduled"
    if commence:
        try:
            gt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
            if gt <= datetime.now(timezone.utc):
                status = "live"
        except Exception:
            pass
    return {
        "id": event["id"], "sport": sport_label,
        "homeTeam": event["home_team"], "awayTeam": event["away_team"],
        "scheduledAt": commence, "status": status,
        "odds": {"spread": spread or 0, "total": total or 0, "mlHome": ml_home or 0, "mlAway": ml_away or 0},
        "bookmaker": bookmaker_used,
    }


async def _fetch_live_games(sport: str) -> list:
    if not ODDS_API_KEY:
        logger.error("ODDS_API_KEY not configured")
        return []
    keys = SPORT_KEYS.get(sport.lower(), [sport.lower()])
    label = sport.upper()
    all_games = []
    async with httpx.AsyncClient(timeout=15) as client:
        for key in keys:
            try:
                resp = await client.get(f"{ODDS_API_BASE}/{key}/odds/", params={"apiKey": ODDS_API_KEY, "regions": "us,us2", "markets": "h2h,spreads,totals", "oddsFormat": "american"})
                if resp.status_code == 200:
                    events = resp.json()
                    logger.info(f"[ODDS API] {key}: {len(events)} events")
                    for event in events:
                        all_games.append(_parse_event(event, label))
                else:
                    logger.warning(f"[ODDS API] {key}: HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"[ODDS API] {key}: {e}")
    return all_games


class GradeRequest(BaseModel):
    game_id: str
    sport: str
    home_team: str
    away_team: str
    context: Dict = {}


@app.get("/health")
async def health():
    return {"status": "healthy", "time": datetime.now().isoformat(), "odds_api": bool(ODDS_API_KEY)}


@app.get("/api/games")
async def get_games(sport: str = "nba"):
    sport_lower = sport.lower()
    cached = _cache.get(sport_lower)
    if cached:
        age = (datetime.now(timezone.utc) - cached["fetched_at"]).total_seconds()
        if age < CACHE_TTL:
            return cached["data"]
    games = await _fetch_live_games(sport_lower)
    if games:
        _cache[sport_lower] = {"data": games, "fetched_at": datetime.now(timezone.utc)}
    return games


@app.post("/api/grade")
async def grade_game(request: GradeRequest):
    return {
        "game_id": request.game_id,
        "our_process": {"grade": "A-", "score": 7.2, "confidence": 82},
        "ai_process": {"grade": "A", "score": 7.8, "confidence": 85, "model": "DeepSeek"},
        "convergence": {"status": "ALIGNED", "consensus_score": 7.5, "consensus_grade": "A-", "delta": 0.6}
    }


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
        return f.read()
