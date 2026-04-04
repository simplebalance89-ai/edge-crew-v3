"""
Peter Rules - Kills and Boosts
"""
import logging
from typing import Optional
from models import Game, PeterRulesResult, SportType, TeamProfile

logger = logging.getLogger(__name__)


class PeterRulesEngine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def apply(self, game: Game, side: str, profile: Optional[TeamProfile] = None,
              opp_profile: Optional[TeamProfile] = None) -> PeterRulesResult:
        kills = []
        boosts = []
        adjustment = 0.0
        kill_severity = 0
        boost_strength = 0
        
        if self._check_key_injury(profile):
            kills.append("KEY_INJURY")
            adjustment -= 2.0
            kill_severity = max(kill_severity, 5)
        
        if self._check_rest_disaster(profile, opp_profile):
            kills.append("REST_DISASTER")
            adjustment -= 1.5
            kill_severity = max(kill_severity, 4)
        
        if self._check_injury_cluster(profile):
            kills.append("INJURY_CLUSTER")
            adjustment -= 1.5
            kill_severity = max(kill_severity, 4)
        
        if self._check_weather_extreme(game):
            kills.append("WEATHER_EXTREME")
            adjustment -= 2.0
            kill_severity = max(kill_severity, 5)
        
        if self._check_late_line_move(game, side):
            kills.append("LATE_LINE_MOVE")
            adjustment -= 1.0
            kill_severity = max(kill_severity, 3)
        
        # Check boosts
        if self._check_revenge_boost(profile):
            boosts.append("REVENGE_GAME")
            adjustment += 1.0
            boost_strength = max(boost_strength, 4)
        
        if self._check_rest_boost(profile, opp_profile):
            boosts.append("REST_ADVANTAGE")
            adjustment += 0.8
            boost_strength = max(boost_strength, 3)
        
        if self._check_sharp_alignment(game, side):
            boosts.append("SHARP_ALIGNMENT")
            adjustment += 1.2
            boost_strength = max(boost_strength, 4)
        
        if self._check_matchup_dominance(profile, opp_profile):
            boosts.append("MATCHUP_DOMINANCE")
            adjustment += 1.0
            boost_strength = max(boost_strength, 3)
        
        explanation = self._build_explanation(kills, boosts, adjustment)
        
        return PeterRulesResult(
            adjustment=adjustment,
            kills=kills,
            boosts=boosts,
            kill_severity=kill_severity,
            boost_strength=boost_strength,
            explanation=explanation
        )
    
    def _check_key_injury(self, profile: Optional[TeamProfile]) -> bool:
        if not profile:
            return False
        key_injuries = getattr(profile, "key_injuries", [])
        return len([i for i in key_injuries if i.get("impact", 0) > 8]) > 0
    
    def _check_rest_disaster(self, profile: Optional[TeamProfile],
                             opp_profile: Optional[TeamProfile]) -> bool:
        if not profile or not opp_profile:
            return False
        return (profile.back_to_back and opp_profile.days_of_rest >= 3)
    
    def _check_injury_cluster(self, profile: Optional[TeamProfile]) -> bool:
        if not profile:
            return False
        injuries = getattr(profile, "injuries", [])
        return len([i for i in injuries if i.get("status") in ["out", "doubtful"]]) >= 3
    
    def _check_weather_extreme(self, game: Game) -> bool:
        if not game.weather:
            return False
        wind = game.weather.get("wind_speed", 0)
        temp = game.weather.get("temperature", 70)
        return wind > 25 or temp < 20 or temp > 100
    
    def _check_late_line_move(self, game: Game, side: str) -> bool:
        if not game.line_history:
            return False
        recent_moves = game.line_history[-3:]
        against_count = sum(1 for m in recent_moves if m.get("against_side") == side)
        return against_count >= 2
    
    def _check_revenge_boost(self, profile: Optional[TeamProfile]) -> bool:
        if not profile:
            return False
        return getattr(profile, "revenge_game_strength", 0) > 7
    
    def _check_rest_boost(self, profile: Optional[TeamProfile],
                          opp_profile: Optional[TeamProfile]) -> bool:
        if not profile or not opp_profile:
            return False
        return (profile.days_of_rest >= 3 and opp_profile.back_to_back)
    
    def _check_sharp_alignment(self, game: Game, side: str) -> bool:
        sharp_pct = getattr(game, "sharp_money_pct", 50)
        public_pct = getattr(game, "public_betting_pct", 50)
        return (sharp_pct > 60 and public_pct < 40 and side == "home") or \
               (sharp_pct < 40 and public_pct > 60 and side == "away")
    
    def _check_matchup_dominance(self, profile: Optional[TeamProfile],
                                 opp_profile: Optional[TeamProfile]) -> bool:
        if not profile or not opp_profile:
            return False
        history = getattr(profile, "matchup_history_wins", 0)
        total = getattr(profile, "matchup_history_games", 1)
        return total >= 3 and history / total >= 0.8
    
    def _build_explanation(self, kills: list, boosts: list, adjustment: float) -> str:
        parts = []
        if kills:
            parts.append(f"Kills: {', '.join(kills)}")
        if boosts:
            parts.append(f"Boosts: {', '.join(boosts)}")
        parts.append(f"Net adjustment: {adjustment:+.1f}")
        return "; ".join(parts)
