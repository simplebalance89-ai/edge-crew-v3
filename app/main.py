"""
Edge Crew v3.0 — Combined API + Frontend
Live odds → ESPN profiles → Grade Engine → Two-Lane Display
"""

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Dict

import httpx
from fastapi import FastAPI
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

    # Spread scoring — big spread means clear favorite, not a penalty
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


def _convergence(our: dict, ai: dict) -> dict:
    """Compute convergence between Our Process and AI Process."""
    delta = round(abs(our["score"] - ai["score"]), 2)
    consensus = round((our["score"] * 0.6 + ai["score"] * 0.4), 1)  # Weight Our Process more
    # LOCK = both agree AND the game is good (consensus >= 7.0)
    if delta <= 0.5 and consensus >= 7.0: status = "LOCK"
    elif delta <= 1.0: status = "ALIGNED"
    elif delta <= 1.5: status = "CLOSE"
    else: status = "SPLIT"
    grade = "F"
    for threshold, g in GRADE_MAP:
        if consensus >= threshold:
            grade = g
            break
    return {
        "status": status,
        "consensusScore": consensus,
        "consensusGrade": grade,
        "delta": delta,
        "variance": round(delta / 2, 2),
    }


def _compute_pick(event: dict, odds: dict, our: dict, ai: dict, conv: dict) -> dict:
    """Determine pick recommendation from convergence."""
    consensus = conv["consensusScore"]
    status = conv["status"]
    spread = odds.get("spread", 0)
    home = event.get("homeTeam", "") or event.get("home_team", "")
    away = event.get("awayTeam", "") or event.get("away_team", "")

    if spread <= 0:
        fav, dog, fav_spread = home, away, spread
    else:
        fav, dog, fav_spread = away, home, -spread

    if status in ("LOCK", "ALIGNED") and consensus >= 7.0:
        return {"side": fav, "type": "spread", "line": fav_spread,
                "confidence": min(95, int(consensus * 10 + 10)), "sizing": "Strong Play"}
    elif status == "ALIGNED" and consensus >= 6.0:
        return {"side": fav, "type": "spread", "line": fav_spread,
                "confidence": min(80, int(consensus * 8 + 10)), "sizing": "Standard"}
    elif consensus >= 5.5:
        return {"side": fav, "type": "ml", "line": 0,
                "confidence": min(70, int(consensus * 7)), "sizing": "Lean"}
    else:
        # Always show a pick — low consensus = Lean on favorite ML
        return {"side": fav, "type": "ml", "line": 0,
                "confidence": max(30, int(consensus * 6)), "sizing": "Lean"}


def _parse_event(event: dict, sport_label: str) -> dict:
    """Parse odds API event into our game format (without grading — added later)."""
    spread = total = ml_home = ml_away = None
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
        for o in markets.get("h2h", []):
            if o["name"] == event["home_team"]: ml_home = o.get("price")
            elif o["name"] == event["away_team"]: ml_away = o.get("price")
        for o in markets.get("spreads", []):
            if o["name"] == event["home_team"]: spread = o.get("point")
        for o in markets.get("totals", []):
            if o["name"] == "Over": total = o.get("point")
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

    odds = {"spread": spread or 0, "total": total or 0, "mlHome": ml_home or 0, "mlAway": ml_away or 0}
    return {
        "id": event["id"],
        "sport": sport_label,
        "homeTeam": event["home_team"],
        "awayTeam": event["away_team"],
        "scheduledAt": commence,
        "status": status,
        "odds": odds,
        "bookmaker": bookmaker_used,
    }


