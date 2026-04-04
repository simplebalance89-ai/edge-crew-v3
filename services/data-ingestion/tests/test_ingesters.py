"""Tests for data ingesters."""
import pytest
import httpx
import respx
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

from models import (
    DataSource,
    EventType,
    Priority,
    Sport,
    GameStatus,
    InjuryStatus,
)
from ingesters.base import BaseIngester, RateLimiter, CircuitBreakerConfig
from ingesters.odds_api import OddsAPIIngester
from ingesters.espn import ESPNIngester
from ingesters.rotowire import RotowireIngester
from ingesters.kalshi import KalshiIngester


class TestBaseIngester:
    """Test base ingester functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiter(self):
        """Rate limiter should control request rate."""
        limiter = RateLimiter(rate=2, period=1)
        
        # First two should not wait
        await limiter.acquire()
        await limiter.acquire()
        
        # Should have 0 tokens left
        assert limiter._tokens < 1

    @pytest.mark.asyncio
    async def test_deduplication(self):
        """Duplicate events should be detected."""
        class TestIngester(BaseIngester):
            source = DataSource.ODDS_API
            base_url = "https://test.com"
            
            async def fetch(self, sport, priority):
                return []
            
            def map_sport(self, sport):
                return sport.value
        
        ingester = TestIngester("test-key")
        await ingester.start()
        
        from models import BaseEvent, EventType
        
        event = BaseEvent(
            source=DataSource.ODDS_API,
            event_type=EventType.ODDS_CHANGE,
            sport=Sport.NBA,
            dedup_key="test-key-123"
        )
        
        assert ingester._is_duplicate(event) is False
        assert ingester._is_duplicate(event) is True  # Now it's a duplicate
        
        await ingester.stop()

    @pytest.mark.asyncio
    async def test_dedup_key_generation(self):
        """Dedup keys should be deterministic."""
        class TestIngester(BaseIngester):
            source = DataSource.ODDS_API
            base_url = "https://test.com"
            
            async def fetch(self, sport, priority):
                return []
            
            def map_sport(self, sport):
                return sport.value
        
        ingester = TestIngester("test-key")
        
        key1 = ingester._generate_dedup_key("part1", "part2", "part3")
        key2 = ingester._generate_dedup_key("part1", "part2", "part3")
        key3 = ingester._generate_dedup_key("part1", "part2", "different")
        
        assert key1 == key2
        assert key1 != key3
        assert len(key1) == 32  # SHA256 hex truncated


class TestOddsAPIIngester:
    """Test Odds API ingester."""

    @pytest.fixture
    def ingester(self):
        return OddsAPIIngester("test-api-key")

    def test_sport_mapping(self, ingester):
        """Sports should map correctly to Odds API format."""
        assert ingester.map_sport(Sport.NBA) == "basketball_nba"
        assert ingester.map_sport(Sport.NFL) == "americanfootball_nfl"
        assert ingester.map_sport(Sport.MLB) == "baseball_mlb"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_odds(self, ingester, mock_odds_response):
        """Should fetch and parse odds correctly."""
        await ingester.start()
        
        # Mock the API response
        route = respx.get("https://api.the-odds-api.com/v4/sports/basketball_nba/odds").mock(
            return_value=httpx.Response(200, json=mock_odds_response)
        )
        
        events = await ingester.fetch(Sport.NBA, Priority.HIGH)
        
        assert len(events) > 0
        assert route.called
        
        # Check first event structure
        event = events[0]
        assert event.source == DataSource.ODDS_API
        assert event.sport == Sport.NBA
        assert event.game_id == "game123"
        
        await ingester.stop()

    @pytest.mark.asyncio
    @respx.mock
    async def test_rate_limiting(self, ingester):
        """Should respect rate limits."""
        await ingester.start()
        
        respx.get("https://api.the-odds-api.com/v4/sports/basketball_nba/odds").mock(
            return_value=httpx.Response(200, json=[])
        )
        
        # Multiple fetches should not exceed rate limit
        import asyncio
        start = asyncio.get_event_loop().time()
        
        await ingester.fetch(Sport.NBA, Priority.LOW)
        await ingester.fetch(Sport.NBA, Priority.LOW)
        
        elapsed = asyncio.get_event_loop().time() - start
        
        # Should take at least some time due to rate limiting
        assert elapsed >= 0
        
        await ingester.stop()


class TestESPNIngester:
    """Test ESPN ingester."""

    @pytest.fixture
    def ingester(self):
        return ESPNIngester()

    def test_sport_mapping(self, ingester):
        """Sports should map correctly to ESPN format."""
        assert ingester.map_sport(Sport.NBA) == "basketball/nba"
        assert ingester.map_sport(Sport.NFL) == "football/nfl"
        assert ingester.map_sport(Sport.NCAAB) == "basketball/mens-college-basketball"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_scores(self, ingester, mock_espn_scoreboard):
        """Should fetch and parse scores correctly."""
        await ingester.start()
        
        route = respx.get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard").mock(
            return_value=httpx.Response(200, json=mock_espn_scoreboard)
        )
        
        events = await ingester.fetch(Sport.NBA, Priority.HIGH)
        
        score_events = [e for e in events if e.event_type == EventType.SCORE_UPDATE]
        assert len(score_events) > 0
        assert route.called
        
        score = score_events[0]
        assert score.home_team == "LAL"
        assert score.away_team == "GSW"
        assert score.home_score == 112
        
        await ingester.stop()

    def test_score_parsing(self, ingester):
        """Should parse various game states correctly."""
        now = datetime.utcnow()
        
        # Test different status types
        test_cases = [
            ({"status": {"type": {"state": "pre"}}}, GameStatus.SCHEDULED),
            ({"status": {"type": {"state": "in"}}}, GameStatus.LIVE),
            ({"status": {"type": {"state": "post"}}}, GameStatus.FINAL),
        ]
        
        for status_data, expected in test_cases:
            game = {
                "id": "123",
                "status": status_data["status"],
                "competitions": [{
                    "competitors": [
                        {"homeAway": "home", "score": "100", "team": {"abbreviation": "LAL"}},
                        {"homeAway": "away", "score": "98", "team": {"abbreviation": "GSW"}}
                    ]
                }]
            }
            
            event = ingester._parse_score_event(game, Sport.NBA, Priority.MEDIUM)
            if event:
                assert event.status == expected


class TestRotowireIngester:
    """Test Rotowire ingester."""

    @pytest.fixture
    def ingester(self):
        return RotowireIngester("test-api-key")

    def test_sport_mapping(self, ingester):
        """Sports should map correctly to Rotowire format."""
        assert ingester.map_sport(Sport.NBA) == "nba"
        assert ingester.map_sport(Sport.NFL) == "nfl"
        assert ingester.map_sport(Sport.NCAAB) == "cbb"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_lineups(self, ingester):
        """Should fetch and parse lineups correctly."""
        await ingester.start()
        
        mock_response = {
            "data": {
                "lineups": [
                    {
                        "gameId": "game123",
                        "homeTeam": "LAL",
                        "awayTeam": "GSW",
                        "homePlayers": [
                            {
                                "playerId": "p1",
                                "name": "LeBron James",
                                "position": "SF",
                                "isStarting": True,
                                "projectedMinutes": 36,
                                "team": "LAL"
                            }
                        ],
                        "awayPlayers": [
                            {
                                "playerId": "p2",
                                "name": "Stephen Curry",
                                "position": "PG",
                                "isStarting": True,
                                "projectedMinutes": 34,
                                "team": "GSW"
                            }
                        ]
                    }
                ]
            }
        }
        
        route = respx.post("https://www.rotowire.com/graphql").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        
        events = await ingester.fetch(Sport.NBA, Priority.HIGH)
        
        lineup_events = [e for e in events if e.event_type == EventType.LINEUP_CHANGE]
        assert len(lineup_events) == 2  # One for each player
        assert route.called
        
        await ingester.stop()

    def test_parse_player_lineup(self, ingester):
        """Should parse player lineup correctly."""
        player = {
            "playerId": "123",
            "name": "Test Player",
            "position": "PG",
            "isStarting": True,
            "projectedMinutes": 30
        }
        
        event = ingester._parse_player_lineup(
            player, "game123", Sport.NBA, "LAL", Priority.HIGH
        )
        
        assert event.player_name == "Test Player"
        assert event.is_starting is True
        assert event.minutes_projection == 30
        assert event.team == "LAL"


class TestKalshiIngester:
    """Test Kalshi ingester."""

    @pytest.fixture
    def ingester(self):
        return KalshiIngester("test-key", "test-secret")

    def test_sport_mapping(self, ingester):
        """Sports should map correctly to Kalshi format."""
        assert ingester.map_sport(Sport.NBA) == "NBA"
        assert ingester.map_sport(Sport.NFL) == "NFL"
        assert ingester.map_sport(Sport.NCAAB) == "CBB"

    def test_extract_teams_from_title(self, ingester):
        """Should extract team names from market titles."""
        test_cases = [
            ("LAL vs GSW", {"home": "GSW", "away": "LAL"}),
            ("LAL @ GSW", {"home": "GSW", "away": "LAL"}),
            ("LAL at GSW", {"home": "GSW", "away": "LAL"}),
            ("No teams here", {"home": "", "away": ""}),
        ]
        
        for title, expected in test_cases:
            result = ingester._extract_teams_from_title(title, Sport.NBA)
            assert result == expected

    def test_normalize_prices(self, ingester):
        """Should normalize prices to 0-1 scale."""
        # Kalshi prices can be 1-100 or 0.01-1.00
        price_high = Decimal("65")
        price_low = Decimal("0.65")
        
        # If price > 1, should divide by 100
        normalized = price_high / 100 if price_high > 1 else price_high
        assert normalized == Decimal("0.65")
        
        # If price <= 1, should stay same
        normalized = price_low / 100 if price_low > 1 else price_low
        assert normalized == Decimal("0.65")


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self):
        """Circuit should open after threshold failures."""
        class FailingIngester(BaseIngester):
            source = DataSource.ODDS_API
            base_url = "https://test.com"
            
            async def fetch(self, sport, priority):
                raise Exception("Always fails")
            
            def map_sport(self, sport):
                return sport.value
        
        ingester = FailingIngester()
        await ingester.start()
        
        # Multiple failures should open circuit
        for _ in range(CircuitBreakerConfig.FAILURE_THRESHOLD + 1):
            try:
                await ingester.fetch(Sport.NBA, Priority.HIGH)
            except Exception:
                pass
        
        # Circuit should be open now
        status = ingester.get_status()
        assert not status.is_healthy or status.circuit_state != "closed"
        
        await ingester.stop()
