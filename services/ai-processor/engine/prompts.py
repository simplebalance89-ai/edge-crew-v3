"""
Sport-specific prompt templates for AI grading.
"""
from typing import Dict, Optional, List
from datetime import datetime

from models import Pick, SportType, Game, Team, PickType


class SportPrompts:
    """Prompt templates for each sport."""
    
    NFL_SYSTEM = """You are an expert NFL betting analyst with deep knowledge of:
- Team statistics and advanced metrics (DVOA, EPA, success rate)
- Player matchups and injury impacts
- Weather and venue effects
- Coaching tendencies and game scripts
- Historical ATS trends

Grade picks on a scale of 0-100 with detailed reasoning. Return JSON format:
{
    "score": 85,
    "confidence": 0.82,
    "reasoning": "Detailed analysis...",
    "key_factors": ["factor1", "factor2"],
    "red_flags": ["flag1"]
}"""
    
    NBA_SYSTEM = """You are an expert NBA betting analyst specializing in:
- Advanced metrics (OFF/DEF RTG, pace, true shooting%)
- Rest advantages and schedule spots
- Matchup-specific advantages
- Player workload and injury management
- Home court and travel effects

Grade picks on a scale of 0-100 with detailed reasoning. Return JSON format:
{
    "score": 78,
    "confidence": 0.75,
    "reasoning": "Detailed analysis...",
    "key_factors": ["factor1", "factor2"],
    "red_flags": []
}"""
    
    NCAAB_SYSTEM = """You are an expert college basketball betting analyst focusing on:
- KenPom and other advanced ratings
- Home court advantages in college
- Tournament vs regular season dynamics
- Coaching philosophies and adjustments
- Player development and rotations

Grade picks on a scale of 0-100 with detailed reasoning. Return JSON format:
{
    "score": 72,
    "confidence": 0.68,
    "reasoning": "Detailed analysis...",
    "key_factors": ["factor1", "factor2"],
    "red_flags": []
}"""
    
    MLB_SYSTEM = """You are an expert MLB betting analyst with expertise in:
- Starting pitcher analysis and recent form
- Bullpen strength and usage patterns
- Platoon advantages and splits
- Park factors and weather
- Umpire tendencies and strike zones

Grade picks on a scale of 0-100 with detailed reasoning. Return JSON format:
{
    "score": 80,
    "confidence": 0.78,
    "reasoning": "Detailed analysis...",
    "key_factors": ["factor1", "factor2"],
    "red_flags": []
}"""
    
    NHL_SYSTEM = """You are an expert NHL betting analyst specializing in:
- Goaltender matchups and recent performance
- Advanced stats (Corsi, xG, high-danger chances)
- Special teams and power play efficiency
- Back-to-back and rest advantages
- Line matching and coaching strategies

Grade picks on a scale of 0-100 with detailed reasoning. Return JSON format:
{
    "score": 76,
    "confidence": 0.72,
    "reasoning": "Detailed analysis...",
    "key_factors": ["factor1", "factor2"],
    "red_flags": []
}"""
    
    SOCCER_SYSTEM = """You are an expert soccer betting analyst with knowledge of:
- League-specific styles and tactics
- Form and momentum analysis
- Key injuries and suspensions
- European/International fixture congestion
- Referee tendencies and card patterns

Grade picks on a scale of 0-100 with detailed reasoning. Return JSON format:
{
    "score": 82,
    "confidence": 0.80,
    "reasoning": "Detailed analysis...",
    "key_factors": ["factor1", "factor2"],
    "red_flags": []
}"""
    
    UFC_SYSTEM = """You are an expert UFC/MMA betting analyst specializing in:
- Fighter styles and matchup analysis
- Recent fight history and damage taken
- Weight class dynamics and cuts
- Training camp quality and changes
- Judging tendencies and fight location

Grade picks on a scale of 0-100 with detailed reasoning. Return JSON format:
{
    "score": 88,
    "confidence": 0.85,
    "reasoning": "Detailed analysis...",
    "key_factors": ["factor1", "factor2"],
    "red_flags": []
}"""
    
    DEFAULT_SYSTEM = """You are an expert sports betting analyst. Grade this pick on a scale of 0-100 with detailed reasoning. Return JSON format:
{
    "score": 75,
    "confidence": 0.70,
    "reasoning": "Detailed analysis...",
    "key_factors": ["factor1", "factor2"],
    "red_flags": []
}"""


