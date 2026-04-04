"""
Pydantic models for AI grading service.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class GradeLevel(str, Enum):
    """Grade levels for picks."""
    A_PLUS = "A+"
    A = "A"
    A_MINUS = "A-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    C_PLUS = "C+"
    C = "C"
    C_MINUS = "C-"
    D_PLUS = "D+"
    D = "D"
    F = "F"
    PASS = "PASS"


class SportType(str, Enum):
    """Supported sports."""
    NFL = "nfl"
    NBA = "nba"
    NCAAB = "ncaab"
    NCAAF = "ncaaf"
    MLB = "mlb"
    NHL = "nhl"
    SOCCER = "soccer"
    UFC = "ufc"


class PickType(str, Enum):
    """Types of picks/grades."""
    SPREAD = "spread"
    MONEYLINE = "moneyline"
    TOTAL = "total"
    PROP = "prop"
    PARLAY = "parlay"
    FUTURE = "future"


class ModelProvider(str, Enum):
    """AI model providers."""
    GROK = "grok"
    DEEPSEEK = "deepseek"
    KIMI = "kimi"
    CLAUDE = "claude"
    GPT5 = "gpt5"


class ModelPrediction(BaseModel):
    """Individual model prediction."""
    model: ModelProvider
    score: float = Field(..., ge=0.0, le=100.0)
    grade: GradeLevel
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    latency_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    error: Optional[str] = None


class Team(BaseModel):
    """Team information."""
    name: str
    abbreviation: str
    record: Optional[str] = None
    rank: Optional[int] = None
    injuries: List[Dict[str, Any]] = Field(default_factory=list)
    last_games: List[Dict[str, Any]] = Field(default_factory=list)


class Game(BaseModel):
    """Game information for grading."""
    id: str
    sport: SportType
    home_team: Team
    away_team: Team
    game_time: datetime
    spread: Optional[float] = None
    total: Optional[float] = None
    home_moneyline: Optional[int] = None
    away_moneyline: Optional[int] = None
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    weather: Optional[Dict[str, Any]] = None
    venue: Optional[str] = None
    is_playoffs: bool = False
    is_primetime: bool = False
    rivalry_game: bool = False


class Pick(BaseModel):
    """Pick to be graded."""
    id: str
    game: Game
    pick_type: PickType
    selection: str  # e.g., "LAL -5.5", "OVER 220.5"
    odds: Optional[int] = None
    stake: Optional[float] = None
    analyst: Optional[str] = None
    notes: Optional[str] = None


class AIGrade(BaseModel):
    """Final AI-generated grade."""
    pick_id: str
    score: float = Field(..., ge=0.0, le=100.0)
    grade: GradeLevel
    confidence: float = Field(..., ge=0.0, le=1.0)
    consensus_score: float = Field(..., ge=0.0, le=100.0)
    breakdown: Dict[ModelProvider, float] = Field(default_factory=dict)
    model_predictions: List[ModelPrediction] = Field(default_factory=list)
    reasoning: Optional[str] = None
    key_factors: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    latency_ms: int
    models_used: List[ModelProvider] = Field(default_factory=list)
    models_failed: List[ModelProvider] = Field(default_factory=list)
    ab_test_variant: Optional[str] = None


class GradeRequest(BaseModel):
    """Request to grade a pick."""
    pick: Pick
    use_ensemble: bool = True
    required_models: Optional[List[ModelProvider]] = None
    timeout_ms: Optional[int] = 30000
    ab_test_variant: Optional[str] = None


class GradeBatchRequest(BaseModel):
    """Batch grading request."""
    picks: List[Pick]
    use_ensemble: bool = True
    max_concurrent: int = 5


class GradeResponse(BaseModel):
    """Grading response."""
    success: bool
    grade: Optional[AIGrade] = None
    error: Optional[str] = None
    processing_time_ms: int


class GradeBatchResponse(BaseModel):
    """Batch grading response."""
    results: List[GradeResponse]
    total_processed: int
    success_count: int
    failed_count: int
    total_time_ms: int


class ModelHealth(BaseModel):
    """Model health status."""
    provider: ModelProvider
    status: str  # "healthy", "degraded", "down"
    avg_latency_ms: int
    error_rate: float
    last_success: Optional[datetime]
    consecutive_failures: int
    circuit_state: str  # "closed", "open", "half-open"


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    models: List[ModelHealth]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ABTestConfig(BaseModel):
    """A/B test configuration."""
    test_id: str
    name: str
    variant_a: str
    variant_b: str
    traffic_split: float = Field(0.5, ge=0.0, le=1.0)
    metric: str
    start_date: datetime
    end_date: Optional[datetime] = None
    status: str = "running"  # "running", "paused", "completed"


class ModelWeight(BaseModel):
    """Model weight based on historical accuracy."""
    provider: ModelProvider
    weight: float = Field(..., ge=0.0, le=1.0)
    accuracy: float = Field(..., ge=0.0, le=1.0)
    sample_size: int
    last_updated: datetime
    sport_weights: Dict[SportType, float] = Field(default_factory=dict)


class GradingConfig(BaseModel):
    """Grading configuration."""
    min_confidence_threshold: float = 0.6
    min_models_required: int = 2
    grade_thresholds: Dict[GradeLevel, tuple] = Field(default_factory=lambda: {
        GradeLevel.A_PLUS: (95, 100),
        GradeLevel.A: (90, 94),
        GradeLevel.A_MINUS: (85, 89),
        GradeLevel.B_PLUS: (80, 84),
        GradeLevel.B: (75, 79),
        GradeLevel.B_MINUS: (70, 74),
        GradeLevel.C_PLUS: (65, 69),
        GradeLevel.C: (60, 64),
        GradeLevel.C_MINUS: (55, 59),
        GradeLevel.D_PLUS: (50, 54),
        GradeLevel.D: (45, 49),
        GradeLevel.F: (0, 44),
    })
    timeout_ms: int = 30000
    retry_attempts: int = 2
