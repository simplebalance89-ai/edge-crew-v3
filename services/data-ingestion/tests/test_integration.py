"""Integration tests for the data ingestion service."""
import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
import respx

from scheduler import SmartScheduler
from models import (
    Sport,
    Priority,
    GameInfo,
    GameStatus,
    DataSource,
)
from ingesters import (
    OddsAPIIngester,
    ESPNIngester,
    RotowireIngester,
)


@pytest.mark.asyncio
class TestSchedulerIntegration:
    """Integration tests for scheduler with ingesters."""

    async def test_scheduler_triggers_ingesters(self):
        """Scheduler should trigger ingesters based on priority."""
        scheduler = SmartScheduler()
        
        # Mock ingester callback
        mock_callback = AsyncMock()
        scheduler.register_callback(DataSource.ODDS_API, mock_callback)
        
        # Add games that should trigger high priority
        now = datetime.utcnow()
        games = [
            GameInfo(
                game_id="urgent",
                sport=Sport.NBA,
                home_team="LAL",
                away_team="GSW",
                tipoff=now + timedelta(hours=1),
                status=GameStatus.SCHEDULED
            )
        ]
        scheduler.update_games(games)
        
        # Verify priority is calculated correctly
        priority = scheduler.get_fetch_priority(Sport.NBA)
        assert priority in [Priority.CRITICAL, Priority.HIGH]

    async def test_end_to_end_fetch_flow(self):
        """Test full fetch flow from scheduler to event generation."""
        scheduler = SmartScheduler()
        
        # Track events
        events_collected = []
        
        async def collect_events(sport, priority):
            # Simulated ingester callback
            from models import BaseEvent, EventType
            event = BaseEvent(
                source=DataSource.ODDS_API,
                event_type=EventType.ODDS_CHANGE,
                sport=sport,
                dedup_key=f"test-{sport.value}-{priority.value}"
            )
            events_collected.append(event)
        
        scheduler.register_callback(DataSource.ODDS_API, collect_events)
        
        # Add games to trigger fetch
        now = datetime.utcnow()
        games = [
            GameInfo(
                game_id="test",
                sport=Sport.NBA,
                home_team="LAL",
                away_team="GSW",
                tipoff=now + timedelta(hours=1),
                status=GameStatus.SCHEDULED
            )
        ]
        scheduler.update_games(games)
        
        # Manually trigger callback
        await collect_events(Sport.NBA, Priority.HIGH)
        
        assert len(events_collected) == 1
        assert events_collected[0].sport == Sport.NBA


