"""
Kalshi ingester for fetching event-based prediction markets.

Uses Kalshi API v2 for market data.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import structlog

from models import (
    BaseEvent,
    DataSource,
    EventType,
    GameInfo,
    MarketEvent,
    Priority,
    Sport,
)
from ingesters.base import BaseIngester

logger = structlog.get_logger()


class KalshiIngester(BaseIngester):
    """Ingester for Kalshi prediction markets."""
    
    source = DataSource.KALSHI
    base_url = "https://trading-api.kalshi.com/trade-api/v2"
    rate_limit = 100  # requests per minute
    rate_limit_period = 60
    
    # Kalshi uses different event series for sports
    SERIES_MAP = {
        Sport.NBA: "NBA",
        Sport.NCAAB: "CBB",
        Sport.NFL: "NFL",
        Sport.NCAAF: "CFB",
        Sport.MLB: "MLB",
        Sport.NHL: "NHL",
        Sport.WNBA: "WNBA",
    }
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key)
        self.api_secret = api_secret
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
    
    def map_sport(self, sport: Sport) -> str:
        """Map internal sport to Kalshi series."""
        return self.SERIES_MAP.get(sport, sport.value.upper())
    
    async def _ensure_authenticated(self):
        """Ensure we have a valid auth token."""
        now = datetime.utcnow()
        
        if self._token and self._token_expires and now < self._token_expires:
            return
        
        # Get new token using API key/secret
        import base64
        credentials = base64.b64encode(
            f"{self.api_key}:{self.api_secret}".encode()
        ).decode()
        
        response = await self._client.post(
            "/login",
            headers={"Authorization": f"Basic {credentials}"}
        )
        response.raise_for_status()
        
        data = response.json()
        self._token = data.get("token")
        # Tokens are valid for 24 hours
        self._token_expires = now + timedelta(hours=23)
        
        # Update client headers
        self._client.headers["Authorization"] = f"Bearer {self._token}"
    
    async def fetch(
        self,
        sport: Sport,
        priority: Priority = Priority.MEDIUM
    ) -> list[BaseEvent]:
        """Fetch Kalshi markets for a sport."""
        await self._ensure_authenticated()
        
        events = []
        
        try:
            # Get active markets for this sport
            markets = await self._fetch_markets(sport, priority)
            events.extend(markets)
            
            logger.info(
                "kalshi.fetch_completed",
                sport=sport.value,
                event_count=len(events)
            )
            
        except Exception as e:
            logger.error(
                "kalshi.fetch_failed",
                sport=sport.value,
                error=str(e)
            )
        
        return events
    
    async def _fetch_markets(
        self,
        sport: Sport,
        priority: Priority
    ) -> list[MarketEvent]:
        """Fetch active markets for a sport."""
        series = self.map_sport(sport)
        
        params = {
            "series_ticker": series,
            "status": "open",
            "limit": 100,
        }
        
        response = await self._request(
            "GET",
            "/events",
            params=params
        )
        
        data = response.json()
        events = []
        
        for event in data.get("events", []):
            event_id = event.get("event_ticker", "")
            
            # Get market data for this event
            market_events = await self._fetch_event_markets(
                event_id, sport, priority, event
            )
            events.extend(market_events)
        
        return events
    
    async def _fetch_event_markets(
        self,
        event_ticker: str,
        sport: Sport,
        priority: Priority,
        raw_event: dict
    ) -> list[MarketEvent]:
        """Fetch markets for a specific event."""
        response = await self._request(
            "GET",
            f"/events/{event_ticker}"
        )
        
        data = response.json()
        events = []
        
        event_data = data.get("event", raw_event)
        markets = event_data.get("markets", [])
        
        for market in markets:
            event = self._parse_market(
                market, event_data, sport, priority
            )
            if event and not self._is_duplicate(event):
                events.append(event)
        
        return events
    
    def _parse_market(
        self,
        market: dict,
        event: dict,
        sport: Sport,
        priority: Priority
    ) -> Optional[MarketEvent]:
        """Parse a Kalshi market into a MarketEvent."""
        market_id = market.get("ticker", "")
        title = market.get("title", event.get("title", ""))
        
        # Get yes/no prices
        yes_ask = market.get("yes_ask")
        yes_bid = market.get("yes_bid")
        no_ask = market.get("no_ask")
        no_bid = market.get("no_bid")
        
        if yes_ask is None or no_ask is None:
            return None
        
        # Use mid price
        yes_price = Decimal(str((yes_ask + yes_bid) / 2)) if yes_bid else Decimal(str(yes_ask))
        no_price = Decimal(str((no_ask + no_bid) / 2)) if no_bid else Decimal(str(no_ask))
        
        # Normalize to 0-1 scale (Kalshi uses 1-100 or 0.01-1.00)
        if yes_price > 1:
            yes_price = yes_price / 100
            no_price = no_price / 100
        
        volume = market.get("volume", 0)
        open_interest = market.get("open_interest", 0)
        
        # Parse close time
        close_time = None
        close_date = market.get("close_date") or event.get("close_date")
        close_time_str = market.get("close_time") or event.get("close_time")
        if close_date and close_time_str:
            try:
                close_time = datetime.fromisoformat(
                    f"{close_date}T{close_time_str}".replace("Z", "+00:00")
                )
            except ValueError:
                pass
        
        # Try to extract related game ID from title
        related_game_id = self._extract_game_id(title, sport)
        
        # Generate dedup key
        dedup_key = self._generate_dedup_key(
            market_id, str(yes_price), str(no_price), str(volume)
        )
        
        return MarketEvent(
            source=self.source,
            sport=sport,
            priority=priority,
            dedup_key=dedup_key,
            market_id=market_id,
            market_title=title,
            yes_price=yes_price,
            no_price=no_price,
            volume=volume,
            open_interest=open_interest,
            close_time=close_time,
            related_game_id=related_game_id,
            raw_data={"market": market, "event": event}
        )
    
    def _extract_game_id(self, title: str, sport: Sport) -> Optional[str]:
        """Try to extract a game ID from market title."""
        # This would use team name matching to associate Kalshi markets
        # with our game database
        # Simplified implementation - would need team name normalization
        return None
    
    async def get_games(self, sport: Sport) -> list[GameInfo]:
        """
        Get game-like events from Kalshi markets.
        Note: Kalshi doesn't have traditional games, but we can infer
        them from market titles.
        """
        series = self.map_sport(sport)
        
        params = {
            "series_ticker": series,
            "status": "open",
            "limit": 100,
        }
        
        response = await self._request("GET", "/events", params=params)
        data = response.json()
        
        games = []
        for event in data.get("events", []):
            # Parse event to extract game-like info
            # This is heuristic-based
            game = self._event_to_game_info(event, sport)
            if game:
                games.append(game)
        
        return games
    
    def _event_to_game_info(
        self,
        event: dict,
        sport: Sport
    ) -> Optional[GameInfo]:
        """Convert a Kalshi event to GameInfo."""
        event_id = event.get("event_ticker", "")
        title = event.get("title", "")
        
        # Parse close time as tipoff proxy
        close_date = event.get("close_date", "")
        close_time = event.get("close_time", "")
        
        if close_date and close_time:
            try:
                tipoff = datetime.fromisoformat(
                    f"{close_date}T{close_time}".replace("Z", "+00:00")
                )
            except ValueError:
                tipoff = datetime.utcnow()
        else:
            tipoff = datetime.utcnow()
        
        # Try to extract teams from title
        # This is sport-specific parsing
        teams = self._extract_teams_from_title(title, sport)
        
        return GameInfo(
            game_id=event_id,
            sport=sport,
            home_team=teams.get("home", ""),
            away_team=teams.get("away", ""),
            tipoff=tipoff,
            status=event.get("status", "open")
        )
    
    def _extract_teams_from_title(
        self,
        title: str,
        sport: Sport
    ) -> dict[str, str]:
        """Extract team names from Kalshi market title."""
        # This would need comprehensive team name matching
        # Simplified implementation
        teams = {"home": "", "away": ""}
        
        # Look for "Team A vs Team B" or "Team A @ Team B" patterns
        import re
        
        vs_match = re.search(r'(.+?)\s+(?:vs\.?|@|at)\s+(.+?)(?:\s*[\|:]|$)', title, re.IGNORECASE)
        if vs_match:
            teams["away"] = vs_match.group(1).strip()
            teams["home"] = vs_match.group(2).strip()
        
        return teams
    
    async def get_market_orderbook(
        self,
        market_ticker: str
    ) -> dict:
        """Get orderbook for a specific market."""
        await self._ensure_authenticated()
        
        response = await self._request(
            "GET",
            f"/markets/{market_ticker}/orderbook"
        )
        
        return response.json()
    
    async def subscribe_to_websocket(self, sports: list[Sport]):
        """
        Subscribe to Kalshi WebSocket for real-time updates.
        This is a placeholder - full implementation would use
        websockets library for persistent connection.
        """
        import websockets
        
        ws_url = "wss://trading-api.kalshi.com/trade-api/ws/v2"
        
        # Connect and subscribe to market updates
        # Full implementation would handle reconnection, heartbeat, etc.
        logger.info(
            "kalshi.websocket_subscribe",
            sports=[s.value for s in sports]
        )
        
        # Placeholder - would return websocket connection object
        return None