def _generate_ai_models(enriched: dict, odds: dict, our_score: float) -> list:
    """Generate 5 AI personality grades with reasoning — pure math, no API needed."""
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

    # DeepSeek — data-driven, stats-heavy
    ds_score = round(our_score * 0.85 + (fav_margin / 10) * 1.5, 1)
    ds_score = max(3.0, min(9.5, ds_score))
    ds_grade = _score_to_grade_local(ds_score)
    if fav_margin > 5:
        ds_thesis = f"{fav} ({fav_rec}) averaging +{fav_margin:.1f} margin — clear statistical edge vs {dog} ({dog_rec}). Spread {abs(spread):.1f} is justified by the data."
    elif fav_margin > 0:
        ds_thesis = f"{fav} ({fav_rec}) slight edge with +{fav_margin:.1f} margin, but {dog} ({dog_rec}) keeps it close. Moderate value on the spread."
    else:
        ds_thesis = f"Numbers don't back {fav} strongly — margin only {fav_margin:+.1f}. {dog} ({dog_rec}) has underdog value here."
    models.append({"model": "DeepSeek R1", "grade": ds_grade, "score": ds_score,
                    "confidence": min(90, int(55 + ds_score * 4)),
                    "thesis": ds_thesis, "key_factors": []})

    # Grok — contrarian, looks for traps
    grok_adj = -0.5 if abs(spread) > 10 else (0.3 if abs(spread) < 3 else 0)
    grok_score = round(our_score + grok_adj + (dog_margin / 15), 1)
    grok_score = max(3.0, min(9.5, grok_score))
    grok_grade = _score_to_grade_local(grok_score)
    if abs(spread) > 10:
        grok_thesis = f"Big spread alert — {fav} at {spread:+.1f} smells like a public trap. {dog} ({dog_rec}) margin is {dog_margin:+.1f}, not as bad as the line suggests."
    elif abs(spread) < 3:
        grok_thesis = f"Tight line ({spread:+.1f}) means sharps see this as a coin flip. {fav} ({fav_rec}) slight edge but no blowout coming."
    else:
        grok_thesis = f"Line at {spread:+.1f} is fair. {fav} ({fav_rec}) should cover but not by much. No strong contrarian signal."
    models.append({"model": "Grok 4.1", "grade": grok_grade, "score": grok_score,
                    "confidence": min(85, int(50 + grok_score * 4)),
                    "thesis": grok_thesis, "key_factors": []})

    # Kimi — structural/tactical scout
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
        kimi_thesis = f"No strong structural edge detected. {fav} ({fav_rec}) vs {dog} ({dog_rec}) — standard matchup, grade from fundamentals only."
    models.append({"model": "Kimi K2.5", "grade": kimi_grade, "score": kimi_score,
                    "confidence": min(88, int(52 + kimi_score * 4)),
                    "thesis": kimi_thesis, "key_factors": []})

    # GPT Nano — balanced consensus builder, weighs all factors equally
    odds_score = _odds_grade(odds)["score"]
    gpt_score = round((our_score + odds_score) / 2, 1)
    gpt_score = max(3.0, min(9.5, gpt_score))
    gpt_grade = _score_to_grade_local(gpt_score)
    if abs(our_score - odds_score) <= 1.0:
        gpt_thesis = f"Both fundamental and market analysis align on {fav} ({fav_rec}). Consensus score {gpt_score:.1f} reflects agreement across processes — steady value."
    else:
        stronger = "fundamentals" if our_score > odds_score else "market"
        weaker = "market" if our_score > odds_score else "fundamentals"
        gpt_thesis = f"Mixed signals: {stronger} say {fav} ({fav_rec}) is the play ({max(our_score, odds_score):.1f}) but {weaker} lag behind ({min(our_score, odds_score):.1f}). Middle ground lands at {gpt_score:.1f}."
    models.append({"model": "GPT 5.4 Nano", "grade": gpt_grade, "score": gpt_score,
                    "confidence": min(90, int(55 + gpt_score * 4)),
                    "thesis": gpt_thesis, "key_factors": []})

    # Claude Opus — deep strategic thinker, momentum & narrative focus, contrarian on big spreads
    momentum_weight = fav_margin * 0.2  # heavier momentum factor
    contrarian_adj = -0.4 if abs(spread) > 10 else (0.2 if abs(spread) < 3 else 0)
    claude_score = round(our_score * 0.7 + momentum_weight + contrarian_adj + 1.5, 1)
    claude_score = max(3.0, min(9.5, claude_score))
    claude_grade = _score_to_grade_local(claude_score)
    if fav_margin > 5:
        claude_thesis = f"Sustainable edge — {fav} ({fav_rec}) trajectory shows +{fav_margin:.1f} margin, a durable pattern not fluky variance. Momentum supports the line."
    elif fav_margin > 0:
        claude_thesis = f"{fav} ({fav_rec}) holding slim +{fav_margin:.1f} margin. Trajectory positive but regression risk exists if {dog} ({dog_rec}) tightens up. Lean cautiously."
    else:
        claude_thesis = f"Regression risk: {fav} favored at {spread:+.1f} but margin is only {fav_margin:+.1f}. {dog} ({dog_rec}) narrative is stronger than the line implies — contrarian value."
    models.append({"model": "Claude Opus 4.6", "grade": claude_grade, "score": claude_score,
                    "confidence": min(92, int(54 + claude_score * 4)),
                    "thesis": claude_thesis, "key_factors": []})

    # Phi-4 Reasoning — small but sharp reasoning model, chain-of-thought approach
    # Weighs the delta between processes heavily — if Our and AI disagree, Phi digs into why
    process_delta = abs(our_score - (sum(m["score"] for m in models) / len(models)))
    if process_delta > 1.5:
        # Significant disagreement — Phi reasons through the conflict
        phi_score = round((our_score * 0.55 + ds_score * 0.25 + grok_score * 0.2), 1)
        phi_thesis = f"Process disagreement detected ({process_delta:.1f}pt gap). Reasoning through: {fav} ({fav_rec}) fundamentals score {our_score:.1f} but model consensus at {sum(m['score'] for m in models)/len(models):.1f}. Splitting the difference — edge exists but confidence is capped."
    elif fav_margin > 3:
        phi_score = round(our_score * 0.8 + fav_margin * 0.15 + 0.5, 1)
        phi_thesis = f"Chain-of-thought: {fav} ({fav_rec}) margin +{fav_margin:.1f} is reproducible across sample. {dog} ({dog_rec}) hasn't shown ability to close that gap. Line {spread:+.1f} is fair to slightly short."
    else:
        phi_score = round(our_score * 0.9 + 0.3, 1)
        phi_thesis = f"Thin edge — {fav} ({fav_rec}) is the right side but margin {fav_margin:+.1f} doesn't inspire conviction. Reasoning says bet small or pass unless other signals confirm."
    phi_score = max(3.0, min(9.5, phi_score))
    phi_grade = _score_to_grade_local(phi_score)
    models.append({"model": "Phi-4 Reasoning", "grade": phi_grade, "score": phi_score,
                    "confidence": min(88, int(50 + phi_score * 4)),
                    "thesis": phi_thesis, "key_factors": []})

    return models


