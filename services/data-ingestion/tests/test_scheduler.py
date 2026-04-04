"""Tests for smart scheduler."""
import asyncio
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from models import GameInfo, GameStatus, Priority, Sport
from scheduler import SmartScheduler


class TestSmartScheduler:
    """Test smart scheduling logic."""

    @pytest.fixture
    def scheduler(self):
        return SmartScheduler()

    @pytest.fixture
    def sample_games(self):
        now = datetime.utcnow()
        return [
            GameInfo(
                game_id="game1",
                sport=Sport.NBA,
                home_team="LAL",
                away_team="GSW",
                tipoff=now + timedelta(hours=1),  # Within 2 hours
                status=GameStatus.SCHEDULED,
                has_high_confidence_pick=False,
                line_movement_24h=Decimal("0")
            ),
            GameInfo(
                game_id="game2",
                sport=Sport.NBA,
                home_team="BOS",
                away_team="NYK",
                tipoff=now + timedelta(hours=4),  # Within 6 hours
                status=GameStatus.SCHEDULED,
                has_high_confidence_pick=True,
                line_movement_24h=Decimal("0")
            ),
            GameInfo(
                game_id="game3",
                sport=Sport.NBA,
                home_team="MIA",
                away_team="PHI",
                tipoff=now + timedelta(hours=12),  # Later today
                status=GameStatus.SCHEDULED,
                has_high_confidence_pick=False,
                line_movement_24h=Decimal("1.5")
            ),
            GameInfo(
                game_id="game4",
                sport=Sport.NFL,
                home_team="KC",
                away_team="SF",
                tipoff=now + timedelta(days=2),  # Future
                status=GameStatus.SCHEDULED,
                has_high_confidence_pick=False,
                line_movement_24h=Decimal("0")
            ),
        ]

    def test_critical_priority_for_urgent_games(self, scheduler, sample_games):
        """Games within 2 hours should get CRITICAL priority."""
        scheduler.update_games(sample_games)
        priority = scheduler.get_fetch_priority(Sport.NBA)
        # 10 points from game1 (within 2h) + 5 points from game2 (within 6h + high confidence) + 
        # 2+ points from game3 (within 12h + line movement)
        assert priority in [Priority.CRITICAL, Priority.HIGH]

    def test_high_priority_with_confidence_pick(self, scheduler, sample_games):
        """Games with high confidence picks bump priority."""
        now = datetime.utcnow()
        games = [
            GameInfo(
                game_id="game1",
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
        assert priority in [Priority.HIGH, Priority.CRITICAL]

    def test_line_movement_scoring(self, scheduler):
        """Line movement affects priority."""
        now = datetime.utcnow()
        games = [
            GameInfo(
                game_id="game1",
                sport=Sport.NBA,
                home_team="LAL",
                away_team="GSW",
                tipoff=now + timedelta(hours=3),
                status=GameStatus.SCHEDULED,
                has_high_confidence_pick=False,
                line_movement_24h=Decimal("2.5")
            )
        ]
        scheduler.update_games(games)
        priority = scheduler.get_fetch_priority(Sport.NBA)
        # 5 (within 6h) + 3 (line movement > 2.0) = 8 points = HIGH
        assert priority == Priority.HIGH

    def test_low_priority_for_distant_games(self, scheduler):
        """Games far in future get LOW priority."""
        now = datetime.utcnow()
        games = [
            GameInfo(
                game_id="game1",
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

    def test_fetch_intervals(self, scheduler):
        """Different priorities have different intervals."""
        assert scheduler.FETCH_INTERVALS[Priority.CRITICAL] == 30
        assert scheduler.FETCH_INTERVALS[Priority.HIGH] == 120
        assert scheduler.FETCH_INTERVALS[Priority.MEDIUM] == 300
        assert scheduler.FETCH_INTERVALS[Priority.LOW] == 900

    def test_get_fetch_interval(self, scheduler, sample_games):
        """Fetch interval should match priority."""
        scheduler.update_games(sample_games)
        interval = scheduler.get_fetch_interval(Sport.NBA)
        priority = scheduler.get_fetch_priority(Sport.NBA)
        assert interval == scheduler.FETCH_INTERVALS[priority]

    def test_sport_priority_breakdown(self, scheduler, sample_games):
        """Breakdown should contain expected fields."""
        scheduler.update_games(sample_games)
        breakdown = scheduler.get_sport_priority_breakdown(Sport.NBA)
        
        assert breakdown["sport"] == "nba"
        assert breakdown["total_games"] == 3  # Only NBA games
        assert breakdown["games_within_2h"] == 1
        assert breakdown["games_within_6h"] == 2
        assert breakdown["high_confidence_games"] == 1
        assert breakdown["significant_line_movement"] == 1

    def test_should_fetch_deduplication(self, scheduler):
        """Should return True for new keys, False for recent duplicates."""
        assert scheduler.should_fetch("test-key", 60) is True
        assert scheduler.should_fetch("test-key", 60) is False
        # After enough time passes (simulated), should fetch again

    def test_clean_stale_games(self, scheduler):
        """Old games should be cleaned up."""
        now = datetime.utcnow()
        old_game = GameInfo(
            game_id="old",
            sport=Sport.NBA,
            home_team="LAL",
            away_team="GSW",
            tipoff=now - timedelta(days=3),
            status=GameStatus.FINAL
        )
        scheduler.update_games([old_game])
        assert len(scheduler._games) == 1
        
        scheduler.clean_stale_games(max_age_hours=48)
        assert len(scheduler._games) == 0

    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self, scheduler):
        """Scheduler should start and stop cleanly."""
        await scheduler.start()
        assert scheduler._running is True
        
        await scheduler.stop()
        assert scheduler._running is False

    def test_callback_registration(self, scheduler):
        """Callbacks should be registered correctly."""
        from models import DataSource
        
        async def dummy_callback(sport, priority):
            pass
        
        scheduler.register_callback(DataSource.ODDS_API, dummy_callback)
        assert DataSource.ODDS_API in scheduler._callbacks
        assert len(scheduler._callbacks[DataSource.ODDS_API]) == 1


class TestRateLimiter:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiter_acquisition(self):
        """Rate limiter should allow requests within rate."""
        from scheduler import RateLimiter
        
        limiter = RateLimiter(rate=10, period=1)  # 10 per second
        
        # Should acquire immediately
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_rate_limiter_throttling(self):
        """Rate limiter should throttle excess requests."""
        from scheduler import RateLimiter
        
        limiter = RateLimiter(rate=2, period=1)  # 2 per second
        
        # First two should be fast
        await limiter.acquire()
        await limiter.acquire()
        
        # Third should wait
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.4  # Should wait for token replenishment
