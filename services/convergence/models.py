"""
Convergence Engine Models

Pydantic models for Convergence, Pick, and Portfolio data structures.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class ConvergenceStatus(str, Enum):
    """Status of convergence between engine and AI grades."""
    LOCK = "lock"           # High confidence agreement (delta < 0.5, variance < 0.5)
    ALIGNED = "aligned"     # General agreement (delta < 1.5)
    DIVERGENT = "divergent" # Disagreement (delta < 2.5)
    CONFLICT = "conflict"   # Strong disagreement (delta >= 2.5)


class MarketType(str, Enum):
    """Types of betting markets."""
    SPREAD = "spread"
    MONEYLINE = "moneyline"
    TOTAL = "total"
    PROP = "prop"
    FUTURE = "future"


class Sport(str, Enum):
    """Supported sports."""
    NBA = "nba"
    NCAAB = "ncaab"
    NFL = "nfl"
    NCAAF = "ncaaf"
    MLB = "mlb"
    NHL = "nhl"
    SOCCER = "soccer"


class EngineGrade(BaseModel):
    """Grade from the internal engine (Our Process)."""
    id: UUID = Field(default_factory=uuid4)
    game_id: str
    sport: Sport
    market: MarketType
    selection: str  # e.g., "LAL -5.5" or "Over 220.5"
    score: float = Field(..., ge=0, le=10, description="Engine grade 0-10")
    confidence: float = Field(..., ge=0, le=1, description="Confidence 0-1")
    edge_percent: float = Field(..., description="Expected edge percentage")
    factors: Dict[str, float] = Field(default_factory=dict, description="Factor breakdown")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError('Confidence must be between 0 and 1')
        return v


class AIGrade(BaseModel):
    """Grade from the AI analysis process."""
    id: UUID = Field(default_factory=uuid4)
    game_id: str
    sport: Sport
    market: MarketType
    selection: str
    score: float = Field(..., ge=0, le=10, description="AI grade 0-10")
    confidence: float = Field(..., ge=0, le=1, description="Confidence 0-1")
    edge_percent: float = Field(..., description="Expected edge percentage")
    reasoning: str = Field(default="", description="AI reasoning summary")
    model_version: str = Field(default="unknown")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError('Confidence must be between 0 and 1')
        return v


class Convergence(BaseModel):
    """Result of Bayesian fusion between Engine and AI grades."""
    id: UUID = Field(default_factory=uuid4)
    game_id: str
    sport: Sport
    market: MarketType
    selection: str
    
    # Fused results
    score: float = Field(..., ge=0, le=10, description="Fused score")
    status: ConvergenceStatus
    variance: float = Field(..., ge=0, description="Uncertainty variance")
    delta: float = Field(..., ge=0, description="Absolute difference between grades")
    
    # Source grades
    our_process: EngineGrade
    ai_process: AIGrade
    
    # Calculated metrics
    confidence: float = Field(..., ge=0, le=1, description="Combined confidence")
    edge_percent: float = Field(..., description="Expected edge percentage")
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(default="3.0.0")

    @property
    def is_actionable(self) -> bool:
        """Whether this convergence meets actionable criteria."""
        return (
            self.status in (ConvergenceStatus.LOCK, ConvergenceStatus.ALIGNED)
            and self.score >= 7.0
            and self.confidence >= 0.6
        )

    @property
    def quality_score(self) -> float:
        """Overall quality score combining multiple factors."""
        return (
            self.score * 0.4 +
            (1 - self.variance) * 10 * 0.3 +
            self.confidence * 10 * 0.3
        )


class Pick(BaseModel):
    """A generated betting pick with sizing."""
    id: UUID = Field(default_factory=uuid4)
    convergence_id: UUID
    
    # Game info
    game_id: str
    sport: Sport
    market: MarketType
    selection: str
    
    # Odds and pricing
    odds: float = Field(..., description="American odds (e.g., -110, +150)")
    line: Optional[float] = Field(None, description="Spread or total line")
    
    # Grading
    convergence_score: float
    confidence: float
    edge_percent: float
    
    # Kelly sizing
    kelly_fraction: float = Field(..., ge=0, le=1, description="Full Kelly fraction")
    fractional_kelly: float = Field(default=0.25, ge=0, le=1)
    recommended_units: float = Field(..., ge=0, description="Recommended bet size in units")
    
    # Risk management
    max_units: float = Field(default=5.0, description="Maximum units for this pick")
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: str = Field(default="")

    @property
    def expected_value(self) -> float:
        """Calculate expected value of the pick."""
        prob = self.edge_percent / 100 + 0.5  # Approximate implied probability
        if self.odds > 0:
            return (prob * self.odds / 100) - (1 - prob)
        else:
            return (prob * 100 / abs(self.odds)) - (1 - prob)

    @property
    def decimal_odds(self) -> float:
        """Convert American odds to decimal."""
        if self.odds > 0:
            return self.odds / 100 + 1
        else:
            return 100 / abs(self.odds) + 1


class Portfolio(BaseModel):
    """Optimized portfolio of picks."""
    id: UUID = Field(default_factory=uuid4)
    date: datetime = Field(default_factory=datetime.utcnow)
    
    # Picks with allocation
    picks: List[Pick]
    weights: List[float] = Field(..., description="Portfolio weights summing to <= 1")
    
    # Constraints used
    max_single_position: float = Field(default=0.05)
    max_daily_exposure: float = Field(default=0.25)
    
    # Metrics
    expected_return: float
    expected_variance: float
    sharpe_ratio: float
    
    # Allocation summary
    total_allocation: float
    num_positions: int
    
    # Risk metrics
    var_95: float = Field(..., description="Value at Risk (95% confidence)")
    max_drawdown_estimate: float
    
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_balanced(self) -> bool:
        """Check if portfolio meets risk criteria."""
        return (
            self.total_allocation <= self.max_daily_exposure and
            all(w <= self.max_single_position for w in self.weights) and
            self.sharpe_ratio > 0.5
        )


class StreamEvent(BaseModel):
    """SSE event for real-time updates."""
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConvergenceRequest(BaseModel):
    """Request to fuse engine and AI grades."""
    engine_grade: EngineGrade
    ai_grade: AIGrade


class PickRequest(BaseModel):
    """Request to generate a pick from convergence."""
    convergence: Convergence
    odds: float
    line: Optional[float] = None
    bankroll_units: float = Field(default=100.0, description="Total bankroll in units")


class PortfolioRequest(BaseModel):
    """Request to optimize a portfolio."""
    picks: List[Pick]
    target_return: Optional[float] = None
    risk_tolerance: float = Field(default=0.5, ge=0, le=1)


class HealthCheck(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime
    components: Dict[str, str]
