"""
ESPN ingester for fetching injury reports and live scores.

Uses ESPN's public API endpoints.
"""
import asyncio
from datetime import datetime
from typing import Optional

import structlog

from models import (
    BaseEvent,
    DataSource,
    EventType,
    GameInfo,
    GameStatus,
    InjuryEvent,
    InjuryStatus,
    Priority,
    ScoreEvent,
    Sport,
)
from ingesters.base import BaseIngester

logger = structlog.get_logger()


class ESPNIngester(BaseIngester):
    """Ingester for ESPN data (injuries, scores)."""
    
    source = DataSource.ESPN
    base_url = "https://site.api.espn.com/apis/site/v2/sports"
    rate_limit = 120  # requests per minute
    rate_limit_period = 60
    
    # Sport mapping to ESPN league slugs
    SPORT_MAP = {
        Sport.NBA: "basketball/nba",
        Sport.NCAAB: "basketball/mens-college-basketball",
        Sport.NFL: "football/nfl",
        Sport.NCAAF: "football/college-football",
        Sport.MLB: "baseball/mlb",
        Sport.NHL: "hockey/nhl",
        Sport.WNBA: "basketball/wnba",
        Sport.SOCCER: "soccer/usa.1",  # MLS
    }
    
    # ESPN team ID mappings (simplified - would be more complete in production)
    TEAM_ID_MAP: dict[Sport, dict[str, int]] = {
        Sport.NBA: {
            "LAL": 13, "GSW": 9, "BOS": 2, "BKN": 17, "NYK": 18,
            "PHI": 20, "TOR": 28, "CHI": 4, "CLE": 5, "DET": 8,
            "IND": 12, "MIL": 15, "ATL": 1, "CHA": 30, "MIA": 14,
            "ORL": 19, "WAS": 27, "DEN": 7, "MIN": 16, "OKC": 25,
            "POR": 22, "UTA": 26, "DAL": 6, "HOU": 10, "MEM": 29,
            "NOP": 3, "SAS": 24, "PHX": 21, "SAC": 23, "LAC": 12,
        }
    }
    
    def __init__(self, api_key: Optional[str] = None):
        # ESPN doesn't require API key for public endpoints
        super().__init__(None)
    
    def map_sport(self, sport: Sport) -> str:
        """Map internal sport to ESPN league slug."""
        return self.SPORT_MAP.get(sport, sport.value)
    
    async def fetch(
        self,
        sport: Sport,
        priority: Priority = Priority.MEDIUM
    ) -> list[BaseEvent]:
        """Fetch ESPN data for a sport (scores + injuries)."""
        # Fetch scores and injuries concurrently
        scores_task = self._fetch_scores(sport, priority)
        injuries_task = self._fetch_injuries(sport, priority)
        
        scores, injuries = await asyncio.gather(
            scores_task, injuries_task,
            return_exceptions=True
        )
        
        events = []
        
        if isinstance(scores, list):
            events.extend(scores)
        else:
            logger.error("espn.scores_fetch_failed", error=str(scores))
        
        if isinstance(injuries, list):
            events.extend(injuries)
        else:
            logger.error("espn.injuries_fetch_failed", error=str(injuries))
        
        logger.info(
            "espn.fetch_completed",
            sport=sport.value,
            event_count=len(events)
        )
        
        return events
    
    async def _fetch_scores(
        self,
        sport: Sport,
        priority: Priority
    ) -> list[ScoreEvent]:
        """Fetch live scores for a sport."""
        league = self.map_sport(sport)
        
        # Get today's scoreboard
        response = await self._request(
            "GET",
            f"/{league}/scoreboard"
        )
        
        data = response.json()
        events = []
        
        for game in data.get("events", []):
            event = self._parse_score_event(game, sport, priority)
            if event and not self._is_duplicate(event):
                events.append(event)
        
        return events
    
    def _parse_score_event(
        self,
        game: dict,
        sport: Sport,
        priority: Priority
    ) -> Optional[ScoreEvent]:
        """Parse a game into a ScoreEvent."""
        game_id = str(game.get("id", ""))
        status_data = game.get("status", {})
        status_type = status_data.get("type", {})
        
        # Determine game status
        state = status_type.get("state", "")
        status_map = {
            "pre": GameStatus.SCHEDULED,
            "in": GameStatus.LIVE,
            "post": GameStatus.FINAL,
        }
        status = status_map.get(state, GameStatus.SCHEDULED)
        
        # Get teams and scores
        competitions = game.get("competitions", [])
        if not competitions:
            return None
        
        comp = competitions[0]
        teams_data = comp.get("competitors", [])
        
        if len(teams_data) < 2:
            return None
        
        home_team_data = teams_data[0] if teams_data[0].get("homeAway") == "home" else teams_data[1]
        away_team_data = teams_data[1] if teams_data[0].get("homeAway") == "home" else teams_data[0]
        
        home_team = home_team_data.get("team", {}).get("abbreviation", "")
        away_team = away_team_data.get("team", {}).get("abbreviation", "")
        home_score = int(home_team_data.get("score", 0))
        away_score = int(away_team_data.get("score", 0))
        
        # Get period and time
        period = status_data.get("period", 0)
        clock = status_data.get("displayClock", "")
        
        # Generate dedup key based on score
        dedup_key = self._generate_dedup_key(
            game_id, str(home_score), str(away_score), str(period)
        )
        
        return ScoreEvent(
            source=self.source,
            sport=sport,
            priority=priority,
            dedup_key=dedup_key,
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            home_score=home_score,
            away_score=away_score,
            period=str(period),
            time_remaining=clock,
            status=status,
            raw_data=game
        )
    
    async def _fetch_injuries(
        self,
        sport: Sport,
        priority: Priority
    ) -> list[InjuryEvent]:
        """Fetch injury reports for a sport."""
        league = self.map_sport(sport)
        events = []
        
        # Get list of teams for this sport
        team_ids = self.TEAM_ID_MAP.get(sport, {})
        
        # Fetch injuries for each team concurrently
        tasks = [
            self._fetch_team_injuries(sport, team_id, team_abbr, priority)
            for team_abbr, team_id in team_ids.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                events.extend(result)
            elif isinstance(result, Exception):
                logger.error("espn.injury_fetch_failed", error=str(result))
        
        return events
    
    async def _fetch_team_injuries(
        self,
        sport: Sport,
        team_id: int,
        team_abbr: str,
        priority: Priority
    ) -> list[InjuryEvent]:
        """Fetch injuries for a specific team."""
        league = self.map_sport(sport)
        
        try:
            response = await self._request(
                "GET",
                f"/{league}/teams/{team_id}/injuries"
            )
            
            data = response.json()
            events = []
            
            for injury in data.get("injuries", []):
                event = self._parse_injury_event(
                    injury, sport, team_abbr, priority
                )
                if event and not self._is_duplicate(event):
                    events.append(event)
            
            return events
            
        except Exception as e:
            logger.error(
                "espn.team_injury_fetch_failed",
                team=team_abbr,
                error=str(e)
            )
            return []
    
    def _parse_injury_event(
        self,
        injury: dict,
        sport: Sport,
        team: str,
        priority: Priority
    ) -> Optional[InjuryEvent]:
        """Parse an injury report into an InjuryEvent."""
        athlete = injury.get("athlete", {})
        player_id = str(athlete.get("id", ""))
        player_name = athlete.get("displayName", "")
        
        status_data = injury.get("status", "")
        injury_type = injury.get("type", {}).get("description", "")
        
        # Map ESPN status to our status
        status_map = {
            "Active": InjuryStatus.HEALTHY,
            "Questionable": InjuryStatus.QUESTIONABLE,
            "Doubtful": InjuryStatus.DOUBTFUL,
            "Out": InjuryStatus.OUT,
            "Injured Reserve": InjuryStatus.INJURED_RESERVE,
        }
        status = status_map.get(status_data, InjuryStatus.HEALTHY)
        
        # Skip healthy players for injury reports
        if status == InjuryStatus.HEALTHY:
            return None
        
        # Generate dedup key
        dedup_key = self._generate_dedup_key(
            player_id, team, status.value, injury_type
        )
        
        return InjuryEvent(
            source=self.source,
            sport=sport,
            priority=priority,
            dedup_key=dedup_key,
            player_id=player_id,
            player_name=player_name,
            team=team,
            status=status,
            injury_type=injury_type,
            notes=injury.get("details", ""),
            raw_data=injury
        )
    
    async def get_games(self, sport: Sport) -> list[GameInfo]:
        """Get list of games for a sport."""
        league = self.map_sport(sport)
        
        response = await self._request(
            "GET",
            f"/{league}/scoreboard"
        )
        
        data = response.json()
        games = []
        
        for event in data.get("events", []):
            game_id = str(event.get("id", ""))
            
            # Get teams
            competitions = event.get("competitions", [])
            if not competitions:
                continue
            
            comp = competitions[0]
            teams_data = comp.get("competitors", [])
            
            if len(teams_data) < 2:
                continue
            
            home_team = teams_data[0].get("team", {}).get("abbreviation", "")
            away_team = teams_data[1].get("team", {}).get("abbreviation", "")
            
            # Parse date
            date_str = event.get("date", "")
            try:
                tipoff = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                tipoff = datetime.utcnow()
            
            games.append(GameInfo(
                game_id=game_id,
                sport=sport,
                home_team=home_team,
                away_team=away_team,
                tipoff=tipoff,
                status=GameStatus.SCHEDULED
            ))
        
        return games