SYSTEM_PROMPTS = {
    SportType.NFL: SportPrompts.NFL_SYSTEM,
    SportType.NBA: SportPrompts.NBA_SYSTEM,
    SportType.NCAAB: SportPrompts.NCAAB_SYSTEM,
    SportType.NCAAF: SportPrompts.NFL_SYSTEM,
    SportType.MLB: SportPrompts.MLB_SYSTEM,
    SportType.NHL: SportPrompts.NHL_SYSTEM,
    SportType.SOCCER: SportPrompts.SOCCER_SYSTEM,
    SportType.UFC: SportPrompts.UFC_SYSTEM,
}


class PromptManager:
    """Manages prompt construction for different sports and pick types."""
    
    def __init__(self):
        self.system_prompts = SYSTEM_PROMPTS
    
    def get_system_prompt(self, sport: SportType) -> str:
        return self.system_prompts.get(sport, SportPrompts.DEFAULT_SYSTEM)
    
    def build_grading_prompt(self, pick: Pick) -> str:
        game = pick.game
        sections = [
            self._build_game_info(game),
            self._build_pick_info(pick),
            self._build_team_info(game),
            self._build_context(game),
            self._build_grading_request(pick),
        ]
        return '\n\n'.join(sections)
    
    def _build_game_info(self, game: Game) -> str:
        lines = [
            "=== GAME INFORMATION ===",
            f"Sport: {game.sport.value.upper()}",
            f"Matchup: {game.away_team.name} @ {game.home_team.name}",
            f"Game Time: {game.game_time.strftime('%Y-%m-%d %H:%M UTC')}",
            f"Venue: {game.venue or 'TBD'}",
        ]
        if game.is_playoffs:
            lines.append("Context: PLAYOFF GAME")
        if game.is_primetime:
            lines.append("Context: PRIMETIME GAME")
        if game.rivalry_game:
            lines.append("Context: RIVALRY GAME")
        return '\n'.join(lines)
    
    def _build_pick_info(self, pick: Pick) -> str:
        lines = [
            "=== PICK TO GRADE ===",
            f"Type: {pick.pick_type.value}",
            f"Selection: {pick.selection}",
        ]
        if pick.odds:
            lines.append(f"Odds: {pick.odds:+d}")
        if pick.analyst:
            lines.append(f"Analyst: {pick.analyst}")
        if pick.notes:
            lines.append(f"Notes: {pick.notes}")
        return '\n'.join(lines)
    
    def _build_team_info(self, game: Game) -> str:
        lines = ["=== TEAM INFORMATION ==="]
        for team, location in [(game.home_team, "HOME"), (game.away_team, "AWAY")]:
            lines.append(f"\n{location}: {team.name} ({team.abbreviation})")
            if team.record:
                lines.append(f"  Record: {team.record}")
            if team.rank:
                lines.append(f"  Rank: #{team.rank}")
            if team.injuries:
                lines.append(f"  Injuries: {len(team.injuries)} players")
            if team.last_games:
                lines.append(f"  Last 5: {', '.join([g.get('result', '?') for g in team.last_games[-5:]])}")
        return '\n'.join(lines)
    
    def _build_context(self, game: Game) -> str:
        lines = ["=== ADDITIONAL CONTEXT ==="]
        if game.spread:
            lines.append(f"Market Spread: {game.spread:+.1f}")
        if game.total:
            lines.append(f"Market Total: {game.total}")
        if game.home_moneyline:
            lines.append(f"Home ML: {game.home_moneyline:+d}")
        if game.away_moneyline:
            lines.append(f"Away ML: {game.away_moneyline:+d}")
        if game.weather:
            lines.append(f"Weather: {game.weather.get('condition', 'N/A')}, {game.weather.get('temp', 'N/A')}F")
        if game.context:
            for key, value in game.context.items():
                lines.append(f"{key}: {value}")
        return '\n'.join(lines)
    
    def _build_grading_request(self, pick: Pick) -> str:
        return """=== GRADING INSTRUCTIONS ===
Grade this pick on a scale of 0-100 where:
- 95-100 (A+): Exceptional value, highly confident
- 90-94 (A): Strong pick with solid edge
- 85-89 (A-): Good pick, above average confidence
- 80-84 (B+): Above average, some concerns
- 75-79 (B): Average play, fair value
- 70-74 (B-): Below average, minor edge
- 60-69 (C): Weak pick, minimal edge
- Below 60 (D/F): Poor pick, avoid

Consider: statistical edge, injury impact, matchup advantages, situational spots, market movement, and any red flags.

Return your analysis in the specified JSON format."""
