"""Tests for data models."""
import pytest
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from models import (
    BaseEvent,
    DataSource,
    EventType,
    GameInfo,
    GameStatus,
    HealthCheck,
    InjuryEvent,
    InjuryStatus,
    LineupEvent,
    MarketEvent,
    OddsEvent,
    PlayerPropEvent,
    Priority,
    ScoreEvent,
    Sport,
)


class TestDataModels:
    """Test data model creation and serialization."""

    def test_base_event_creation(self):
        event = BaseEvent(
            source=DataSource.ODDS_API,
            event_type=EventType.ODDS_CHANGE,
            sport=Sport.NBA,
            dedup_key="test-key-123",
            raw_data={"test": "data"}
        )
        assert event.source == DataSource.ODDS_API
        assert event.event_type == EventType.ODDS_CHANGE
        assert event.sport == Sport.NBA
        assert isinstance(event.event_id, UUID)
        assert event.priority == Priority.MEDIUM

    def test_odds_event_creation(self):
        event = OddsEvent(
            source=DataSource.ODDS_API,
            sport=Sport.NBA,
            dedup_key="odds-test",
            game_id="game123",
            home_team="LAL",
            away_team="GSW",
            market_type="spread",
            bookmaker="draftkings",
            line=Decimal("-5.5"),
            price=Decimal("1.91"),
            raw_data={}
        )
        assert event.game_id == "game123"
        assert event.home_team == "LAL"
        assert event.away_team == "GSW"
        assert event.line == Decimal("-5.5")

    def test_lineup_event_creation(self):
        event = LineupEvent(
            source=DataSource.ROTOWIRE,
            sport=Sport.NBA,
            dedup_key="lineup-test",
            game_id="game456",
            team="LAL",
            player_id="player789",
            player_name="LeBron James",
            is_starting=True,
            position="SF",
            minutes_projection=36
        )
        assert event.is_starting is True
        assert event.minutes_projection == 36
        assert event.position == "SF"

    def test_injury_event_creation(self):
        event = InjuryEvent(
            source=DataSource.ESPN,
            sport=Sport.NBA,
            dedup_key="injury-test",
            player_id="player123",
            player_name="Stephen Curry",
            team="GSW",
            status=InjuryStatus.QUESTIONABLE,
            injury_type="Ankle Sprain"
        )
        assert event.status == InjuryStatus.QUESTIONABLE
        assert event.injury_type == "Ankle Sprain"

    def test_score_event_creation(self):
        event = ScoreEvent(
            source=DataSource.ESPN,
            sport=Sport.NBA,
            dedup_key="score-test",
            game_id="game789",
            home_team="BOS",
            away_team="NYK",
            home_score=112,
            away_score=108,
            period="4",
            time_remaining="2:34",
            status=GameStatus.LIVE
        )
        assert event.home_score == 112
        assert event.status == GameStatus.LIVE

    def test_market_event_creation(self):
        event = MarketEvent(
            source=DataSource.KALSHI,
            sport=Sport.NBA,
            dedup_key="market-test",
            market_id="market123",
            market_title="LAL to win tonight?",
            yes_price=Decimal("0.65"),
            no_price=Decimal("0.35"),
            volume=15000,
            open_interest=5000
        )
        assert event.yes_price == Decimal("0.65")
        assert event.volume == 15000

    def test_player_prop_event_creation(self):
        event = PlayerPropEvent(
            source=DataSource.ODDS_API,
            sport=Sport.NBA,
            dedup_key="prop-test",
            game_id="game999",
            player_id="player111",
            player_name="Kevin Durant",
            team="PHX",
            stat_type="points",
            line=Decimal("27.5"),
            over_price=Decimal("1.87"),
            under_price=Decimal("1.95"),
            bookmaker="fanduel"
        )
        assert event.stat_type == "points"
        assert event.line == Decimal("27.5")

    def test_game_info_creation(self):
        game = GameInfo(
            game_id="game001",
            sport=Sport.NFL,
            home_team="KC",
            away_team="SF",
            tipoff=datetime(2024, 2, 11, 18, 30),
            status=GameStatus.SCHEDULED,
            has_high_confidence_pick=True,
            line_movement_24h=Decimal("2.5")
        )
        assert game.has_high_confidence_pick is True
        assert game.line_movement_24h == Decimal("2.5")

    def test_health_check_creation(self):
        health = HealthCheck(
            status="healthy",
            version="3.0.0",
            queue_depth=100,
            active_jobs=5
        )
        assert health.status == "healthy"
        assert health.queue_depth == 100

    def test_event_serialization(self):
        event = OddsEvent(
            source=DataSource.ODDS_API,
            sport=Sport.NBA,
            dedup_key="serialize-test",
            game_id="game123",
            home_team="LAL",
            away_team="GSW",
            market_type="spread",
            bookmaker="draftkings",
            line=Decimal("-5.5"),
            price=Decimal("1.91"),
            raw_data={"extra": "data"}
        )
        
        # Test that it can be serialized to dict
        data = event.model_dump(mode="json")
        assert data["source"] == "odds_api"
        assert data["sport"] == "nba"
        assert data["line"] == "-5.5"  # Decimal serialized as string
        assert "event_id" in data
        assert "timestamp" in data

    def test_priority_enum(self):
        assert Priority.CRITICAL.value == 1
        assert Priority.HIGH.value == 2
        assert Priority.MEDIUM.value == 3
        assert Priority.LOW.value == 4

    def test_sport_enum_values(self):
        assert Sport.NBA.value == "nba"
        assert Sport.NFL.value == "nfl"
        assert Sport.MLB.value == "mlb"

    def test_data_source_enum_values(self):
        assert DataSource.ODDS_API.value == "odds_api"
        assert DataSource.ESPN.value == "espn"
        assert DataSource.ROTOWIRE.value == "rotowire"
        assert DataSource.KALSHI.value == "kalshi"


class TestDeduplication:
    """Test deduplication key generation."""

    def test_dedup_key_uniqueness(self):
        event1 = BaseEvent(
            source=DataSource.ODDS_API,
            event_type=EventType.ODDS_CHANGE,
            sport=Sport.NBA,
            dedup_key="key-1"
        )
        event2 = BaseEvent(
            source=DataSource.ODDS_API,
            event_type=EventType.ODDS_CHANGE,
            sport=Sport.NBA,
            dedup_key="key-2"
        )
        assert event1.dedup_key != event2.dedup_key

    def test_same_dedup_key_same_event(self):
        event1 = BaseEvent(
            source=DataSource.ODDS_API,
            event_type=EventType.ODDS_CHANGE,
            sport=Sport.NBA,
            dedup_key="same-key"
        )
        event2 = BaseEvent(
            source=DataSource.ODDS_API,
            event_type=EventType.ODDS_CHANGE,
            sport=Sport.NBA,
            dedup_key="same-key"
        )
        assert event1.dedup_key == event2.dedup_key
