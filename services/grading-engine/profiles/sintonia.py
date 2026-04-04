"""
Sintonia Profile - 20-Variable Matrix Scoring

Deterministic scoring based on 20 weighted variables
across offense, defense, situational, and matchup factors.
"""

import logging
from typing import Any, Dict, List, Tuple

from models import (
    Game,
    Grade,
    SintoniaScore,
    SportType,
    TeamProfile,
)

logger = logging.getLogger(__name__)


class SintoniaScorer:
    """
    Sintonia 20-Variable Matrix Scoring Engine.
    
    Scores team profiles against opponent profiles using
    a weighted matrix of 20 core variables.
    """
    
    # Variable weights by sport type
    WEIGHTS = {
        SportType.NBA: {
            # Core offensive/defensive (40%)
            "offensive_rating": 0.12,
            "defensive_rating": 0.12,
            "efficiency_rating": 0.10,
            "pace_rating": 0.06,
            # Shooting metrics (20%)
            "shooting_efficiency": 0.08,
            "three_point_efficiency": 0.06,
            "free_throw_efficiency": 0.04,
            "turnover_rate": 0.02,
            # Rebounding/playmaking (15%)
            "rebounding_efficiency": 0.08,
            "assist_to_turnover_ratio": 0.07,
            # Situational (25%)
            "recent_form_rating": 0.08,
            "home_away_split": 0.06,
            "rest_advantage": 0.04,
            "schedule_strength": 0.04,
            "matchup_history": 0.03,
            # Context (15%)
            "injuries_impact": 0.05,
            "clutch_performance": 0.05,
            "days_of_rest": 0.03,
            "back_to_back": -0.02,  # Penalty
        },
        SportType.NCAAB: {
            "offensive_rating": 0.10,
            "defensive_rating": 0.10,
            "efficiency_rating": 0.10,
            "pace_rating": 0.05,
            "shooting_efficiency": 0.08,
            "three_point_efficiency": 0.05,
            "free_throw_efficiency": 0.04,
            "turnover_rate": 0.03,
            "rebounding_efficiency": 0.08,
            "assist_to_turnover_ratio": 0.07,
            "recent_form_rating": 0.08,
            "home_away_split": 0.08,  # More important in college
            "rest_advantage": 0.03,
            "schedule_strength": 0.05,
            "matchup_history": 0.02,
            "injuries_impact": 0.05,
            "clutch_performance": 0.04,
            "days_of_rest": 0.02,
            "back_to_back": -0.03,
        },
        SportType.NHL: {
            "offensive_rating": 0.10,
            "defensive_rating": 0.10,
            "efficiency_rating": 0.08,
            "pace_rating": 0.05,
            "shooting_efficiency": 0.06,
            "power_play_efficiency": 0.06,
            "penalty_kill_efficiency": 0.06,
            "turnover_rate": 0.02,
            "rebounding_efficiency": 0.00,  # Not applicable
            "assist_to_turnover_ratio": 0.03,
            "recent_form_rating": 0.10,
            "home_away_split": 0.06,
            "rest_advantage": 0.05,
            "schedule_strength": 0.05,
            "matchup_history": 0.04,
            "injuries_impact": 0.06,
            "clutch_performance": 0.05,
            "days_of_rest": 0.05,
            "back_to_back": -0.04,  # Huge in NHL
        },
        SportType.MLB: {
            "offensive_rating": 0.10,
            "defensive_rating": 0.10,
            "efficiency_rating": 0.08,
            "pitching_rotation_rating": 0.12,
            "bullpen_rating": 0.08,
            "shooting_efficiency": 0.00,  # Not applicable
            "three_point_efficiency": 0.00,
            "turnover_rate": 0.00,
            "rebounding_efficiency": 0.00,
            "assist_to_turnover_ratio": 0.00,
            "recent_form_rating": 0.08,
            "home_away_split": 0.06,
            "rest_advantage": 0.04,
            "schedule_strength": 0.06,
            "matchup_history": 0.05,
            "injuries_impact": 0.08,
            "clutch_performance": 0.03,
            "days_of_rest": 0.06,
            "back_to_back": 0.00,  # Less relevant in MLB
        },
        SportType.NFL: {
            "offensive_rating": 0.12,
            "defensive_rating": 0.12,
            "efficiency_rating": 0.08,
            "pace_rating": 0.03,
            "red_zone_efficiency": 0.06,
            "third_down_conversion": 0.06,
            "turnover_rate": 0.05,
            "rebounding_efficiency": 0.00,
            "assist_to_turnover_ratio": 0.00,
            "recent_form_rating": 0.08,
            "home_away_split": 0.08,
            "rest_advantage": 0.05,
            "schedule_strength": 0.06,
            "matchup_history": 0.04,
            "injuries_impact": 0.08,
            "clutch_performance": 0.05,
            "days_of_rest": 0.06,
            "back_to_back": 0.00,  # Not applicable
        },
        SportType.NCAAF: {
            "offensive_rating": 0.11,
            "defensive_rating": 0.11,
            "efficiency_rating": 0.08,
            "pace_rating": 0.03,
            "red_zone_efficiency": 0.06,
            "third_down_conversion": 0.05,
            "turnover_rate": 0.04,
            "rebounding_efficiency": 0.00,
            "assist_to_turnover_ratio": 0.00,
            "recent_form_rating": 0.07,
            "home_away_split": 0.10,  # Huge in college
            "rest_advantage": 0.04,
            "schedule_strength": 0.08,
            "matchup_history": 0.03,
            "injuries_impact": 0.05,
            "clutch_performance": 0.04,
            "days_of_rest": 0.04,
            "back_to_back": 0.00,
        },
        SportType.SOCCER: {
            "offensive_rating": 0.12,
            "defensive_rating": 0.12,
            "efficiency_rating": 0.10,
            "pace_rating": 0.04,
            "shooting_efficiency": 0.08,
            "turnover_rate": 0.04,
            "recent_form_rating": 0.12,
            "home_away_split": 0.10,
            "rest_advantage": 0.06,
            "schedule_strength": 0.08,
            "matchup_history": 0.04,
            "injuries_impact": 0.06,
            "clutch_performance": 0.04,
            "days_of_rest": 0.06,
            "back_to_back": -0.02,
        },
    }
    
    def __init__(self):
        """Initialize Sintonia scorer."""
        self.logger = logging.getLogger(__name__)
    
    def score(
        self,
        profile: TeamProfile,
        opp_profile: TeamProfile,
    ) -> SintoniaScore:
        """
        Score team profile vs opponent profile.
        
        Args:
            profile: Team profile to score
            opp_profile: Opponent team profile
            
        Returns:
            SintoniaScore with detailed breakdown
        """
        sport = profile.sport
        weights = self.WEIGHTS.get(sport, self.WEIGHTS[SportType.NBA])
        
        # Calculate component scores
        component_scores = self._calculate_components(profile, opp_profile, weights)
        
        # Calculate differential advantages
        differential_scores = self._calculate_differentials(profile, opp_profile, weights)
        
        # Combine scores
        total_score = 0.0
        variable_contributions = {}
        
        for variable, weight in weights.items():
            if variable in component_scores:
                contribution = component_scores[variable] * weight
            elif variable in differential_scores:
                contribution = differential_scores[variable] * weight
            else:
                contribution = 0.0
            
            total_score += contribution
            variable_contributions[variable] = contribution
        
        # Normalize to -5 to +5 scale
        normalized_score = self._normalize_score(total_score)
        
        # Calculate confidence based on data completeness
        confidence = self._calculate_confidence(profile, opp_profile)
        
        # Generate explanation
        explanation = self._generate_explanation(
            normalized_score,
            variable_contributions,
            profile,
            opp_profile
        )
        
        self.logger.debug(
            f"Sintonia score for {profile.team_id} vs {opp_profile.team_id}: "
            f"{normalized_score:.2f} (confidence: {confidence:.2f})"
        )
        
        return SintoniaScore(
            score=normalized_score,
            confidence=confidence,
            component_scores=component_scores,
            variable_contributions=variable_contributions,
            explanation=explanation
        )
    
    def _calculate_components(
        self,
        profile: TeamProfile,
        opp_profile: TeamProfile,
        weights: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate individual component scores."""
        scores = {}
        
        # Offensive vs defensive matchup
        scores["offensive_rating"] = self._normalize_value(
            profile.offensive_rating - opp_profile.defensive_rating,
            -20, 20
        )
        
        # Defensive vs offensive matchup
        scores["defensive_rating"] = self._normalize_value(
            profile.defensive_rating - opp_profile.offensive_rating,
            -20, 20
        )
        
        # Efficiency differential
        scores["efficiency_rating"] = self._normalize_value(
            profile.efficiency_rating - opp_profile.efficiency_rating,
            -15, 15
        )
        
        # Pace control (higher pace favors better shooting teams)
        pace_diff = profile.pace_rating - opp_profile.pace_rating
        if profile.shooting_efficiency > opp_profile.shooting_efficiency:
            scores["pace_rating"] = self._normalize_value(pace_diff, -10, 10)
        else:
            scores["pace_rating"] = self._normalize_value(-pace_diff, -10, 10)
        
        # Shooting efficiency
        scores["shooting_efficiency"] = self._normalize_value(
            profile.shooting_efficiency - opp_profile.shooting_efficiency,
            -0.1, 0.1
        )
        
        # Three point efficiency
        scores["three_point_efficiency"] = self._normalize_value(
            profile.three_point_efficiency - opp_profile.three_point_efficiency,
            -0.08, 0.08
        )
        
        # Free throw efficiency
        scores["free_throw_efficiency"] = self._normalize_value(
            profile.free_throw_efficiency - opp_profile.free_throw_efficiency,
            -0.1, 0.1
        )
        
        # Turnover rate (lower is better)
        scores["turnover_rate"] = self._normalize_value(
            opp_profile.turnover_rate - profile.turnover_rate,
            -0.05, 0.05
        )
        
        # Rebounding
        scores["rebounding_efficiency"] = self._normalize_value(
            profile.rebounding_efficiency - opp_profile.rebounding_efficiency,
            -0.1, 0.1
        )
        
        # Assist to turnover
        scores["assist_to_turnover_ratio"] = self._normalize_value(
            profile.assist_to_turnover_ratio - opp_profile.assist_to_turnover_ratio,
            -1.0, 1.0
        )
        
        # Recent form
        scores["recent_form_rating"] = self._normalize_value(
            profile.recent_form_rating - opp_profile.recent_form_rating,
            -10, 10
        )
        
        # Home/away split
        scores["home_away_split"] = self._normalize_value(
            profile.home_away_split,
            -10, 10
        )
        
        # Rest advantage
        scores["rest_advantage"] = self._normalize_value(
            profile.rest_advantage,
            -3, 3
        )
        
        # Schedule strength
        scores["schedule_strength"] = self._normalize_value(
            profile.schedule_strength - opp_profile.schedule_strength,
            -5, 5
        )
        
        # Matchup history
        scores["matchup_history"] = self._normalize_value(
            profile.matchup_history,
            -10, 10
        )
        
        # Clutch performance
        scores["clutch_performance"] = self._normalize_value(
            profile.clutch_performance - opp_profile.clutch_performance,
            -0.1, 0.1
        )
        
        # Injuries impact
        scores["injuries_impact"] = self._normalize_value(
            opp_profile.injuries_impact - profile.injuries_impact,
            -10, 10
        )
        
        # Days of rest
        scores["days_of_rest"] = self._normalize_value(
            profile.days_of_rest - 2,
            -2, 3
        )
        
        # Back to back penalty
        if profile.back_to_back:
            scores["back_to_back"] = -1.0
        else:
            scores["back_to_back"] = 0.0
        
        # Sport-specific calculations
        if hasattr(profile, 'pitching_rotation_rating') and profile.pitching_rotation_rating is not None:
            scores["pitching_rotation_rating"] = self._normalize_value(
                profile.pitching_rotation_rating - getattr(opp_profile, 'pitching_rotation_rating', 0),
                -2, 2
            )
        
        if hasattr(profile, 'bullpen_rating') and profile.bullpen_rating is not None:
            scores["bullpen_rating"] = self._normalize_value(
                profile.bullpen_rating - getattr(opp_profile, 'bullpen_rating', 0),
                -2, 2
            )
        
        if hasattr(profile, 'power_play_efficiency') and profile.power_play_efficiency is not None:
            scores["power_play_efficiency"] = self._normalize_value(
                profile.power_play_efficiency - getattr(opp_profile, 'power_play_efficiency', 0),
                -0.15, 0.15
            )
        
        if hasattr(profile, 'penalty_kill_efficiency') and profile.penalty_kill_efficiency is not None:
            scores["penalty_kill_efficiency"] = self._normalize_value(
                profile.penalty_kill_efficiency - getattr(opp_profile, 'penalty_kill_efficiency', 0),
                -0.15, 0.15
            )
        
        if hasattr(profile, 'red_zone_efficiency') and profile.red_zone_efficiency is not None:
            scores["red_zone_efficiency"] = self._normalize_value(
                profile.red_zone_efficiency - getattr(opp_profile, 'red_zone_efficiency', 0),
                -0.2, 0.2
            )
        
        if hasattr(profile, 'third_down_conversion') and profile.third_down_conversion is not None:
            scores["third_down_conversion"] = self._normalize_value(
                profile.third_down_conversion - getattr(opp_profile, 'third_down_conversion', 0),
                -0.15, 0.15
            )
        
        return scores
    
    def _calculate_differentials(
        self,
        profile: TeamProfile,
        opp_profile: TeamProfile,
        weights: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate differential advantages."""
        differentials = {}
        
        # Overall team strength differential
        profile_strength = (
            profile.offensive_rating + 
            profile.defensive_rating + 
            profile.efficiency_rating
        ) / 3
        
        opp_strength = (
            opp_profile.offensive_rating + 
            opp_profile.defensive_rating + 
            opp_profile.efficiency_rating
        ) / 3
        
        differentials["overall_strength"] = self._normalize_value(
            profile_strength - opp_strength,
            -15, 15
        )
        
        return differentials
    
    def _normalize_value(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize a value to -1 to 1 range."""
        if max_val == min_val:
            return 0.0
        
        normalized = 2 * (value - min_val) / (max_val - min_val) - 1
        return max(-1.0, min(1.0, normalized))
    
    def _normalize_score(self, raw_score: float) -> float:
        """Normalize final score to -5 to +5 range."""
        # Raw scores typically range from -2 to +2
        # Scale to -5 to +5
        scaled = raw_score * 2.5
        return max(-5.0, min(5.0, scaled))
    
    def _calculate_confidence(
        self,
        profile: TeamProfile,
        opp_profile: TeamProfile
    ) -> float:
        """Calculate confidence score based on data completeness."""
        confidence = 0.5  # Base confidence
        
        # Check for missing critical data
        critical_vars = [
            profile.offensive_rating,
            profile.defensive_rating,
            profile.efficiency_rating,
        ]
        
        for var in critical_vars:
            if var != 0.0:
                confidence += 0.1
        
        # Penalize for missing matchup history
        if profile.matchup_history == 0.0:
            confidence -= 0.1
        
        # Penalize for significant injuries
        if profile.injuries_impact < -5.0:
            confidence -= 0.1
        
        return max(0.1, min(1.0, confidence))
    
    def _generate_explanation(
        self,
        score: float,
        contributions: Dict[str, float],
        profile: TeamProfile,
        opp_profile: TeamProfile
    ) -> str:
        """Generate human-readable explanation."""
        # Find top positive and negative contributors
        sorted_contribs = sorted(
            contributions.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )
        
        top_positive = [(k, v) for k, v in sorted_contribs if v > 0.1][:2]
        top_negative = [(k, v) for k, v in sorted_contribs if v < -0.1][:2]
        
        explanation_parts = []
        
        if score > 2.0:
            explanation_parts.append(f"Strong advantage ({score:.1f})")
        elif score > 0.5:
            explanation_parts.append(f"Moderate advantage ({score:.1f})")
        elif score > -0.5:
            explanation_parts.append(f"Even matchup ({score:.1f})")
        elif score > -2.0:
            explanation_parts.append(f"Moderate disadvantage ({score:.1f})")
        else:
            explanation_parts.append(f"Significant disadvantage ({score:.1f})")
        
        if top_positive:
            factors = ", ".join([k.replace("_", " ") for k, v in top_positive])
            explanation_parts.append(f"Key advantages: {factors}")
        
        if top_negative:
            factors = ", ".join([k.replace("_", " ") for k, v in top_negative])
            explanation_parts.append(f"Key concerns: {factors}")
        
        return "; ".join(explanation_parts)
