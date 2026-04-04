"""
Edge Crew v3.0 - Convergence Engine
Bayesian fusion of deterministic and AI grades with real-time streaming.
"""

import asyncio
import json
import logging
import math
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, AsyncGenerator

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("convergence")


class ConvergenceStatus(str, Enum):
    LOCK = "LOCK"
    ALIGNED = "ALIGNED"
    DIVERGENT = "DIVERGENT"
    CONFLICT = "CONFLICT"


class GradeComponent(BaseModel):
    score: float = Field(..., ge=0, le=10)
    grade: str
    confidence: float = Field(..., ge=0, le=100)
    details: Dict = Field(default_factory=dict)


class ConvergenceResult(BaseModel):
    game_id: str
    sport: str
    home_team: str
    away_team: str
    
    # Two lanes
    our_process: GradeComponent
    ai_process: GradeComponent
    
    # Convergence
    consensus_score: float
    consensus_grade: str
    status: ConvergenceStatus
    delta: float
    variance: float
    
    # Pick recommendation
    pick_side: Optional[str] = None
    pick_confidence: float = 0.0
    kelly_fraction: float = 0.0
    suggested_sizing: str = "PASS"
    
    # Metadata
    generated_at: str
    fusion_method: str = "bayesian_weighted"


@dataclass
class FusionWeights:
    """Dynamic weights based on historical accuracy."""
    our_weight: float = 0.6
    ai_weight: float = 0.4
    
    def normalize(self):
        total = self.our_weight + self.ai_weight
        return FusionWeights(
            our_weight=self.our_weight / total,
            ai_weight=self.ai_weight / total
        )


class ConvergenceEngine:
    """Core fusion engine using Bayesian methods."""
    
    def __init__(self, db_pool: asyncpg.Pool, redis_client: redis.Redis):
        self.db = db_pool
        self.redis = redis_client
        self.weights = FusionWeights()
    
    def fuse_grades(
        self,
        our: GradeComponent,
        ai: GradeComponent
    ) -> ConvergenceResult:
        """
        Bayesian fusion of two grade sources.
        
        Uses precision-weighted average where precision = confidence²
        """
        # Convert confidence to precision (inverse variance)
        our_precision = (our.confidence / 100) ** 2
        ai_precision = (ai.confidence / 100) ** 2
        
        # Normalize weights
        weights = self.weights.normalize()
        
        # Weighted precision
        our_weighted_precision = our_precision * weights.our_weight
        ai_weighted_precision = ai_precision * weights.ai_weight
        
        total_precision = our_weighted_precision + ai_weighted_precision
        
        if total_precision == 0:
            # Fallback to simple average
            consensus_score = (our.score + ai.score) / 2
            variance = 1.0
        else:
            # Precision-weighted fusion
            consensus_score = (
                our.score * our_weighted_precision +
                ai.score * ai_weighted_precision
            ) / total_precision
            
            # Uncertainty propagation
            variance = 1 / total_precision
        
        # Agreement metrics
        delta = abs(our.score - ai.score)
        
        # Determine convergence status
        if delta < 0.5 and variance < 0.5:
            status = ConvergenceStatus.LOCK
        elif delta < 1.5:
            status = ConvergenceStatus.ALIGNED
        elif delta < 2.5:
            status = ConvergenceStatus.DIVERGENT
        else:
            status = ConvergenceStatus.CONFLICT
        
        # Convert to grade
        consensus_grade = self._score_to_grade(consensus_score)
        
        # Calculate pick recommendation
        pick_side, pick_confidence = self._generate_pick(
            our, ai, consensus_score, status
        )
        
        # Kelly criterion sizing
        kelly = self._kelly_criterion(pick_confidence, 2.0)  # Assume -110 odds
        suggested_sizing = self._kelly_to_units(kelly)
        
        return ConvergenceResult(
            game_id="",  # Set by caller
            sport="",
            home_team="",
            away_team="",
            our_process=our,
            ai_process=ai,
            consensus_score=round(consensus_score, 2),
            consensus_grade=consensus_grade,
            status=status,
            delta=round(delta, 2),
            variance=round(variance, 2),
            pick_side=pick_side,
            pick_confidence=round(pick_confidence, 2),
            kelly_fraction=round(kelly, 4),
            suggested_sizing=suggested_sizing,
            generated_at="",
        )
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        thresholds = [
            (8.0, "A+"), (7.3, "A"), (6.5, "A-"),
            (6.0, "B+"), (5.5, "B"), (5.0, "B-"),
            (4.5, "C+"), (3.5, "C"), (2.5, "D"), (0.0, "F")
        ]
        for threshold, grade in thresholds:
            if score >= threshold:
                return grade
        return "F"
    
    def _generate_pick(
        self,
        our: GradeComponent,
        ai: GradeComponent,
        consensus: float,
        status: ConvergenceStatus
    ) -> tuple:
        """Generate pick recommendation."""
        # Only bet on LOCK or ALIGNED
        if status not in (ConvergenceStatus.LOCK, ConvergenceStatus.ALIGNED):
            return None, 0.0
        
        # Need strong consensus
        if consensus < 6.5:  # B+ threshold
            return None, 0.0
        
        # Use the higher confidence side
        if our.confidence > ai.confidence:
            pick_confidence = our.confidence * (consensus / 10)
        else:
            pick_confidence = ai.confidence * (consensus / 10)
        
        # Consensus must be better than both individual scores
        if consensus < max(our.score, ai.score):
            pick_confidence *= 0.9  # Slight penalty
        
        return "home", pick_confidence  # Simplified - would analyze sides
    
    def _kelly_criterion(self, edge_pct: float, odds: float = 2.0) -> float:
        """
        Calculate Kelly Criterion fraction.
        
        f* = (bp - q) / b
        
        where:
        b = odds - 1 (decimal odds minus 1)
        p = probability of winning
        q = 1 - p
        """
        # Convert edge percentage to win probability
        # Assume fair odds imply 50%, edge shifts from there
        p = min(0.95, 0.5 + (edge_pct / 200))  # Cap at 95%
        q = 1 - p
        b = odds - 1
        
        kelly = (b * p - q) / b
        
        # Fractional Kelly (quarter Kelly for safety)
        return max(0, kelly * 0.25)
    
    def _kelly_to_units(self, kelly: float) -> str:
        """Convert Kelly fraction to unit sizing."""
        if kelly >= 0.08:
            return "2u"
        elif kelly >= 0.05:
            return "1.5u"
        elif kelly >= 0.03:
            return "1u"
        elif kelly >= 0.01:
            return "0.5u"
        else:
            return "PASS"
    
    async def save_convergence(self, result: ConvergenceResult):
        """Save convergence result to database."""
        try:
            await self.db.execute(
                """
                INSERT INTO convergence_history 
                (time, game_id, sport, our_score, ai_score, consensus_score, 
                 our_confidence, ai_confidence, status, delta, variance)
                VALUES (NOW(), $1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                result.game_id,
                result.sport,
                result.our_process.score,
                result.ai_process.score,
                result.consensus_score,
                result.our_process.confidence,
                result.ai_process.confidence,
                result.status.value,
                result.delta,
                result.variance
            )
        except Exception as e:
            logger.error(f"Failed to save convergence: {e}")
    
    async def publish_update(self, result: ConvergenceResult):
        """Publish update to Redis for real-time clients."""
        try:
            await self.redis.publish(
                f"game:{result.game_id}:updates",
                json.dumps(result.dict())
            )
        except Exception as e:
            logger.error(f"Failed to publish update: {e}")


# FastAPI app setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database and Redis connections."""
    # Startup
    app.state.db = await asyncpg.create_pool(
        os.environ.get("DATABASE_URL", "postgresql://edgecrew:edgecrew@localhost:5432/edgecrew"),
        min_size=2,
        max_size=10
    )
    app.state.redis = redis.Redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379"),
        decode_responses=True
    )
    app.state.engine = ConvergenceEngine(app.state.db, app.state.redis)
    
    logger.info("Convergence Engine started")
    yield
    
    # Shutdown
    await app.state.db.close()
    await app.state.redis.close()
    logger.info("Convergence Engine stopped")


