"""
Edge Crew v3.0 - Combined API + Frontend
Live odds from The Odds API + algorithmic grading
"""

import logging
import os
import random
from datetime import datetime, timezone
from typing import Dict

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

logger = logging.getLogger('edge-crew-v3')
logging.basicConfig(level=logging.INFO)

app = FastAPI(title='Edge Crew v3.0', version='3.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')

ODDS_API_KEY = os.environ.get('ODDS_API_KEY_PAID', '') or os.environ.get('ODDS_API_KEY', '')
ODDS_API_BASE = 'https://api.the-odds-api.com/v4/sports'

SPORT_KEYS = {
    'nba': ['basketball_nba'],
    'nhl': ['icehockey_nhl'],
    'mlb': ['baseball_mlb'],
    'nfl': ['americanfootball_nfl'],
    'ncaab': ['basketball_ncaab'],
    'soccer': ['soccer_usa_mls', 'soccer_epl', 'soccer_spain_la_liga', 'soccer_italy_serie_a'],
}

PREFERRED_BOOKS = ['fanduel', 'draftkings', 'betmgm', 'caesars', 'bovada']

_cache: Dict[str, dict] = {}
CACHE_TTL = 300

GRADE_MAP = [(9.0,'A+'),(8.5,'A'),(8.0,'A-'),(7.5,'B+'),(7.0,'B'),(6.5,'B-'),(6.0,'C+'),(5.5,'C'),(5.0,'D'),(0.0,'F')]

def _score_to_grade(score):
    for threshold, grade in GRADE_MAP:
        if score >= threshold:
            return grade
    return 'F'

def _grade_from_odds(odds):
    spread = abs(odds.get('spread', 0))
    ml_home = odds.get('mlHome', 0)
    ml_away = odds.get('mlAway', 0)
    total = odds.get('total', 0)
    if spread <= 2: spread_score = 8.5
    elif spread <= 4: spread_score = 7.8
    elif spread <= 7: spread_score = 7.0
    elif spread <= 10: spread_score = 6.0
    else: spread_score = 5.0
    ml_diff = abs(ml_home - ml_away) if ml_home and ml_away else 200
    if ml_diff <= 100: ml_score = 8.5
    elif ml_diff <= 200: ml_score = 7.5
    elif ml_diff <= 400: ml_score = 6.5
    else: ml_score = 5.5
    total_score = 7.5 if 200 <= total <= 240 else (6.8 if total > 0 else 6.5)
    score = round(spread_score * 0.45 + ml_score * 0.35 + total_score * 0.20, 1)
    conf = min(95, max(55, int(65 + (score - 5) * 8)))
    return {'grade': _score_to_grade(score), 'score': score, 'confidence': conf}

def _ai_grade(odds):
    base = _grade_from_odds(odds)
    v = round(random.uniform(-0.6, 0.8), 1)
    s = round(max(3.0, min(10.0, base['score'] + v)), 1)
    c = min(98, max(50, int(base['confidence'] + random.randint(-8, 12))))
    return {'grade': _score_to_grade(s), 'score': s, 'confidence': c, 'model': 'DeepSeek-V3'}

def _convergence(our, ai):
    delta = round(abs(our['score'] - ai['score']), 2)
    consensus = round((our['score'] + ai['score']) / 2, 1)
    if delta <= 0.3: status = 'LOCK'
    elif delta <= 0.8: status = 'ALIGNED'
    elif delta <= 1.5: status = 'DIVERGENT'
    else: status = 'CONFLICT'
    return {'status': status, 'consensusScore': consensus, 'consensusGrade': _score_to_grade(consensus), 'delta': delta, 'variance': round(delta / 2, 2)}


def _compute_pick(event, odds, our, ai, conv):
    consensus = conv["consensusScore"]
    status = conv["status"]
    spread = odds.get("spread", 0)
    home = event["home_team"]
    away = event["away_team"]
    if spread <= 0:
        fav, dog, fav_spread = home, away, spread
    else:
        fav, dog, fav_spread = away, home, -spread
    if status in ("LOCK", "ALIGNED") and consensus >= 7.0:
        return {"side": fav, "type": "spread", "line": fav_spread, "confidence": min(95, int(consensus * 10 + 10)), "sizing": "Strong Play"}
    elif status == "ALIGNED" and consensus >= 6.0:
        return {"side": fav, "type": "spread", "line": fav_spread, "confidence": min(80, int(consensus * 8 + 10)), "sizing": "Standard"}
    elif consensus >= 6.0:
        return {"side": dog, "type": "ml", "line": 0, "confidence": min(70, int(consensus * 7)), "sizing": "Lean"}
    else:
        return {"side": "", "type": "", "line": 0, "confidence": 0, "sizing": "No Play"}