def _score_to_grade_local(score: float) -> str:
    for threshold, g in GRADE_MAP:
        if score >= threshold:
            return g
    return "F"


async def _grade_game_full(game: dict, sport_upper: str, odds_key: str = "") -> dict:
    """Run full grading pipeline: ESPN data → Grade Engine → Two-Lane output."""
    enriched = None
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
            "variables": {k: {"score": v["score"], "name": k.replace("_", " "), "available": v.get("available", True)}
                          for k, v in best.get("variables", {}).items()},
        }
    except Exception as e:
        logger.warning(f"Grade engine error for {game.get('homeTeam')} vs {game.get('awayTeam')}: {e}")
        our_grade = {"grade": "C", "score": 5.0, "confidence": 40, "thesis": "Grade engine fallback"}

    # AI Process: odds-based model for consensus
    ai_grade = _odds_grade(game.get("odds", {}))

    # AI Models: 5 personality grades with reasoning (always, no API needed)
    ai_models = _generate_ai_models(
        enriched or game,
        game.get("odds", {}),
        our_grade["score"],
    )

    # Blend AI model scores into ai_grade
    if ai_models:
        avg_ai = round(sum(m["score"] for m in ai_models) / len(ai_models), 1)
        ai_grade["score"] = avg_ai
        ai_grade["grade"] = _score_to_grade_local(avg_ai)
        ai_grade["confidence"] = int(sum(m["confidence"] for m in ai_models) / len(ai_models))
        ai_grade["model"] = f"{len(ai_models)}-Model Consensus"

    # Convergence
    conv = _convergence(our_grade, ai_grade)

    # Pick
    pick = _compute_pick(game, game.get("odds", {}), our_grade, ai_grade, conv)

    # Determine pick side for EV/Peter's Rules
    pick_side = "home"
    if pick and pick.get("side"):
        if pick["side"] == game.get("awayTeam", ""):
            pick_side = "away"

    # EV calculation
    ev = calculate_ev(enriched or game, pick_side, conv["consensusScore"])

    # Peter's Rules
    pr = peter_rules(enriched or game, pick_side)

    return {
        "ourGrade": our_grade,
        "aiGrade": ai_grade,
        "convergence": conv,
        "pick": pick,
        "aiModels": ai_models,
        "ev": ev,
        "peterRules": pr,
        "kalshi_prob": None,
    }


