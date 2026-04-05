"""
Edge Crew v3.0 - Combined API + Frontend
"""

import os
from datetime import datetime
from typing import Dict

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Edge Crew v3.0", version="3.0.0")

# Get static files directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

class GradeRequest(BaseModel):
    game_id: str
    sport: str
    home_team: str
    away_team: str
    context: Dict = {}

# API Routes FIRST
@app.get("/health")
async def health():
    return {"status": "healthy", "time": datetime.now().isoformat()}

@app.get("/api/games")
async def get_games(sport: str = "nba"):
    return [
        {"id": f"{sport}-001", "home_team": "Lakers", "away_team": "Warriors", "time": "19:30", "our_grade": "A", "ai_grade": "A-", "status": "ALIGNED"},
        {"id": f"{sport}-002", "home_team": "Celtics", "away_team": "Heat", "time": "20:00", "our_grade": "B+", "ai_grade": "B", "status": "ALIGNED"},
    ]

@app.post("/api/grade")
async def grade_game(request: GradeRequest):
    return {
        "game_id": request.game_id,
        "our_process": {"grade": "A-", "score": 7.2, "confidence": 82},
        "ai_process": {"grade": "A", "score": 7.8, "confidence": 85, "model": "DeepSeek"},
        "convergence": {"status": "ALIGNED", "consensus_score": 7.5, "consensus_grade": "A-", "delta": 0.6}
    }

# Frontend Routes LAST
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve index.html"""
    with open(os.path.join(STATIC_DIR, "index.html")) as f:
        return f.read()

@app.get("/{path:path}")
async def catch_all(path: str):
    """Serve static files or fallback to index.html"""
    # Don't catch API routes
    if path.startswith("api/") or path == "health":
        return {"detail": "Not Found"}
    file_path = os.path.join(STATIC_DIR, path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    # Fallback to index.html for SPA routes
    with open(os.path.join(STATIC_DIR, "index.html")) as f:
        return f.read()
