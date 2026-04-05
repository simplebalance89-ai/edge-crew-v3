"""
Edge Crew v3.0 - 20260404140021 - Railway Deploy (Single Service)
Simplified version for Railway deployment
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict

print("🚀 Starting Edge Crew v3.0 - 20260404140021...", flush=True)

try:
    import httpx
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    print("✅ Imports successful", flush=True)
except Exception as e:
    print(f"❌ Import error: {e}", flush=True)
    sys.exit(1)

app = FastAPI(title="Edge Crew v3.0 - 20260404140021", version="3.0.0-railway")

# CORS - Allow Vercel frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
print("✅ FastAPI app created", flush=True)

# API Keys from environment
AZURE_KEYS = {
    "sweden": os.environ.get("KIMI_SCOUT_KEY", ""),
    "nc": os.environ.get("AZURE_OPENAI_KEY", ""),
    "gce": os.environ.get("AZURE_OPENAI_KEY", ""),
}

class GradeRequest(BaseModel):
    game_id: str
    sport: str
    home_team: str
    away_team: str
    context: Dict = {}

@app.get("/")
async def root():
    return {
        "name": "Edge Crew v3.0 - 20260404140021",
        "version": "3.0.0-railway",
        "status": "online",
        "endpoints": ["/health", "/api/grade"]
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "time": datetime.now().isoformat(),
        "version": "3.0.0-railway"
    }

async def call_ai(prompt: str) -> Dict:
    """Call AI with fallback."""
    # Try Azure endpoints
    endpoints = [
        ("https://peter-mna31gr3-swedencentral.services.ai.azure.com/openai/v1", AZURE_KEYS["sweden"]),
        ("https://peter-mnji0acb-northcentralus.services.ai.azure.com/openai/v1", AZURE_KEYS["nc"]),
    ]
    
    for endpoint, key in endpoints:
        if not key:
            continue
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{endpoint}/chat/completions",
                    headers={"api-key": key},
                    json={
                        "model": "DeepSeek-V3-0324",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 500
                    }
                )
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                
                # Try to parse JSON
                try:
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    result = json.loads(content.strip())
                except:
                    result = {"grade": "B", "score": 6.0, "thesis": content[:100]}
                
                return {
                    "grade": result.get("grade", "B"),
                    "score": result.get("score", 6.0),
                    "thesis": result.get("thesis", "AI analysis"),
                    "model": "DeepSeek-V3-0324"
                }
        except Exception as e:
            print(f"Endpoint failed: {e}")
            continue
    
    # Fallback
    return {"grade": "C", "score": 5.0, "thesis": "AI temporarily unavailable", "model": "fallback"}

def grade_deterministic(sport: str, context: Dict) -> Dict:
    """Deterministic grading."""
    score = 5.0
    
    if context.get("home_rest_advantage"):
        score += 1.5
    if context.get("key_injuries"):
        score -= context["key_injuries"] * 0.5
    
    score = max(0, min(10, score))
    
    # Convert to grade
    grade = "F"
    for threshold, g in [(8, "A+"), (7.3, "A"), (6.5, "A-"), (6, "B+"), (5.5, "B"), (5, "B-")]:
        if score >= threshold:
            grade = g
            break
    
    return {"grade": grade, "score": round(score, 2), "confidence": 75}

@app.post("/api/grade")
async def grade_game(request: GradeRequest):
    """Grade a game with two-lane architecture."""
    
    # Our Process (Deterministic)
    our = grade_deterministic(request.sport, request.context)
    
    # AI Process
    prompt = f"""Grade this {request.sport} game: {request.home_team} vs {request.away_team}.
Context: {json.dumps(request.context)}
Return JSON: {{"grade": "A", "score": 7.5, "thesis": "brief explanation"}}"""
    
    ai = await call_ai(prompt)
    
    # Convergence
    delta = abs(our["score"] - ai["score"])
    consensus = (our["score"] * 0.6) + (ai["score"] * 0.4)
    
    if delta < 0.5:
        status = "LOCK"
    elif delta < 1.5:
        status = "ALIGNED"
    elif delta < 2.5:
        status = "DIVERGENT"
    else:
        status = "CONFLICT"
    
    return {
        "game_id": request.game_id,
        "our_process": our,
        "ai_process": ai,
        "convergence": {
            "status": status,
            "consensus_score": round(consensus, 2),
            "delta": round(delta, 2)
        }
    }

@app.get("/api/games")
async def get_games(sport: str = "nba"):
    """Get sample games."""
    return [
        {
            "id": f"{sport}-001",
            "home_team": "Lakers",
            "away_team": "Warriors",
            "time": "19:30",
            "our_grade": "A",
            "ai_grade": "A-",
            "status": "ALIGNED"
        },
        {
            "id": f"{sport}-002",
            "home_team": "Celtics",
            "away_team": "Heat",
            "time": "20:00",
            "our_grade": "B+",
            "ai_grade": "B",
            "status": "ALIGNED"
        }
    ]