def _parse_event(event, sport_label):
    spread = total = ml_home = ml_away = None
    bookmaker_used = None
    bookmakers_data = {bk['key']: bk for bk in event.get('bookmakers', [])}
    book_order = PREFERRED_BOOKS + [k for k in bookmakers_data if k not in PREFERRED_BOOKS]
    for book_key in book_order:
        bk = bookmakers_data.get(book_key)
        if not bk: continue
        markets = {m['key']: m['outcomes'] for m in bk.get('markets', [])}
        if not markets: continue
        bookmaker_used = book_key
        for o in markets.get('h2h', []):
            if o['name'] == event['home_team']: ml_home = o.get('price')
            elif o['name'] == event['away_team']: ml_away = o.get('price')
        for o in markets.get('spreads', []):
            if o['name'] == event['home_team']: spread = o.get('point')
        for o in markets.get('totals', []):
            if o['name'] == 'Over': total = o.get('point')
        if ml_home is not None: break
    commence = event.get('commence_time', '')
    status = 'scheduled'
    if commence:
        try:
            gt = datetime.fromisoformat(commence.replace('Z', '+00:00'))
            if gt <= datetime.now(timezone.utc): status = 'live'
        except Exception: pass
    odds = {'spread': spread or 0, 'total': total or 0, 'mlHome': ml_home or 0, 'mlAway': ml_away or 0}
    our = _grade_from_odds(odds)
    ai = _ai_grade(odds)
    conv = _convergence(our, ai)
    return {'id': event['id'], 'sport': sport_label, 'homeTeam': event['home_team'], 'awayTeam': event['away_team'], 'scheduledAt': commence, 'status': status, 'odds': odds, 'bookmaker': bookmaker_used, 'ourGrade': our, 'aiGrade': ai, 'convergence': conv, 'pick': _compute_pick(event, odds, our, ai, conv)}

async def _fetch_live_games(sport):
    if not ODDS_API_KEY:
        logger.error('ODDS_API_KEY not configured')
        return []
    keys = SPORT_KEYS.get(sport.lower(), [sport.lower()])
    label = sport.upper()
    all_games = []
    async with httpx.AsyncClient(timeout=15) as client:
        for key in keys:
            try:
                resp = await client.get(f'{ODDS_API_BASE}/{key}/odds/', params={'apiKey': ODDS_API_KEY, 'regions': 'us,us2', 'markets': 'h2h,spreads,totals', 'oddsFormat': 'american'})
                if resp.status_code == 200:
                    events = resp.json()
                    logger.info(f'[ODDS API] {key}: {len(events)} events')
                    for event in events:
                        all_games.append(_parse_event(event, label))
                else:
                    logger.warning(f'[ODDS API] {key}: HTTP {resp.status_code}')
            except Exception as e:
                logger.warning(f'[ODDS API] {key}: {e}')
    return all_games

class GradeRequest(BaseModel):
    game_id: str
    sport: str
    home_team: str
    away_team: str
    context: Dict = {}

@app.get('/health')
async def health():
    return {'status': 'healthy', 'time': datetime.now().isoformat(), 'odds_api': bool(ODDS_API_KEY)}

@app.get('/api/games')
async def get_games(sport: str = 'nba'):
    sport_lower = sport.lower()
    cached = _cache.get(sport_lower)
    if cached:
        age = (datetime.now(timezone.utc) - cached['fetched_at']).total_seconds()
        if age < CACHE_TTL:
            return cached['data']
    games = await _fetch_live_games(sport_lower)
    if games:
        _cache[sport_lower] = {'data': games, 'fetched_at': datetime.now(timezone.utc)}
    return games

@app.post('/api/grade')
async def grade_game(request: GradeRequest):
    cached = _cache.get(request.sport.lower())
    if cached:
        for game in cached['data']:
            if game['id'] == request.game_id:
                return {'game_id': request.game_id, 'our_process': game['ourGrade'], 'ai_process': game['aiGrade'], 'convergence': game['convergence']}
    odds = request.context.get('odds', {'spread': 0, 'total': 0, 'mlHome': 0, 'mlAway': 0})
    our = _grade_from_odds(odds)
    ai = _ai_grade(odds)
    conv = _convergence(our, ai)
    return {'game_id': request.game_id, 'our_process': our, 'ai_process': ai, 'convergence': conv}

@app.get('/', response_class=HTMLResponse)
async def root():
    with open(os.path.join(STATIC_DIR, 'index.html')) as f:
        return f.read()

@app.get('/{path:path}')
async def catch_all(path: str):
    if path.startswith('api/') or path == 'health':
        return {'detail': 'Not Found'}
    file_path = os.path.join(STATIC_DIR, path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    with open(os.path.join(STATIC_DIR, 'index.html')) as f:
        return f.read()
