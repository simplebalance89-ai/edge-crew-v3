"""
Edge Crew v3.0 - AI Processor Service
Multi-model AI grading with ensemble voting and circuit breaker pattern.
"""

import asyncio
import json
import logging
import os
import random
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-processor")


class ModelTier(str, Enum):
    FAST = "fast"
    REASONING = "reasoning"
    PREMIUM = "premium"


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ModelConfig:
    name: str
    endpoint: str
    api_key: str
    tier: ModelTier
    timeout: int = 30
    failure_threshold: int = 5
    recovery_timeout: int = 60


# Model configurations from environment
MODELS: Dict[str, ModelConfig] = {
    "deepseek-v3": ModelConfig(
        name="DeepSeek-V3-0324",
        endpoint=os.environ.get("DEEPSEEK_ENDPOINT", "https://api.deepseek.com/v1"),
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        tier=ModelTier.FAST,
        timeout=30,
    ),
    "grok-fast": ModelConfig(
        name="grok-4-fast",
        endpoint=os.environ.get("GROK_ENDPOINT", "https://api.x.ai/v1"),
        api_key=os.environ.get("GROK_API_KEY", ""),
        tier=ModelTier.FAST,
        timeout=20,
    ),
    "kimi-k2": ModelConfig(
        name="kimi-k2.5",
        endpoint=os.environ.get("KIMI_ENDPOINT", "https://api.moonshot.cn/v1"),
        api_key=os.environ.get("KIMI_API_KEY", ""),
        tier=ModelTier.REASONING,
        timeout=60,
    ),
    "claude": ModelConfig(
        name="claude-3-5-sonnet",
        endpoint=os.environ.get("ANTHROPIC_ENDPOINT", "https://api.anthropic.com/v1"),
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        tier=ModelTier.PREMIUM,
        timeout=45,
    ),
}

# Fallback chains by tier
FALLBACK_CHAINS = {
    ModelTier.FAST: ["deepseek-v3", "grok-fast"],
    ModelTier.REASONING: ["kimi-k2", "deepseek-v3"],
    ModelTier.PREMIUM: ["claude", "kimi-k2"],
}


class CircuitBreaker:
    """Circuit breaker pattern for resilient AI calling."""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.failures = 0
        self.last_failure = 0
        self.state = CircuitState.CLOSED
    
    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure > self.config.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit {self.config.name}: entering half-open state")
                return True
            return False
        return True  # HALF_OPEN
    
    def record_success(self):
        self.failures = 0
        self.state = CircuitState.CLOSED
    
    def record_failure(self):
        self.failures += 1
        self.last_failure = time.time()
        if self.failures >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit {self.config.name}: OPENED after {self.failures} failures")


# Global circuit breakers
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(model_key: str) -> CircuitBreaker:
    if model_key not in _circuit_breakers:
        _circuit_breakers[model_key] = CircuitBreaker(MODELS[model_key])
    return _circuit_breakers[model_key]


# Pydantic models
class GradeRequest(BaseModel):
    game_id: str
    sport: str
    home_team: str
    away_team: str
    context: Dict = Field(default_factory=dict)
    tier: ModelTier = ModelTier.REASONING


class ModelPrediction(BaseModel):
    model: str
    grade: str
    score: float
    confidence: float
    thesis: str
    key_factors: List[str]
    latency_ms: int


class AIGradeResponse(BaseModel):
    game_id: str
    consensus_grade: str
    consensus_score: float
    confidence: float
    predictions: List[ModelPrediction]
    model_breakdown: Dict[str, float]
    fusion_method: str = "weighted_average"
    processing_time_ms: int


class HealthResponse(BaseModel):
    status: str
    models: Dict[str, str]
    version: str = "3.0.0"