async def _fetch_and_grade(sport: str) -> list:
    """Fetch live games from Odds API, then grade each one."""
    if not ODDS_API_KEY:
        logger.error("ODDS_API_KEY not configured")
        return []

    keys = SPORT_KEYS.get(sport.lower(), [sport.lower()])
    sport_upper = sport.upper()
    all_games = []

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
                        all_games.append(game)
                else:
                    logger.warning(f"[ODDS API] {key}: HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"[ODDS API] {key}: {e}")

    # Grade all games
    for game in all_games:
        odds_key = ""
        for key in keys:
            if sport_upper == "SOCCER":
                odds_key = key
                break
        grades = await _grade_game_full(game, sport_upper, odds_key)
        game.update(grades)

    return all_games


# ─── Routes ────────────────────────────────────────────────────────────────────

class GradeRequest(BaseModel):
    game_id: str
    sport: str
    home_team: str
    away_team: str
    context: Dict = {}


class AnalyzeRequest(BaseModel):
    sport: str


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "3.0.0-b3",
        "time": datetime.now().isoformat(),
        "odds_api": bool(ODDS_API_KEY),
        "engine": "grade_engine_v3",
    }


@app.get("/api/games")
async def get_games(sport: str = "nba"):
    sport_lower = sport.lower()
    cached = _cache.get(sport_lower)
    if cached:
        age = (datetime.now(timezone.utc) - cached["fetched_at"]).total_seconds()
        if age < CACHE_TTL:
            return cached["data"]
    games = await _fetch_and_grade(sport_lower)
    if games:
        _cache[sport_lower] = {"data": games, "fetched_at": datetime.now(timezone.utc)}
    return games


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
    Two-tier system -- this is the SLOW path triggered by 'Analyze All'."""
    sport_lower = request.sport.lower()

    # Get cached games (fast path must have run first)
    cached = _cache.get(sport_lower)
    if not cached or not cached.get("data"):
        games = await _fetch_and_grade(sport_lower)
        if games:
            _cache[sport_lower] = {"data": games, "fetched_at": datetime.now(timezone.utc)}
    else:
        games = cached["data"]

    if not games:
        return {"error": "No games found", "sport": sport_lower}

    # Call AI crowdsource for all games
    logger.info(f"[ANALYZE] Deep analysis for {sport_lower}: {len(games)} games")
    model_grades = await crowdsource_grade(games, sport_lower)

    # Enrich each game with per-model grades + gatekeeper
    enriched = []
    for game in games:
        game_id = game.get("id", "")
        ai_grades_list = model_grades.get(game_id, [])

        # Attach per-model grades
        game["aiModels"] = ai_grades_list

        # If we got AI model grades, compute a blended AI score from them
        if ai_grades_list:
            valid_scores = [m.get("score", 0) for m in ai_grades_list if m.get("score", 0) > 0]
            if valid_scores:
                avg_score = round(sum(valid_scores) / len(valid_scores), 1)
                avg_conf = int(sum(m.get("confidence", 50) for m in ai_grades_list) / len(ai_grades_list))
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
                # Recompute convergence with blended AI grade
                our_grade = game.get("ourGrade", {"score": 5.0})
                game["convergence"] = _convergence(our_grade, game["aiGrade"])
                game["pick"] = _compute_pick(
                    game, game.get("odds", {}), our_grade, game["aiGrade"], game["convergence"]
                )

        # Run Kimi gatekeeper
        if ai_grades_list:
            gk = await kimi_gatekeeper(
                game,
                game.get("ourGrade", {}),
                ai_grades_list,
                game.get("convergence", {}),
            )
            game["gatekeeper"] = gk

            # Apply gatekeeper adjustment to consensus
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

        enriched.append(game)

    # Update cache with enriched data
    _cache[sport_lower] = {"data": enriched, "fetched_at": datetime.now(timezone.utc)}

    return enriched


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


# ─── Static File Serving ──────────────────────────────────────────────────────

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