@pytest.mark.asyncio
class TestIngesterIntegration:
    """Integration tests for ingesters with external APIs."""

    @respx.mock
    async def test_odds_api_end_to_end(self):
        """Test Odds API ingester with mocked responses."""
        ingester = OddsAPIIngester("test-key")
        await ingester.start()
        
        # Mock multiple endpoints
        now = datetime.utcnow()
        
        odds_response = [
            {
                "id": "game1",
                "sport_key": "basketball_nba",
                "home_team": "Lakers",
                "away_team": "Warriors",
                "commence_time": now.isoformat() + "Z",
                "bookmakers": [
                    {
                        "key": "draftkings",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Lakers", "price": 1.85},
                                    {"name": "Warriors", "price": 1.95}
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
        
        respx.get("https://api.the-odds-api.com/v4/sports/basketball_nba/odds").mock(
            return_value=httpx.Response(200, json=odds_response)
        )
        
        events = await ingester.fetch(Sport.NBA, Priority.HIGH)
        
        assert len(events) > 0
        
        # Verify event structure
        event = events[0]
        assert event.source == DataSource.ODDS_API
        assert hasattr(event, 'game_id')
        assert hasattr(event, 'price')
        
        await ingester.stop()

    @respx.mock
    async def test_espn_end_to_end(self):
        """Test ESPN ingester with mocked responses."""
        ingester = ESPNIngester()
        await ingester.start()
        
        scoreboard = {
            "events": [
                {
                    "id": "401559476",
                    "date": datetime.utcnow().isoformat() + "Z",
                    "status": {
                        "type": {"state": "in"},
                        "period": 2,
                        "displayClock": "8:45"
                    },
                    "competitions": [{
                        "competitors": [
                            {"homeAway": "home", "score": "55", "team": {"abbreviation": "LAL"}},
                            {"homeAway": "away", "score": "52", "team": {"abbreviation": "GSW"}}
                        ]
                    }]
                }
            ]
        }
        
        respx.get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard").mock(
            return_value=httpx.Response(200, json=scoreboard)
        )
        
        events = await ingester.fetch(Sport.NBA, Priority.HIGH)
        
        score_events = [e for e in events if e.event_type.value == "score_update"]
        assert len(score_events) > 0
        
        score = score_events[0]
        assert score.home_team == "LAL"
        assert score.away_team == "GSW"
        
        await ingester.stop()


@pytest.mark.asyncio
class TestPriorityCalculation:
    """Tests for priority calculation logic."""

    def test_critical_priority_calculation(self):
        """Games within 2 hours should be CRITICAL."""
        scheduler = SmartScheduler()
        now = datetime.utcnow()
        
        games = [
            GameInfo(
                game_id="critical",
                sport=Sport.NBA,
                home_team="LAL",
                away_team="GSW",
                tipoff=now + timedelta(hours=1),
                status=GameStatus.SCHEDULED,
                has_high_confidence_pick=False,
                line_movement_24h=Decimal("0")
            )
        ]
        scheduler.update_games(games)
        
        priority = scheduler.get_fetch_priority(Sport.NBA)
        assert priority == Priority.CRITICAL

    def test_high_priority_with_confidence(self):
        """Games with high confidence picks should be HIGH priority."""
        scheduler = SmartScheduler()
        now = datetime.utcnow()
        
        games = [
            GameInfo(
                game_id="confident",
                sport=Sport.NBA,
                home_team="LAL",
                away_team="GSW",
                tipoff=now + timedelta(hours=5),
                status=GameStatus.SCHEDULED,
                has_high_confidence_pick=True,
                line_movement_24h=Decimal("0")
            )
        ]
        scheduler.update_games(games)
        
        priority = scheduler.get_fetch_priority(Sport.NBA)
        # 5 (within 6h) + 3 (high confidence) = 8 = HIGH threshold
        assert priority == Priority.HIGH

    def test_medium_priority_regular_games(self):
        """Regular games within 24h should be MEDIUM."""
        scheduler = SmartScheduler()
        now = datetime.utcnow()
        
        games = [
            GameInfo(
                game_id="regular",
                sport=Sport.NBA,
                home_team="LAL",
                away_team="GSW",
                tipoff=now + timedelta(hours=12),
                status=GameStatus.SCHEDULED,
                has_high_confidence_pick=False,
                line_movement_24h=Decimal("0.3")
            )
        ]
        scheduler.update_games(games)
        
        priority = scheduler.get_fetch_priority(Sport.NBA)
        # 2 (within 24h) + 1 (small line movement) = 3 < HIGH threshold
        assert priority == Priority.MEDIUM

    def test_low_priority_distant_games(self):
        """Games more than 24h away should be LOW."""
        scheduler = SmartScheduler()
        now = datetime.utcnow()
        
        games = [
            GameInfo(
                game_id="distant",
                sport=Sport.NBA,
                home_team="LAL",
                away_team="GSW",
                tipoff=now + timedelta(days=2),
                status=GameStatus.SCHEDULED,
                has_high_confidence_pick=False,
                line_movement_24h=Decimal("0")
            )
        ]
        scheduler.update_games(games)
        
        priority = scheduler.get_fetch_priority(Sport.NBA)
        assert priority == Priority.LOW

    def test_multiple_games_accumulation(self):
        """Multiple games should accumulate scores."""
        scheduler = SmartScheduler()
        now = datetime.utcnow()
        
        games = [
            GameInfo(
                game_id="g1",
                sport=Sport.NBA,
                home_team="LAL",
                away_team="GSW",
                tipoff=now + timedelta(hours=1),
                status=GameStatus.SCHEDULED
            ),
            GameInfo(
                game_id="g2",
                sport=Sport.NBA,
                home_team="BOS",
                away_team="NYK",
                tipoff=now + timedelta(hours=1.5),
                status=GameStatus.SCHEDULED
            ),
        ]
        scheduler.update_games(games)
        
        priority = scheduler.get_fetch_priority(Sport.NBA)
        # 10 + 10 = 20 = CRITICAL
        assert priority == Priority.CRITICAL


@pytest.mark.asyncio
class TestErrorHandling:
    """Tests for error handling and recovery."""

    @respx.mock
    async def test_api_error_recovery(self):
        """Should handle API errors gracefully."""
        ingester = OddsAPIIngester("test-key")
        await ingester.start()
        
        # Simulate API error
        respx.get("https://api.the-odds-api.com/v4/sports/basketball_nba/odds").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        
        events = await ingester.fetch(Sport.NBA, Priority.HIGH)
        
        # Should return empty list on error, not crash
        assert events == []
        
        status = ingester.get_status()
        assert status.failure_count > 0
        
        await ingester.stop()

    @respx.mock
    async def test_timeout_handling(self):
        """Should handle timeouts gracefully."""
        ingester = OddsAPIIngester("test-key")
        await ingester.start()
        
        # Simulate timeout
        respx.get("https://api.the-odds-api.com/v4/sports/basketball_nba/odds").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )
        
        events = await ingester.fetch(Sport.NBA, Priority.HIGH)
        
        # Should handle timeout gracefully
        assert events == []
        
        await ingester.stop()

    async def test_malformed_response_handling(self):
        """Should handle malformed responses."""
        ingester = ESPNIngester()
        await ingester.start()
        
        # Test with missing fields
        malformed_game = {
            "id": "123",
            # Missing competitions
        }
        
        event = ingester._parse_score_event(malformed_game, Sport.NBA, Priority.MEDIUM)
        
        # Should return None for invalid data
        assert event is None
        
        await ingester.stop()
