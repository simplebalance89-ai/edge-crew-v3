"""
Edge Crew v3.0 - Combined API + Frontend (Single Service)
"""

import json
import os
from datetime import datetime
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Edge Crew v3.0", version="3.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend files
if os.path.exists("web/dist"):
    @app.get("/", response_class=HTMLResponse)
    async def root():
        with open("web/dist/index.html") as f:
            return f.read()
    
    @app.get("/{path:path}")
    async def catch_all(path: str):
        file_path = f"web/dist/{path}"
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        with open("web/dist/index.html") as f:
            return f.read()

class GradeRequest(BaseModel):
    game_id: str
    sport: str
    home_team: str
    away_team: str
    context: Dict = {}

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
