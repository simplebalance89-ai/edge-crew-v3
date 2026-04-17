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
import sys
import os
import time

# Add parent directory to path for error_handler import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.error_handler import task_manager, retry_with_backoff, ErrorCategory, classify_error
from app.core.config import security_settings

from models import (
    DataSource,
    GameInfo,
    GameStatus,
    Priority,
    Sport,
)

logger = structlog.get_logger()


class SchedulerConfig:
    """Configuration for SmartScheduler loaded from environment"""
    
    def __init__(self):
        import os
        # Priority score thresholds
        self.critical_threshold = int(os.getenv("SCHEDULER_CRITICAL_THRESHOLD", "15"))
        self.high_threshold = int(os.getenv("SCHEDULER_HIGH_THRESHOLD", "8"))
        
        # Base intervals per priority (seconds)
        self.fetch_intervals = {
            Priority.CRITICAL: int(os.getenv("SCHEDULER_CRITICAL_INTERVAL", "30")),
            Priority.HIGH: int(os.getenv("SCHEDULER_HIGH_INTERVAL", "120")),
            Priority.MEDIUM: int(os.getenv("SCHEDULER_MEDIUM_INTERVAL", "300")),
            Priority.LOW: int(os.getenv("SCHEDULER_LOW_INTERVAL", "900")),
        }
        
        # Dedup window (seconds)
        self.dedup_window = int(os.getenv("SCHEDULER_DEDUP_WINDOW", "60"))
        
        # Max age for stale game cleanup (hours)
        self.max_age_hours = int(os.getenv("SCHEDULER_MAX_AGE_HOURS", "48"))
        
        # Scheduling loop interval (seconds)
        self.loop_interval = int(os.getenv("SCHEDULER_LOOP_INTERVAL", "10"))
        
        # Error retry interval (seconds)
        self.error_retry_interval = int(os.getenv("SCHEDULER_ERROR_RETRY", "30"))


class SmartScheduler:
    """
    Intelligent scheduling system that prioritizes data fetching
    based on game proximity and betting significance.
    """

    def __init__(self, config: SchedulerConfig = None):
        self.config = config or SchedulerConfig()
        self._games: dict[str, GameInfo] = {}
        self._schedules: dict[DataSource, asyncio.Task] = {}
        self._callbacks: dict[DataSource, list[Callable]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._running = False
        self._cache: dict[str, datetime] = {}

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
        if score >= self.config.critical_threshold:
            return Priority.CRITICAL
        elif score >= self.config.high_threshold:
            return Priority.HIGH
        elif score > 0:
            return Priority.MEDIUM
        else:
            return Priority.LOW

    def get_fetch_interval(self, sport: Sport) -> int:
        """Get the appropriate fetch interval for a sport."""
        priority = self.get_fetch_priority(sport)
        return self.config.fetch_intervals[priority]

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
                await asyncio.sleep(self.config.loop_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("scheduler.loop_error", error=str(e))
                await asyncio.sleep(self.config.error_retry_interval)

    async def _execute_scheduled_fetches(self):
        """Execute scheduled fetches for all sources with managed tasks."""
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
                    
                    # Execute all callbacks for this source using managed tasks
                    for callback in callbacks:
                        try:
                            task_id = f"fetch_{source.value}_{sport.value}_{int(time.time() * 1000)}"
                            
                            # Wrap callback with retry logic
                            @retry_with_backoff(max_retries=3, base_delay=1.0)
                            async def wrapped_callback(sport_val, priority_val):
                                return await callback(sport_val, priority_val)
                            
                            # Create managed task with resource limits
                            await task_manager.create_managed_task(
                                wrapped_callback,
                                task_id,
                                sport,
                                priority
                            )
                            
                            logger.debug(
                                "scheduler.created_managed_task",
                                task_id=task_id,
                                source=source.value,
                                sport=sport.value
                            )
                            
                        except Exception as e:
                            error_category = classify_error(e)
                            logger.error(
                                "scheduler.callback_error",
                                source=source.value,
                                error_category=error_category.value,
                                error=str(e),
                                active_tasks=task_manager.active_task_count
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
                
            if score >= self.config.critical_threshold:
                breakdown["critical_games"] += 1
            elif score >= self.config.high_threshold:
                breakdown["high_priority_games"] += 1
        
        return breakdown

    def clean_stale_games(self, max_age_hours: int = None):
        if max_age_hours is None:
            max_age_hours = self.config.max_age_hours
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
