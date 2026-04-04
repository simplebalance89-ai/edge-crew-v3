"""
Edge Crew v3.0 - Combined API + Frontend (1 Service)
Serves React frontend + API from same Railway service
"""

import json
import os
from datetime import datetime
from typing import Dict

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Edge Crew v3.0", version="3.0.0-combined")

# API Keys
AZURE_KEYS = {
    "sweden": os.environ.get("AZURE_SWEDEN_KEY", ""),
    "nc": os.environ.get("AZURE_NC_KEY", ""),
}

class GradeRequest(BaseModel):
    game_id: str
    sport: str
    home_team: str
    away_team: str
    context: Dict = {}

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "3.0.0-combined"}

@app.get("/api/games")
async def get_games(sport: str = "nba"):
    return [
        {"id": f"{sport}-001", "homeTeam": "Lakers", "awayTeam": "Warriors", "time": "7:30 PM"},
        {"id": f"{sport}-002", "homeTeam": "Celtics", "awayTeam": "Heat", "time": "8:00 PM"},
    ]

@app.post("/api/grade")
async def grade_game(request: GradeRequest):
    return {
        "game_id": request.game_id,
        "our_process": {"grade": "A-", "score": 7.2, "confidence": 82},
        "ai_process": {"grade": "A", "score": 7.8, "confidence": 85, "model": "DeepSeek"},
        "convergence": {
            "status": "ALIGNED",
            "consensus_score": 7.5,
            "consensus_grade": "A-",
            "delta": 0.6
        }
    }

# Serve React frontend
if os.path.exists("web/dist"):
    @app.get("/", response_class=HTMLResponse)
    async def serve_frontend():
        with open("web/dist/index.html") as f:
            return f.read()
    
    @app.get("/{path:path}")
    async def catch_all(path: str):
        file_path = f"web/dist/{path}"
        if os.path.exists(file_path):
            return FileResponse(file_path)
        return FileResponse("web/dist/index.html")
