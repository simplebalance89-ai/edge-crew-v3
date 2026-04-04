"""
Smart scheduling system with priority-based prefetching.

The scheduler determines fetch priority based on:
- Time to tipoff (games starting soon = higher priority)
- High confidence picks (bump priority)
- Line movement significance (significant movement = higher priority)
"""
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable, Optional

import structlog

from models import (
    DataSource,
    GameInfo,
    GameStatus,
    Priority,
    Sport,
)

logger = structlog.get_logger()


class SmartScheduler:
    """
    Intelligent scheduling system that prioritizes data fetching
    based on game proximity and betting significance.
    """

    # Priority score thresholds
    CRITICAL_THRESHOLD = 15
    HIGH_THRESHOLD = 8
    
    # Base intervals per priority (seconds)
    FETCH_INTERVALS = {
        Priority.CRITICAL: 30,    # Every 30 seconds
        Priority.HIGH: 120,       # Every 2 minutes
        Priority.MEDIUM: 300,     # Every 5 minutes
        Priority.LOW: 900,        # Every 15 minutes
    }

    def __init__(self):
        self._games: dict[str, GameInfo] = {}
        self._schedules: dict[DataSource, asyncio.Task] = {}
        self._callbacks: dict[DataSource, list[Callable]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._running = False
        self._cache: dict[str, datetime] = {}
        self._dedup_window = 60  # seconds

    async def start(self):
        """Start the scheduler."""
        self._running = True
        logger.info("scheduler.started")
        # Start the main scheduling loop
        asyncio.create_task(self._scheduling_loop())

    async def stop(self):
        """Stop the scheduler gracefully."""
        self._running = False
        for task in self._schedules.values():
            task.cancel()
        self._schedules.clear()
        logger.info("scheduler.stopped")

    def register_callback(
        self,
        source: DataSource,
        callback: Callable[[Sport, Priority], asyncio.Future]
    ):
        """Register a fetch callback for a data source."""
        self._callbacks[source].append(callback)
        logger.info("scheduler.callback_registered", source=source.value)

    def update_games(self, games: list[GameInfo]):
        """Update the game cache with new information."""
        for game in games:
            self._games[game.game_id] = game
        logger.debug(
            "scheduler.games_updated",
            count=len(games),
            total_games=len(self._games)
        )

    def get_fetch_priority(self, sport: Sport) -> Priority:
        """
        Calculate the fetch priority for a given sport.
        
        Returns Priority.CRITICAL for games starting within 2 hours
        with high significance indicators.
        """
        now = datetime.utcnow()
        score = 0
        
        games = [
            g for g in self._games.values()
            if g.sport == sport and g.status == GameStatus.SCHEDULED
        ]
        
        for game in games:
            hours_to_tip = (game.tipoff - now).total_seconds() / 3600
            
            # Time-based scoring
            if hours_to_tip < 0:
                continue  # Game already started
            elif hours_to_tip < 2:
                score += 10
            elif hours_to_tip < 6:
                score += 5
            elif hours_to_tip < 24:
                score += 2
            
            # Significance scoring
            if game.has_high_confidence_pick:
                score += 3
            if game.line_movement_24h > Decimal("2.0"):
                score += 3
            elif game.line_movement_24h > Decimal("1.0"):
                score += 2
            elif game.line_movement_24h > Decimal("0.5"):
                score += 1

        # Determine priority based on score
        if score >= self.CRITICAL_THRESHOLD:
            return Priority.CRITICAL
        elif score >= self.HIGH_THRESHOLD:
            return Priority.HIGH
        elif score > 0:
            return Priority.MEDIUM
        else:
            return Priority.LOW

    def get_fetch_interval(self, sport: Sport) -> int:
        """Get the appropriate fetch interval for a sport."""
        priority = self.get_fetch_priority(sport)
        return self.FETCH_INTERVALS[priority]

    def should_fetch(self, key: str, min_interval: int) -> bool:
        """
        Check if we should fetch based on deduplication window.
        Returns True if enough time has passed since last fetch.
        """
        now = datetime.utcnow()
        last_fetch = self._cache.get(key)
        
        if last_fetch is None:
            self._cache[key] = now
            return True
        
        elapsed = (now - last_fetch).total_seconds()
        if elapsed >= min_interval:
            self._cache[key] = now
            return True
        
        return False

    async def _scheduling_loop(self):
        """Main scheduling loop that triggers fetches."""
        while self._running:
            try:
                await self._execute_scheduled_fetches()
                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("scheduler.loop_error", error=str(e))
                await asyncio.sleep(30)

    async def _execute_scheduled_fetches(self):
        """Execute scheduled fetches for all sources."""
        for source, callbacks in self._callbacks.items():
            for sport in Sport:
                interval = self.get_fetch_interval(sport)
                cache_key = f"{source.value}:{sport.value}"
                
                if self.should_fetch(cache_key, interval):
                    priority = self.get_fetch_priority(sport)
                    logger.debug(
                        "scheduler.triggering_fetch",
                        source=source.value,
                        sport=sport.value,
                        priority=priority.name,
                        interval=interval
                    )
                    
                    # Execute all callbacks for this source
                    for callback in callbacks:
                        try:
                            asyncio.create_task(
                                callback(sport, priority),
                                name=f"fetch_{source.value}_{sport.value}"
                            )
                        except Exception as e:
                            logger.error(
                                "scheduler.callback_error",
                                source=source.value,
                                error=str(e)
                            )

    def get_sport_priority_breakdown(self, sport: Sport) -> dict:
        """Get detailed priority breakdown for a sport."""
        now = datetime.utcnow()
        games = [
            g for g in self._games.values()
            if g.sport == sport and g.status == GameStatus.SCHEDULED
        ]
        
        breakdown = {
            "sport": sport.value,
            "total_games": len(games),
            "critical_games": 0,
            "high_priority_games": 0,
            "games_within_2h": 0,
            "games_within_6h": 0,
            "high_confidence_games": 0,
            "significant_line_movement": 0,
        }
        
        for game in games:
            hours_to_tip = (game.tipoff - now).total_seconds() / 3600
            
            if 0 < hours_to_tip < 2:
                breakdown["games_within_2h"] += 1
            if 0 < hours_to_tip < 6:
                breakdown["games_within_6h"] += 1
            if game.has_high_confidence_pick:
                breakdown["high_confidence_games"] += 1
            if game.line_movement_24h > Decimal("1.0"):
                breakdown["significant_line_movement"] += 1
                
            # Calculate individual game priority
            score = 0
            if hours_to_tip < 2:
                score += 10
            elif hours_to_tip < 6:
                score += 5
            if game.has_high_confidence_pick:
                score += 3
            if game.line_movement_24h > Decimal("1.0"):
                score += 2
                
            if score >= self.CRITICAL_THRESHOLD:
                breakdown["critical_games"] += 1
            elif score >= self.HIGH_THRESHOLD:
                breakdown["high_priority_games"] += 1
        
        return breakdown

    def clean_stale_games(self, max_age_hours: int = 48):
        """Remove games that have passed or are too old."""
        now = datetime.utcnow()
        stale_ids = [
            game_id for game_id, game in self._games.items()
            if (now - game.tipoff).total_seconds() > max_age_hours * 3600
        ]
        for game_id in stale_ids:
            del self._games[game_id]
        
        if stale_ids:
            logger.info(
                "scheduler.cleaned_stale_games",
                count=len(stale_ids)
            )

    def get_next_fetch_times(self) -> dict[str, datetime]:
        """Get the next scheduled fetch times for all sources."""
        now = datetime.utcnow()
        next_times = {}
        
        for source in DataSource:
            for sport in Sport:
                cache_key = f"{source.value}:{sport.value}"
                last_fetch = self._cache.get(cache_key)
                interval = self.get_fetch_interval(sport)
                
                if last_fetch:
                    next_times[cache_key] = last_fetch + timedelta(seconds=interval)
                else:
                    next_times[cache_key] = now
        
        return next_times
