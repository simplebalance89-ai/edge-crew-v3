"""
Data models for raw ingested data.
All timestamps are UTC.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum, StrEnum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_serializer


class DataSource(StrEnum):
    """Supported data sources."""
    ODDS_API = "odds_api"
    ESPN = "espn"
    ROTOWIRE = "rotowire"
    KALSHI = "kalshi"


class Sport(StrEnum):
    """Supported sports."""
    NBA = "nba"
    NCAAB = "ncaab"
    NFL = "nfl"
    NCAAF = "ncaaf"
    MLB = "mlb"
    NHL = "nhl"
    WNBA = "wnba"
    SOCCER = "soccer"
    MMA = "mma"
    BOXING = "boxing"


class EventType(StrEnum):
    """Types of data events."""
    ODDS_CHANGE = "odds_change"
    LINEUP_CHANGE = "lineup_change"
    INJURY_UPDATE = "injury_update"
    SCORE_UPDATE = "score_update"
    GAME_STATUS = "game_status"
    MARKET_UPDATE = "market_update"
    PLAYER_PROP = "player_prop"


class Priority(int, Enum):
    """Event priority levels."""
    CRITICAL = 1   # Games starting within 2 hours
    HIGH = 2       # Games within 6 hours or high confidence picks
    MEDIUM = 3     # Regular monitoring
    LOW = 4        # Background prefetch


class GameStatus(StrEnum):
    """Game status values."""
    SCHEDULED = "scheduled"
    LIVE = "live"
    HALFTIME = "halftime"
    FINAL = "final"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class InjuryStatus(StrEnum):
    """Player injury status."""
    HEALTHY = "healthy"
    QUESTIONABLE = "questionable"
    DOUBTFUL = "doubtful"
    OUT = "out"
    INJURED_RESERVE = "injured_reserve"


class BaseEvent(BaseModel):
    """Base model for all events."""
    event_id: UUID = Field(default_factory=uuid4)
    source: DataSource
    event_type: EventType
    sport: Sport
    priority: Priority = Priority.MEDIUM
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    dedup_key: str = Field(..., description="Unique key for deduplication")
    raw_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat()

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
        }


class OddsEvent(BaseEvent):
    """Odds change event."""
    event_type: EventType = EventType.ODDS_CHANGE
    game_id: str
    home_team: str
    away_team: str
    market_type: str  # spread, moneyline, total
    bookmaker: str
    line: Optional[Decimal] = None
    price: Decimal
    previous_line: Optional[Decimal] = None
    previous_price: Optional[Decimal] = None
    line_movement_24h: Decimal = Decimal("0")
    volume_indicator: Optional[str] = None


class LineupEvent(BaseEvent):
    """Lineup change event."""
    event_type: EventType = EventType.LINEUP_CHANGE
    game_id: str
    team: str
    player_id: str
    player_name: str
    is_starting: bool
    position: Optional[str] = None
    minutes_projection: Optional[int] = None


class InjuryEvent(BaseEvent):
    """Injury update event."""
    event_type: EventType = EventType.INJURY_UPDATE
    player_id: str
    player_name: str
    team: str
    status: InjuryStatus
    injury_type: Optional[str] = None
    expected_return: Optional[datetime] = None
    notes: Optional[str] = None


class ScoreEvent(BaseEvent):
    """Score update event."""
    event_type: EventType = EventType.SCORE_UPDATE
    game_id: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    period: str
    time_remaining: Optional[str] = None
    status: GameStatus


class MarketEvent(BaseEvent):
    """Kalshi market update event."""
    event_type: EventType = EventType.MARKET_UPDATE
    market_id: str
    market_title: str
    yes_price: Decimal
    no_price: Decimal
    volume: int
    open_interest: int
    close_time: Optional[datetime] = None
    related_game_id: Optional[str] = None


class PlayerPropEvent(BaseEvent):
    """Player prop odds event."""
    event_type: EventType = EventType.PLAYER_PROP
    game_id: str
    player_id: str
    player_name: str
    team: str
    stat_type: str  # points, rebounds, assists, etc.
    line: Decimal
    over_price: Decimal
    under_price: Decimal
    bookmaker: str


class GameInfo(BaseModel):
    """Game information for scheduling."""
    game_id: str
    sport: Sport
    home_team: str
    away_team: str
    tipoff: datetime
    status: GameStatus = GameStatus.SCHEDULED
    has_high_confidence_pick: bool = False
    line_movement_24h: Decimal = Decimal("0")
    priority_score: int = 0

    @field_serializer('tipoff')
    def serialize_tipoff(self, value: datetime) -> str:
        return value.isoformat()


class IngestionStatus(BaseModel):
    """Status of ingestion job."""
    source: DataSource
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    success_count: int = 0
    failure_count: int = 0
    average_latency_ms: float = 0.0
    circuit_state: str = "closed"
    is_healthy: bool = True

    @field_serializer('last_success', 'last_failure')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None


class HealthCheck(BaseModel):
    """Service health check response."""
    status: str = "healthy"
    version: str = "3.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sources: dict[DataSource, IngestionStatus] = Field(default_factory=dict)
    queue_depth: int = 0
    active_jobs: int = 0

    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat()
