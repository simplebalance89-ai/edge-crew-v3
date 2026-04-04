"""
Rotowire ingester for fetching projected lineups and minutes.

Uses Rotowire API for lineup projections.
"""
from datetime import datetime, timedelta
from typing import Optional

import structlog

from models import (
    BaseEvent,
    DataSource,
    EventType,
    GameInfo,
    GameStatus,
    LineupEvent,
    Priority,
    Sport,
)
from ingesters.base import BaseIngester

logger = structlog.get_logger()


class RotowireIngester(BaseIngester):
    """Ingester for Rotowire lineup projections."""
    
    source = DataSource.ROTOWIRE
    base_url = "https://www.rotowire.com/graphql"
    rate_limit = 30  # requests per minute (be conservative)
    rate_limit_period = 60
    
    # Rotowire uses different sport identifiers
    SPORT_MAP = {
        Sport.NBA: "nba",
        Sport.NCAAB: "cbb",
        Sport.NFL: "nfl",
        Sport.NCAAF: "cfb",
        Sport.MLB: "mlb",
        Sport.NHL: "nhl",
        Sport.WNBA: "wnba",
    }
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
    
    def map_sport(self, sport: Sport) -> str:
        """Map internal sport to Rotowire format."""
        return self.SPORT_MAP.get(sport, sport.value)
    
    def _get_default_headers(self) -> dict[str, str]:
        """Get default headers with auth."""
        headers = super()._get_default_headers()
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers["Content-Type"] = "application/json"
        return headers
    
    async def fetch(
        self,
        sport: Sport,
        priority: Priority = Priority.MEDIUM
    ) -> list[BaseEvent]:
        """Fetch lineup projections for a sport."""
        if sport not in [Sport.NBA, Sport.NCAAB, Sport.NFL, Sport.NHL]:
            logger.debug(
                "rotowire.sport_not_supported",
                sport=sport.value
            )
            return []
        
        sport_key = self.map_sport(sport)
        
        # Fetch lineups
        try:
            lineups = await self._fetch_lineups(sport_key, sport, priority)
            logger.info(
                "rotowire.fetch_completed",
                sport=sport.value,
                event_count=len(lineups)
            )
            return lineups
        except Exception as e:
            logger.error(
                "rotowire.fetch_failed",
                sport=sport.value,
                error=str(e)
            )
            return []
    
    async def _fetch_lineups(
        self,
        sport_key: str,
        sport: Sport,
        priority: Priority
    ) -> list[LineupEvent]:
        """Fetch lineup data from Rotowire."""
        # GraphQL query for lineups
        query = """
        query LineupsQuery($sport: String!, $date: String) {
            lineups(sport: $sport, date: $date) {
                gameId
                homeTeam
                awayTeam
                startTime
                homePlayers {
                    playerId
                    name
                    position
                    isStarting
                    projectedMinutes
                    team
                }
                awayPlayers {
                    playerId
                    name
                    position
                    isStarting
                    projectedMinutes
                    team
                }
            }
        }
        """
        
        today = datetime.utcnow().strftime("%Y-%m-%d")
        
        variables = {
            "sport": sport_key,
            "date": today
        }
        
        response = await self._request(
            "POST",
            "",
            json={
                "query": query,
                "variables": variables
            }
        )
        
        data = response.json()
        events = []
        
        for game in data.get("data", {}).get("lineups", []):
            game_id = str(game.get("gameId", ""))
            home_team = game.get("homeTeam", "")
            away_team = game.get("awayTeam", "")
            
            # Process home players
            for player in game.get("homePlayers", []):
                event = self._parse_player_lineup(
                    player, game_id, sport, home_team, priority
                )
                if event and not self._is_duplicate(event):
                    events.append(event)
            
            # Process away players
            for player in game.get("awayPlayers", []):
                event = self._parse_player_lineup(
                    player, game_id, sport, away_team, priority
                )
                if event and not self._is_duplicate(event):
                    events.append(event)
        
        return events
    
    def _parse_player_lineup(
        self,
        player: dict,
        game_id: str,
        sport: Sport,
        team: str,
        priority: Priority
    ) -> Optional[LineupEvent]:
        """Parse a player into a LineupEvent."""
        player_id = str(player.get("playerId", ""))
        player_name = player.get("name", "")
        position = player.get("position", "")
        is_starting = player.get("isStarting", False)
        minutes = player.get("projectedMinutes")
        
        # Generate dedup key
        dedup_key = self._generate_dedup_key(
            game_id, player_id, str(is_starting), str(minutes)
        )
        
        return LineupEvent(
            source=self.source,
            sport=sport,
            priority=priority,
            dedup_key=dedup_key,
            game_id=game_id,
            team=team,
            player_id=player_id,
            player_name=player_name,
            is_starting=is_starting,
            position=position,
            minutes_projection=minutes,
            raw_data=player
        )
    
    async def get_games(self, sport: Sport) -> list[GameInfo]:
        """Get list of games with lineup information."""
        if sport not in [Sport.NBA, Sport.NCAAB, Sport.NFL, Sport.NHL]:
            return []
        
        sport_key = self.map_sport(sport)
        
        query = """
        query GamesQuery($sport: String!, $date: String) {
            games(sport: $sport, date: $date) {
                gameId
                homeTeam
                awayTeam
                startTime
                status
            }
        }
        """
        
        today = datetime.utcnow().strftime("%Y-%m-%d")
        
        variables = {
            "sport": sport_key,
            "date": today
        }
        
        response = await self._request(
            "POST",
            "",
            json={
                "query": query,
                "variables": variables
            }
        )
        
        data = response.json()
        games = []
        
        for game in data.get("data", {}).get("games", []):
            game_id = str(game.get("gameId", ""))
            home_team = game.get("homeTeam", "")
            away_team = game.get("awayTeam", "")
            start_time = game.get("startTime", "")
            status = game.get("status", "scheduled")
            
            try:
                tipoff = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            except ValueError:
                tipoff = datetime.utcnow()
            
            status_map = {
                "scheduled": GameStatus.SCHEDULED,
                "live": GameStatus.LIVE,
                "final": GameStatus.FINAL,
                "postponed": GameStatus.POSTPONED,
            }
            
            games.append(GameInfo(
                game_id=game_id,
                sport=sport,
                home_team=home_team,
                away_team=away_team,
                tipoff=tipoff,
                status=status_map.get(status, GameStatus.SCHEDULED)
            ))
        
        return games
    
    async def fetch_player_news(
        self,
        sport: Sport,
        player_ids: Optional[list[str]] = None
    ) -> list[dict]:
        """Fetch player news updates."""
        sport_key = self.map_sport(sport)
        
        query = """
        query PlayerNewsQuery($sport: String!, $playerIds: [String]) {
            playerNews(sport: $sport, playerIds: $playerIds) {
                playerId
                playerName
                team
                newsType
                headline
                description
                timestamp
                source
            }
        }
        """
        
        variables = {
            "sport": sport_key,
            "playerIds": player_ids
        }
        
        response = await self._request(
            "POST",
            "",
            json={
                "query": query,
                "variables": variables
            }
        )
        
        data = response.json()
        return data.get("data", {}).get("playerNews", [])
