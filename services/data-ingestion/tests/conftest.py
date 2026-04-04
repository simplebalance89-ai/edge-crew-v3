"""Test configuration and fixtures."""
import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

from models import (
    GameInfo,
    GameStatus,
    OddsEvent,
    ScoreEvent,
    LineupEvent,
    InjuryEvent,
    MarketEvent,
    DataSource,
    Sport,
    Priority,
    InjuryStatus,
    EventType,
)


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_odds_response():
    """Sample Odds API response."""
    return [
        {
            "id": "game123",
            "sport_key": "basketball_nba",
            "home_team": "Los Angeles Lakers",
            "away_team": "Golden State Warriors",
            "commence_time": datetime.utcnow().isoformat() + "Z",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Los Angeles Lakers", "price": 1.87},
                                {"name": "Golden State Warriors", "price": 1.95}
                            ]
                        },
                        {
                            "key": "spreads",
                            "outcomes": [
                                {"name": "Los Angeles Lakers", "price": 1.91, "point": -5.5},
                                {"name": "Golden State Warriors", "price": 1.91, "point": 5.5}
                            ]
                        }
                    ]
                }
            ]
        }
    ]


@pytest.fixture
def mock_espn_scoreboard():
    """Sample ESPN scoreboard response."""
    return {
        "events": [
            {
                "id": "401559476",
                "date": datetime.utcnow().isoformat() + "Z",
                "status": {
                    "type": {"state": "in", "description": "In Progress"},
                    "period": 4,
                    "displayClock": "2:34"
                },
                "competitions": [{
                    "competitors": [
                        {"homeAway": "home", "score": "112", "team": {"abbreviation": "LAL"}},
                        {"homeAway": "away", "score": "108", "team": {"abbreviation": "GSW"}}
                    ]
                }]
            }
        ]
    }


@pytest.fixture
def sample_game_info():
    """Sample game info for testing."""
    return GameInfo(
        game_id="test-game-001",
        sport=Sport.NBA,
        home_team="LAL",
        away_team="GSW",
        tipoff=datetime.utcnow() + timedelta(hours=3),
        status=GameStatus.SCHEDULED,
        has_high_confidence_pick=True,
        line_movement_24h=Decimal("1.5")
    )


@pytest.fixture
def sample_odds_event():
    """Sample odds event for testing."""
    return OddsEvent(
        source=DataSource.ODDS_API,
        sport=Sport.NBA,
        priority=Priority.HIGH,
        dedup_key="test-odds-001",
        game_id="game123",
        home_team="LAL",
        away_team="GSW",
        market_type="spread",
        bookmaker="draftkings",
        line=Decimal("-5.5"),
        price=Decimal("1.91"),
        raw_data={}
    )


@pytest.fixture
def sample_score_event():
    """Sample score event for testing."""
    return ScoreEvent(
        source=DataSource.ESPN,
        sport=Sport.NBA,
        priority=Priority.CRITICAL,
        dedup_key="test-score-001",
        game_id="game456",
        home_team="BOS",
        away_team="NYK",
        home_score=112,
        away_score=108,
        period="4",
        time_remaining="2:34",
        status=GameStatus.LIVE,
        raw_data={}
    )


@pytest.fixture
def sample_lineup_event():
    """Sample lineup event for testing."""
    return LineupEvent(
        source=DataSource.ROTOWIRE,
        sport=Sport.NBA,
        priority=Priority.HIGH,
        dedup_key="test-lineup-001",
        game_id="game789",
        team="LAL",
        player_id="player123",
        player_name="LeBron James",
        is_starting=True,
        position="SF",
        minutes_projection=36,
        raw_data={}
    )


@pytest.fixture
def sample_injury_event():
    """Sample injury event for testing."""
    return InjuryEvent(
        source=DataSource.ESPN,
        sport=Sport.NBA,
        priority=Priority.HIGH,
        dedup_key="test-injury-001",
        player_id="player456",
        player_name="Stephen Curry",
        team="GSW",
        status=InjuryStatus.QUESTIONABLE,
        injury_type="Ankle Sprain",
        notes="Questionable for tonight's game",
        raw_data={}
    )


@pytest.fixture
def sample_market_event():
    """Sample market event for testing."""
    return MarketEvent(
        source=DataSource.KALSHI,
        sport=Sport.NBA,
        priority=Priority.MEDIUM,
        dedup_key="test-market-001",
        market_id="market123",
        market_title="Will LAL win tonight?",
        yes_price=Decimal("0.65"),
        no_price=Decimal("0.35"),
        volume=15000,
        open_interest=5000,
        raw_data={}
    )
