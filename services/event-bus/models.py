"""
Pydantic models for Edge Crew v3.0 Event Bus.

Defines all event types and their schemas for type-safe event handling.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    """All supported event types in the Edge Crew system."""
    
    # Odds events
    ODDS_UPDATED = "odds.updated"
    ODDS_LINE_MOVED = "odds.line_moved"
    
    # Injury events
    INJURY_REPORTED = "injury.reported"
    
    # Game lifecycle events
    GAME_STARTED = "game.started"
    GAME_COMPLETED = "game.completed"
    
    # Grading events
    GRADE_REQUESTED = "grade.requested"
    GRADE_COMPLETED = "grade.completed"
    
    # Edge detection events
    EDGE_DETECTED = "edge.detected"
    
    # Pick generation events
    PICK_GENERATED = "pick.generated"


class EventMetadata(BaseModel):
    """Metadata attached to every event."""
    
    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event creation timestamp")
    source: str = Field(default="unknown", description="Service that produced the event")
    correlation_id: Optional[str] = Field(default=None, description="For tracing related events")
    retry_count: int = Field(default=0, ge=0, description="Number of processing attempts")
    version: str = Field(default="1.0", description="Event schema version")


class BaseEvent(BaseModel):
    """Base model for all events."""
    
    metadata: EventMetadata = Field(default_factory=EventMetadata)
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event-specific data")
    
    @property
    def event_type(self) -> str:
        """Override in subclasses to specify event type."""
        raise NotImplementedError
    
    def to_stream_data(self) -> Dict[str, str]:
        """Convert event to Redis Stream entry format."""
        return {
            "event_type": self.event_type,
            "data": self.model_dump_json(),
        }
    
    @classmethod
    def from_stream_data(cls, data: Dict[str, str]) -> "BaseEvent":
        """Parse event from Redis Stream entry."""
        import json
        event_data = json.loads(data.get("data", "{}"))
        return cls.model_validate(event_data)


# ============================================================================
# Odds Events
# ============================================================================

class OddsData(BaseModel):
    """Odds data for a specific bookmaker."""
    
    bookmaker: str = Field(..., description="Name of the bookmaker")
    spread: Optional[float] = Field(default=None, description="Point spread")
    spread_odds: Optional[int] = Field(default=None, description="Odds for the spread")
    moneyline_home: Optional[int] = Field(default=None)
    moneyline_away: Optional[int] = Field(default=None)
    total: Optional[float] = Field(default=None, description="Over/under total")
    over_odds: Optional[int] = Field(default=None)
    under_odds: Optional[int] = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OddsUpdatedEvent(BaseEvent):
    """Emitted when new odds are available for a game."""
    
    game_id: str = Field(..., description="Unique game identifier")
    sport: str = Field(..., description="Sport type (nba, nfl, etc.)")
    home_team: str
    away_team: str
    odds: OddsData
    
    @property
    def event_type(self) -> str:
        return EventType.ODDS_UPDATED


class LineMovementData(BaseModel):
    """Details about a line movement."""
    
    previous_spread: Optional[float] = None
    new_spread: Optional[float] = None
    previous_total: Optional[float] = None
    new_total: Optional[float] = None
    movement_timestamp: datetime = Field(default_factory=datetime.utcnow)


class OddsLineMovedEvent(BaseEvent):
    """Emitted when odds move significantly."""
    
    game_id: str
    bookmaker: str
    movement: LineMovementData
    movement_threshold_exceeded: bool = Field(
        default=False,
        description="Whether movement exceeded configured threshold"
    )
    
    @property
    def event_type(self) -> str:
        return EventType.ODDS_LINE_MOVED


# ============================================================================
# Injury Events
# ============================================================================

class InjuryStatus(str, Enum):
    """Player injury status classifications."""
    
    OUT = "out"
    DOUBTFUL = "doubtful"
    QUESTIONABLE = "questionable"
    PROBABLE = "probable"


class InjuryReportedEvent(BaseEvent):
    """Emitted when a new injury is reported."""
    
    player_id: str
    player_name: str
    team: str
    game_id: Optional[str] = None
    injury_type: str
    status: InjuryStatus
    expected_return: Optional[str] = None
    impact_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Estimated impact on team performance (0-10)"
    )
    
    @property
    def event_type(self) -> str:
        return EventType.INJURY_REPORTED


# ============================================================================
# Game Lifecycle Events
# ============================================================================

class GameStartedEvent(BaseEvent):
    """Emitted when a game begins."""
    
    game_id: str
    sport: str
    home_team: str
    away_team: str
    start_time: datetime
    broadcast_info: Optional[Dict[str, Any]] = None
    
    @property
    def event_type(self) -> str:
        return EventType.GAME_STARTED


class GameResult(BaseModel):
    """Final game result."""
    
    home_score: int
    away_score: int
    winner: str
    total_points: int
    covering_team: Optional[str] = None


class GameCompletedEvent(BaseEvent):
    """Emitted when a game ends."""
    
    game_id: str
    result: GameResult
    duration_minutes: Optional[int] = None
    overtime_periods: int = Field(default=0)
    
    @property
    def event_type(self) -> str:
        return EventType.GAME_COMPLETED


# ============================================================================
# Grading Events
# ============================================================================

class GradeRequestedEvent(BaseEvent):
    """Emitted to request grading of a pick or game."""
    
    game_id: str
    pick_id: Optional[str] = None
    grading_type: str = Field(
        default="auto",
        description="auto, manual, or dispute"
    )
    priority: int = Field(default=5, ge=1, le=10)
    requested_by: str
    
    @property
    def event_type(self) -> str:
        return EventType.GRADE_REQUESTED


class GradeResult(BaseModel):
    """Result of grading a pick."""
    
    status: str = Field(..., pattern="^(win|loss|push|void|pending)$")
    units: float
    closing_line: Optional[Dict[str, Any]] = None
    grade_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: Optional[str] = None


class GradeCompletedEvent(BaseEvent):
    """Emitted when grading is complete."""
    
    game_id: str
    pick_id: Optional[str] = None
    result: GradeResult
    graded_by: str
    graded_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def event_type(self) -> str:
        return EventType.GRADE_COMPLETED


# ============================================================================
# Edge Detection Events
# ============================================================================

class EdgeData(BaseModel):
    """Details about detected edge."""
    
    edge_percentage: float = Field(..., ge=0.0, description="Edge as percentage")
    model_prediction: float
    market_line: float
    expected_value: float
    confidence: float = Field(..., ge=0.0, le=1.0)
    factors: List[str] = Field(default_factory=list)


class EdgeDetectedEvent(BaseEvent):
    """Emitted when an edge is detected on a game."""
    
    game_id: str
    edge_type: str = Field(..., pattern="^(spread|moneyline|total)$")
    bookmaker: str
    edge: EdgeData
    recommended_action: str = Field(
        default="monitor",
        pattern="^(bet|monitor|pass|strong_bet)$"
    )
    expires_at: Optional[datetime] = None
    
    @property
    def event_type(self) -> str:
        return EventType.EDGE_DETECTED


# ============================================================================
# Pick Generation Events
# ============================================================================

class PickData(BaseModel):
    """Generated pick details."""
    
    pick_type: str = Field(..., pattern="^(spread|moneyline|total|prop)$")
    selection: str
    line: float
    odds: int
    units: float = Field(..., gt=0.0)
    bookmaker: str
    rationale: Optional[str] = None


class PickGeneratedEvent(BaseEvent):
    """Emitted when a new pick is generated."""
    
    pick_id: str = Field(default_factory=lambda: str(uuid4()))
    game_id: str
    sport: str
    pick: PickData
    model_version: str
    edge_at_creation: Optional[EdgeData] = None
    risk_level: str = Field(default="medium", pattern="^(low|medium|high)$")
    
    @property
    def event_type(self) -> str:
        return EventType.PICK_GENERATED


# ============================================================================
# Event Registry
# ============================================================================

EVENT_REGISTRY: Dict[str, type[BaseEvent]] = {
    EventType.ODDS_UPDATED: OddsUpdatedEvent,
    EventType.ODDS_LINE_MOVED: OddsLineMovedEvent,
    EventType.INJURY_REPORTED: InjuryReportedEvent,
    EventType.GAME_STARTED: GameStartedEvent,
    EventType.GAME_COMPLETED: GameCompletedEvent,
    EventType.GRADE_REQUESTED: GradeRequestedEvent,
    EventType.GRADE_COMPLETED: GradeCompletedEvent,
    EventType.EDGE_DETECTED: EdgeDetectedEvent,
    EventType.PICK_GENERATED: PickGeneratedEvent,
}


def parse_event(event_type: str, data: Dict[str, str]) -> BaseEvent:
    """Parse a raw event into the appropriate type."""
    if event_type not in EVENT_REGISTRY:
        # Return a generic event for unknown types
        return BaseEvent.model_validate({
            "metadata": {"event_type": event_type},
            "payload": data
        })
    
    event_class = EVENT_REGISTRY[event_type]
    return event_class.from_stream_data(data)
