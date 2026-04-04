"""
Renzo - Data Gaps Finder
Validates data quality and identifies missing information.
"""
import logging
from typing import Any, Dict, List, Optional
from models import Game, RenzoValidation, SportType, TeamProfile

logger = logging.getLogger(__name__)


class RenzoValidator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate(self, game: Game, side: str,
                 profile: Optional[TeamProfile] = None,
                 opp_profile: Optional[TeamProfile] = None) -> RenzoValidation:
        data_gaps = []
        warnings = []
        missing_count = 0
        
        # Check game data completeness
        if not game.line_history:
            data_gaps.append("Missing line movement history")
            missing_count += 1
        
        if game.public_betting_pct is None:
            data_gaps.append("Missing public betting percentage")
            missing_count += 1
        
        if game.sharp_money_indicator is None:
            data_gaps.append("Missing sharp money indicator")
            missing_count += 1
        
        # Check profile completeness
        if profile:
            if profile.offensive_rating == 0.0:
                data_gaps.append("Missing offensive rating")
                missing_count += 1
            
            if profile.defensive_rating == 0.0:
                data_gaps.append("Missing defensive rating")
                missing_count += 1
            
            if profile.recent_form_rating == 0.0:
                warnings.append("Missing recent form data")
            
            if profile.days_of_rest == 0 and not profile.back_to_back:
                warnings.append("Rest data unclear")
            
            # Sport-specific checks
            if game.sport == SportType.MLB:
                if getattr(profile, "pitching_rotation_rating", None) is None:
                    data_gaps.append("Missing pitcher rating")
                    missing_count += 1
            
            if game.sport == SportType.NHL:
                if getattr(profile, "power_play_efficiency", None) is None:
                    warnings.append("Missing special teams data")
        else:
            data_gaps.append("Missing team profile")
            missing_count += 5
        
        # Check opponent profile
        if not opp_profile:
            data_gaps.append("Missing opponent profile")
            missing_count += 5
        
        # Calculate data quality score
        total_expected = 15  # Expected data points
        data_quality = max(0.0, 1.0 - (missing_count / total_expected))
        
        # Calculate validation score
        # Negative means more gaps (lower confidence)
        validation = (data_quality - 0.7) * 3  # Scale to roughly -2 to +1
        validation = max(-1.0, min(1.0, validation))
        
        return RenzoValidation(
            validation=validation,
            data_gaps=data_gaps,
            data_quality_score=data_quality,
            warnings=warnings,
            missing_data_points=missing_count
        )
    
    def validate_market_data(self, game: Game, market_type: str) -> Dict[str, Any]:
        issues = []
        confidence = 1.0
        
        if market_type == "spread":
            if game.spread is None:
                issues.append("No spread available")
                confidence -= 0.3
        
        elif market_type == "total":
            if game.total is None:
                issues.append("No total available")
                confidence -= 0.3
            if game.weather and game.weather.get("wind_speed", 0) > 15:
                issues.append("High wind may affect total")
                confidence -= 0.1
        
        elif market_type == "moneyline":
            if game.home_moneyline is None or game.away_moneyline is None:
                issues.append("Missing moneyline odds")
                confidence -= 0.3
        
        return {
            "market_type": market_type,
            "issues": issues,
            "confidence": max(0.1, confidence),
            "is_valid": confidence > 0.5
        }
