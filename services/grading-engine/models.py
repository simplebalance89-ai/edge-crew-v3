"""
Edge Crew v3.0 - Deterministic Grading Engine Models
Data models for the grading pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class SportType(str, Enum):
    """Supported sport types."""
    NBA = "nba"
    NCAAB = "ncaab"
    NHL = "nhl"
    MLB = "mlb"
    NFL = "nfl"
    NCAAF = "ncaaf"
    SOCCER = "soccer"


class Grade(str, Enum):
    """Edge Crew grade classifications."""
    A_PLUS = "A+"
    A = "A"
    A_MINUS = "A-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    C_PLUS = "C+"
    C = "C"
    C_MINUS = "C-"
    D = "D"
    F = "F"
    HOLD = "HOLD"


class MarketType(str, Enum):
    """Types of betting markets."""
    SPREAD = "spread"
    MONEYLINE = "moneyline"
    TOTAL = "total"
    TEAM_TOTAL = "team_total"
    FIRST_HALF = "first_half"
    SECOND_HALF = "second_half"
    QUARTER = "quarter"
    PERIOD = "period"
    PLAYER_PROP = "player_prop"
    GAME_PROP = "game_prop"


class ChainType(str, Enum):
    """Types of chain bonuses detected."""
    THE_MISPRICING = "THE_MISPRICING"
    FATIGUE_FADE = "FATIGUE_FADE"
    REVENGE_GAME = "REVENGE_GAME"
    LINE_MOVEMENT = "LINE_MOVEMENT"
    SHARP_MONEY = "SHARP_MONEY"
    REST_ADVANTAGE = "REST_ADVANTAGE"
    TRAVEL_IMPACT = "TRAVEL_IMPACT"
    MOTIVATION_EDGE = "MOTIVATION_EDGE"
    WEATHER_IMPACT = "WEATHER_IMPACT"
    INJURY_CLUSTER = "INJURY_CLUSTER"
    SITUATIONAL_SPOT = "SITUATIONAL_SPOT"
    COACHING_TENDENCY = "COACHING_TENDENCY"


@dataclass
class Team:
    """Team data structure."""
    id: str
    name: str
    abbreviation: str
    sport: SportType
    conference: Optional[str] = None
    division: Optional[str] = None
    ranking: Optional[int] = None
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Player:
    """Player data structure."""
    id: str
    name: str
    position: str
    team_id: str
    is_active: bool = True
    is_injured: bool = False
    injury_status: Optional[str] = None
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Game:
    """Game data structure."""
    id: str
    sport: SportType
    home_team: Team
    away_team: Team
    game_time: datetime
    market_type: MarketType
    spread: Optional[float] = None
    total: Optional[float] = None
    home_moneyline: Optional[float] = None
    away_moneyline: Optional[float] = None
    weather: Optional[Dict[str, Any]] = None
    venue: Optional[Dict[str, Any]] = None
    line_history: List[Dict[str, Any]] = field(default_factory=list)
    public_betting_pct: Optional[float] = None
    sharp_money_indicator: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TeamProfile:
    """Comprehensive team profile with 20+ variables."""
    team_id: str
    sport: SportType
    
    # Sintonia 20-variable matrix
    offensive_rating: float = 0.0
    defensive_rating: float = 0.0
    pace_rating: float = 0.0
    efficiency_rating: float = 0.0
    turnover_rate: float = 0.0
    rebounding_efficiency: float = 0.0
    shooting_efficiency: float = 0.0
    three_point_efficiency: float = 0.0
    free_throw_efficiency: float = 0.0
    assist_to_turnover_ratio: float = 0.0
    
    # Advanced metrics
    recent_form_rating: float = 0.0  # Last 5 games
    home_away_split: float = 0.0
    rest_advantage: float = 0.0
    schedule_strength: float = 0.0
    matchup_history: float = 0.0
    clutch_performance: float = 0.0
    
    # Sport-specific
    pitching_rotation_rating: Optional[float] = None  # MLB
    bullpen_rating: Optional[float] = None  # MLB
    power_play_efficiency: Optional[float] = None  # NHL
    penalty_kill_efficiency: Optional[float] = None  # NHL
    red_zone_efficiency: Optional[float] = None  # NFL/NCAAF
    third_down_conversion: Optional[float] = None  # NFL/NCAAF
    
    # Context
    injuries_impact: float = 0.0
    travel_distance: float = 0.0
    days_of_rest: int = 0
    back_to_back: bool = False
    
    # Raw data storage
    raw_stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SintoniaScore:
    """Sintonia profile scoring result."""
    score: float
    confidence: float
    component_scores: Dict[str, float] = field(default_factory=dict)
    variable_contributions: Dict[str, float] = field(default_factory=dict)
    explanation: str = ""


@dataclass
class EdgeScore:
    """Edge situational scoring result."""
    score: float
    situational_factors: List[str] = field(default_factory=list)
    edge_type: str = ""
    magnitude: str = ""  # "small", "medium", "large"
    confidence: float = 0.0


@dataclass
class PeterRulesResult:
    """Peter rules kills and boosts result."""
    adjustment: float
    kills: List[str] = field(default_factory=list)
    boosts: List[str] = field(default_factory=list)
    kill_severity: int = 0  # 1-5 scale
    boost_strength: int = 0  # 1-5 scale
    explanation: str = ""


@dataclass
class RenzoValidation:
    """Renzo data gaps finder result."""
    validation: float  # -1.0 to 1.0
    data_gaps: List[str] = field(default_factory=list)
    data_quality_score: float = 0.0  # 0.0 to 1.0
    warnings: List[str] = field(default_factory=list)
    missing_data_points: int = 0


@dataclass
class Chain:
    """Detected chain bonus."""
    chain_type: ChainType
    bonus: float
    confidence: float
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChainDetectionResult:
    """Chain detection result."""
    chains: List[Chain] = field(default_factory=list)
    total_bonus: float = 0.0
    primary_chain: Optional[ChainType] = None


@dataclass
class SharpMoneySignal:
    """Sharp money detection signal."""
    detected: bool
    confidence: float
    signal_type: str  # "reverse_line_movement", "steam_move", "early_limit", etc.
    strength: float  # 0.0 to 1.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketScanResult:
    """Market scanner result."""
    sharp_signals: List[SharpMoneySignal] = field(default_factory=list)
    line_movement_score: float = 0.0
    public_sharp_divergence: float = 0.0
    overall_signal: float = 0.0


@dataclass
class EngineGrade:
    """Final grading result from the deterministic engine."""
    score: float
    grade: Grade
    components: Dict[str, Any] = field(default_factory=dict)
    chains: List[Chain] = field(default_factory=list)
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    game_id: str = ""
    side: str = ""
    
    # Explanations
    grade_explanation: str = ""
    recommendation: str = ""
    risk_level: str = ""  # "low", "medium", "high"


@dataclass
class GradeRequest:
    """Request to grade a game."""
    game: Game
    side: str  # "home" or "away"
    market_type: MarketType = MarketType.SPREAD
    additional_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchGradeRequest:
    """Request to grade multiple games."""
    games: List[GradeRequest]
    priority: str = "normal"  # "low", "normal", "high"


@dataclass
class BatchGradeResponse:
    """Response for batch grading."""
    results: List[EngineGrade]
    summary: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0
