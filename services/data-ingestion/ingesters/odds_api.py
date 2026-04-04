"""
The Odds API ingester for fetching odds data.

Docs: https://the-odds-api.com/
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import structlog

from models import (
    BaseEvent,
    DataSource,
    EventType,
    OddsEvent,
    GameInfo,
    GameStatus,
    PlayerPropEvent,
    Priority,
    Sport,
)
from ingesters.base import BaseIngester

logger = structlog.get_logger()


class OddsAPIIngester(BaseIngester):
    """Ingester for The Odds API."""
    
    source = DataSource.ODDS_API
    base_url = "https://api.the-odds-api.com/v4"
    rate_limit = 50  # requests per minute for free tier
    rate_limit_period = 60
    
    # Sport mapping to Odds API format
    SPORT_MAP = {
        Sport.NBA: "basketball_nba",
        Sport.NCAAB: "basketball_ncaab",
        Sport.NFL: "americanfootball_nfl",
        Sport.NCAAF: "americanfootball_ncaaf",
        Sport.MLB: "baseball_mlb",
        Sport.NHL: "icehockey_nhl",
        Sport.WNBA: "basketball_wnba",
        Sport.SOCCER: "soccer_usa_mls",
    }
    
    MARKET_TYPES = ["h2h", "spreads", "totals", "player_props"]
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._regions = "us"
        self._odds_format = "decimal"
        self._date_format = "iso"
    
    def map_sport(self, sport: Sport) -> str:
        """Map internal sport to Odds API format."""
        return self.SPORT_MAP.get(sport, sport.value)
    
    async def fetch(
        self,
        sport: Sport,
        priority: Priority = Priority.MEDIUM
    ) -> list[BaseEvent]:
        """Fetch odds data for a sport."""
        events = []
        
        # Fetch odds for each market type
        for market in self.MARKET_TYPES:
            try:
                market_events = await self._fetch_market(sport, market, priority)
                events.extend(market_events)
            except Exception as e:
                logger.error(
                    "odds_api.market_fetch_failed",
                    sport=sport.value,
                    market=market,
                    error=str(e)
                )
        
        logger.info(
            "odds_api.fetch_completed",
            sport=sport.value,
            event_count=len(events)
        )
        
        return events
    
    async def _fetch_market(
        self,
        sport: Sport,
        market: str,
        priority: Priority
    ) -> list[BaseEvent]:
        """Fetch specific market type."""
        sport_key = self.map_sport(sport)
        
        params = {
            "apiKey": self.api_key,
            "regions": self._regions,
            "markets": market,
            "oddsFormat": self._odds_format,
            "dateFormat": self._date_format,
        }
        
        response = await self._request(
            "GET",
            f"/sports/{sport_key}/odds",
            params=params
        )
        
        data = response.json()
        events = self._parse_odds(data, sport, market, priority)
        
        return events
    
    def _parse_odds(
        self,
        data: list[dict],
        sport: Sport,
        market: str,
        priority: Priority
    ) -> list[BaseEvent]:
        """Parse odds response into events."""
        events = []
        
        for game in data:
            game_id = game.get("id", "")
            home_team = game.get("home_team", "")
            away_team = game.get("away_team", "")
            commence_time = game.get("commence_time", "")
            
            # Parse bookmakers
            for bookmaker in game.get("bookmakers", []):
                bookmaker_key = bookmaker.get("key", "")
                
                for market_data in bookmaker.get("markets", []):
                    market_key = market_data.get("key", "")
                    
                    if market_key == "player_props":
                        # Handle player props separately
                        prop_events = self._parse_player_props(
                            market_data, game_id, sport, home_team,
                            away_team, bookmaker_key, priority
                        )
                        events.extend(prop_events)
                    else:
                        # Handle standard markets
                        for outcome in market_data.get("outcomes", []):
                            event = self._create_odds_event(
                                game_id=game_id,
                                sport=sport,
                                home_team=home_team,
                                away_team=away_team,
                                market_type=market_key,
                                bookmaker=bookmaker_key,
                                outcome=outcome,
                                commence_time=commence_time,
                                priority=priority,
                                raw_game=game
                            )
                            
                            if event and not self._is_duplicate(event):
                                events.append(event)
        
        return events
    
    def _create_odds_event(
        self,
        game_id: str,
        sport: Sport,
        home_team: str,
        away_team: str,
        market_type: str,
        bookmaker: str,
        outcome: dict,
        commence_time: str,
        priority: Priority,
        raw_game: dict
    ) -> Optional[OddsEvent]:
        """Create an OddsEvent from parsed data."""
        outcome_name = outcome.get("name", "")
        price = outcome.get("price")
        point = outcome.get("point")
        
        if price is None:
            return None
        
        # Generate dedup key
        dedup_key = self._generate_dedup_key(
            game_id, market_type, bookmaker, outcome_name
        )
        
        event = OddsEvent(
            source=self.source,
            sport=sport,
            priority=priority,
            dedup_key=dedup_key,
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            market_type=market_type,
            bookmaker=bookmaker,
            line=Decimal(str(point)) if point is not None else None,
            price=Decimal(str(price)),
            raw_data=raw_game
        )
        
        return event
    
    def _parse_player_props(
        self,
        market_data: dict,
        game_id: str,
        sport: Sport,
        home_team: str,
        away_team: str,
        bookmaker: str,
        priority: Priority
    ) -> list[PlayerPropEvent]:
        """Parse player prop markets."""
        events = []
        
        # Player props are structured differently
        for outcome in market_data.get("outcomes", []):
            # Parse player name from description
            description = outcome.get("description", "")
            name = outcome.get("name", "")
            
            # Determine over/under and stat type from description
            stat_type = self._extract_stat_type(description)
            is_over = "over" in name.lower() or "o" in name.lower()
            
            point = outcome.get("point")
            price = outcome.get("price")
            
            if point is None or price is None:
                continue
            
            dedup_key = self._generate_dedup_key(
                game_id, description, bookmaker, name
            )
            
            event = PlayerPropEvent(
                source=self.source,
                sport=sport,
                priority=priority,
                dedup_key=dedup_key,
                game_id=game_id,
                player_id="",  # Would need to map name to ID
                player_name=description,
                team=home_team if is_over else away_team,  # Simplified
                stat_type=stat_type,
                line=Decimal(str(point)),
                over_price=Decimal(str(price)) if is_over else Decimal("0"),
                under_price=Decimal(str(price)) if not is_over else Decimal("0"),
                bookmaker=bookmaker
            )
            
            if not self._is_duplicate(event):
                events.append(event)
        
        return events
    
    def _extract_stat_type(self, description: str) -> str:
        """Extract stat type from player prop description."""
        desc_lower = description.lower()
        
        if "points" in desc_lower or "pts" in desc_lower:
            return "points"
        elif "rebounds" in desc_lower or "reb" in desc_lower:
            return "rebounds"
        elif "assists" in desc_lower or "ast" in desc_lower:
            return "assists"
        elif "threes" in desc_lower or "3-pt" in desc_lower:
            return "threes"
        elif "steals" in desc_lower:
            return "steals"
        elif "blocks" in desc_lower:
            return "blocks"
        else:
            return "unknown"
    
    async def get_games(self, sport: Sport) -> list[GameInfo]:
        """Get list of games for a sport."""
        sport_key = self.map_sport(sport)
        
        params = {
            "apiKey": self.api_key,
        }
        
        response = await self._request(
            "GET",
            f"/sports/{sport_key}/scores",
            params=params
        )
        
        data = response.json()
        games = []
        
        for game in data:
            tipoff = datetime.fromisoformat(
                game.get("commence_time", "").replace("Z", "+00:00")
            )
            
            games.append(GameInfo(
                game_id=game.get("id", ""),
                sport=sport,
                home_team=game.get("home_team", ""),
                away_team=game.get("away_team", ""),
                tipoff=tipoff,
                status=GameStatus.SCHEDULED
            ))
        
        return games
    
    async def get_usage(self) -> dict[str, Any]:
        """Get API usage information."""
        # Usage info is in response headers
        response = await self._request("GET", "/sports")
        headers = response.headers
        
        return {
            "requests_remaining": headers.get("x-requests-remaining"),
            "requests_used": headers.get("x-requests-used"),
            "requests_last": headers.get("x-requests-last"),
        }