async def call_model(
    model_key: str,
    prompt: str,
    max_tokens: int = 1000
) -> Tuple[str, int]:
    """Call a single AI model with circuit breaker protection."""
    config = MODELS[model_key]
    circuit = get_circuit_breaker(model_key)
    
    if not circuit.can_execute():
        raise Exception(f"Circuit breaker open for {config.name}")
    
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient(timeout=config.timeout) as client:
            headers = {
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": config.name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            }
            
            resp = await client.post(
                f"{config.endpoint}/chat/completions",
                headers=headers,
                json=payload
            )
            resp.raise_for_status()
            
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            latency = int((time.time() - start_time) * 1000)
            
            circuit.record_success()
            return content, latency
            
    except Exception as e:
        circuit.record_failure()
        raise e


def build_grading_prompt(sport: str, home: str, away: str, context: Dict) -> str:
    """Build sport-specific grading prompt."""
    return f"""You are an expert {sport.upper()} betting analyst. Grade this game for the HOME team ({home}) vs AWAY team ({away}).

Game Context:
{json.dumps(context, indent=2)}

Provide your analysis in this EXACT JSON format:
{{
    "grade": "A+/A/A-/B+/B/B-/C+/C/D/F",
    "score": 0.0-10.0,
    "thesis": "One sentence explaining the key edge",
    "confidence": 0-100,
    "key_factors": ["factor1", "factor2", "factor3"]
}}

Respond with ONLY the JSON, no other text."""


def parse_grade_response(response: str) -> Dict:
    """Parse and validate model response."""
    # Extract JSON from response
    try:
        # Try to find JSON in code blocks
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        
        data = json.loads(response.strip())
        
        # Validate required fields
        required = ["grade", "score", "thesis", "confidence", "key_factors"]
        for field in required:
            if field not in data:
                raise ValueError(f"Missing field: {field}")
        
        return data
    except Exception as e:
        logger.error(f"Failed to parse response: {e}")
        return {
            "grade": "F",
            "score": 0.0,
            "thesis": f"Parse error: {str(e)[:50]}",
            "confidence": 0,
            "key_factors": []
        }


async def grade_with_fallback(
    request: GradeRequest,
    side: str = "home"
) -> ModelPrediction:
    """Grade with automatic model fallback."""
    prompt = build_grading_prompt(
        request.sport,
        request.home_team if side == "home" else request.away_team,
        request.away_team if side == "home" else request.home_team,
        request.context
    )
    
    fallback_chain = FALLBACK_CHAINS[request.tier]
    last_error = None
    
    for model_key in fallback_chain:
        if model_key not in MODELS:
            continue
        
        # Try with retries
        for attempt in range(3):
            try:
                if attempt > 0:
                    delay = min(2 ** attempt + random.random(), 10)
                    await asyncio.sleep(delay)
                
                response, latency = await call_model(model_key, prompt)
                parsed = parse_grade_response(response)
                
                return ModelPrediction(
                    model=MODELS[model_key].name,
                    grade=parsed["grade"],
                    score=parsed["score"],
                    confidence=parsed["confidence"],
                    thesis=parsed["thesis"],
                    key_factors=parsed["key_factors"],
                    latency_ms=latency
                )
                
            except Exception as e:
                last_error = e
                logger.warning(f"{model_key} attempt {attempt + 1} failed: {e}")
    
    raise last_error or Exception("All models failed")


def calculate_consensus(predictions: List[ModelPrediction]) -> Tuple[str, float, float]:
    """Calculate weighted consensus from multiple predictions."""
    if not predictions:
        return "F", 0.0, 0.0
    
    # Convert confidence to weight (higher confidence = more weight)
    total_weight = sum(p.confidence for p in predictions)
    
    if total_weight == 0:
        # Simple average if no confidence
        avg_score = sum(p.score for p in predictions) / len(predictions)
    else:
        # Weighted average
        avg_score = sum(p.score * p.confidence for p in predictions) / total_weight
    
    # Calculate consensus confidence (lower variance = higher confidence)
    if len(predictions) > 1:
        variance = sum((p.score - avg_score) ** 2 for p in predictions) / len(predictions)
        consensus_confidence = max(0, 100 - variance * 10)
    else:
        consensus_confidence = predictions[0].confidence
    
    # Convert score to grade
    grade_thresholds = [
        (8.0, "A+"), (7.3, "A"), (6.5, "A-"),
        (6.0, "B+"), (5.5, "B"), (5.0, "B-"),
        (4.5, "C+"), (3.5, "C"), (2.5, "D"), (0.0, "F")
    ]
    
    consensus_grade = "F"
    for threshold, grade in grade_thresholds:
        if avg_score >= threshold:
            consensus_grade = grade
            break
    
    return consensus_grade, avg_score, consensus_confidence


# FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    logger.info("AI Processor starting up...")
    yield
    logger.info("AI Processor shutting down...")


app = FastAPI(
    title="Edge Crew AI Processor",
    version="3.0.0",
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    model_status = {}
    for key, config in MODELS.items():
        circuit = get_circuit_breaker(key)
        model_status[config.name] = circuit.state.value
    
    return HealthResponse(
        status="healthy",
        models=model_status
    )


@app.post("/grade", response_model=AIGradeResponse)
async def grade_game(request: GradeRequest):
    """Grade a game using multi-model ensemble."""
    start_time = time.time()
    
    # Get predictions from multiple models in parallel
    tasks = [
        grade_with_fallback(request, side="home"),
        grade_with_fallback(request, side="away")
    ]
    
    try:
        predictions = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out failures
        valid_predictions = [
            p for p in predictions 
            if not isinstance(p, Exception)
        ]
        
        if not valid_predictions:
            raise HTTPException(status_code=503, detail="All AI models failed")
        
        # Calculate consensus
        consensus_grade, consensus_score, confidence = calculate_consensus(valid_predictions)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return AIGradeResponse(
            game_id=request.game_id,
            consensus_grade=consensus_grade,
            consensus_score=round(consensus_score, 2),
            confidence=round(confidence, 2),
            predictions=valid_predictions,
            model_breakdown={p.model: p.score for p in valid_predictions},
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        logger.error(f"Grading failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch-grade")
async def batch_grade(requests: List[GradeRequest], background_tasks: BackgroundTasks):
    """Grade multiple games in batch."""
    results = []
    
    # Process with semaphore to limit concurrency
    semaphore = asyncio.Semaphore(5)
    
    async def grade_one(req: GradeRequest):
        async with semaphore:
            try:
                return await grade_game(req)
            except Exception as e:
                logger.error(f"Batch grade failed for {req.game_id}: {e}")
                return None
    
    tasks = [grade_one(req) for req in requests]
    results = await asyncio.gather(*tasks)
    
    return {
        "graded": len([r for r in results if r is not None]),
        "failed": len([r for r in results if r is None]),
        "results": [r for r in results if r is not None]
    }


@app.get("/models")
async def list_models():
    """List available models and their status."""
    return {
        "models": [
            {
                "key": key,
                "name": config.name,
                "tier": config.tier.value,
                "circuit_state": get_circuit_breaker(key).state.value
            }
            for key, config in MODELS.items()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