app = FastAPI(
    title="Edge Crew Convergence Engine",
    version="3.0.0",
    lifespan=lifespan
)


class FuseRequest(BaseModel):
    game_id: str
    sport: str
    home_team: str
    away_team: str
    our_process: GradeComponent
    ai_process: GradeComponent


@app.get("/health")
async def health_check():
    """Health check."""
    return {"status": "healthy", "version": "3.0.0"}


@app.post("/fuse", response_model=ConvergenceResult)
async def fuse_grades(request: FuseRequest):
    """Fuse Our Process and AI Process grades."""
    try:
        engine: ConvergenceEngine = app.state.engine
        
        result = engine.fuse_grades(
            request.our_process,
            request.ai_process
        )
        
        # Fill in game details
        result.game_id = request.game_id
        result.sport = request.sport
        result.home_team = request.home_team
        result.away_team = request.away_team
        result.generated_at = "2026-04-04T00:00:00Z"  # Use actual timestamp
        
        # Persist and publish
        await engine.save_convergence(result)
        await engine.publish_update(result)
        
        return result
        
    except Exception as e:
        logger.error(f"Fusion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stream/{game_id}")
async def stream_updates(game_id: str):
    """Server-Sent Events for real-time grade updates."""
    redis_client: redis.Redis = app.state.redis
    
    async def event_generator() -> AsyncGenerator[str, None]:
        # Send initial connection message
        yield f"data: {json.dumps({'type': 'connected', 'game_id': game_id})}\n\n"
        
        # Subscribe to Redis channel
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"game:{game_id}:updates")
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    yield f"data: {data}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
        finally:
            await pubsub.unsubscribe()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/game/{game_id}")
async def get_convergence(game_id: str):
    """Get latest convergence for a game."""
    db: asyncpg.Pool = app.state.db
    
    try:
        row = await db.fetchrow(
            """
            SELECT * FROM convergence_history 
            WHERE game_id = $1 
            ORDER BY time DESC 
            LIMIT 1
            """,
            game_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="Game not found")
        
        return {
            "game_id": row["game_id"],
            "sport": row["sport"],
            "consensus_score": row["consensus_score"],
            "status": row["status"],
            "our_score": row["our_score"],
            "ai_score": row["ai_score"],
            "generated_at": row["time"].isoformat()
        }
        
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/picks/today")
async def get_todays_picks():
    """Get all picks for today."""
    db: asyncpg.Pool = app.state.db
    
    try:
        rows = await db.fetch(
            """
            SELECT * FROM convergence_history 
            WHERE time > NOW() - INTERVAL '24 hours'
            AND status IN ('LOCK', 'ALIGNED')
            AND consensus_score >= 6.5
            ORDER BY consensus_score DESC
            """
        )
        
        return {
            "picks": [dict(row) for row in rows],
            "count": len(rows)
        }
        
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
