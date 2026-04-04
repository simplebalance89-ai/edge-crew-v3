"""
Edge Profile - Situational Scoring
"""
import logging
from typing import Optional, Tuple, List
from models import Game, EdgeScore, SportType, TeamProfile

logger = logging.getLogger(__name__)


class EdgeSituationalScorer:
    REST_ADVANTAGE_THRESHOLD = 2
    TRAVEL_IMPACT_THRESHOLD = 1500
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def score(self, game: Game, side: str, profile: Optional[TeamProfile] = None,
              opp_profile: Optional[TeamProfile] = None) -> EdgeScore:
        factors = []
        total_score = 0.0
        magnitude = "none"
        
        is_home = side == "home"
        
        rest_score, rest_factors = self._calc_rest(game, side, profile, opp_profile)
        total_score += rest_score
        factors.extend(rest_factors)
        
        travel_score, travel_factors = self._calc_travel(game, side, profile)
        total_score += travel_score
        factors.extend(travel_factors)
        
        sched_score, sched_factors = self._calc_schedule(game, side, profile, opp_profile)
        total_score += sched_score
        factors.extend(sched_factors)
        
        mot_score, mot_factors = self._calc_motivation(game, side, profile, opp_profile)
        total_score += mot_score
        factors.extend(mot_factors)
        
        home_score, home_factors = self._calc_home(game, side, profile)
        total_score += home_score
        factors.extend(home_factors)
        
        abs_score = abs(total_score)
        if abs_score >= 2.0:
            magnitude = "large"
        elif abs_score >= 1.0:
            magnitude = "medium"
        elif abs_score >= 0.5:
            magnitude = "small"
        
        return EdgeScore(
            score=total_score,
            situational_factors=factors,
            edge_type="situational",
            magnitude=magnitude,
            confidence=0.7
        )
    
    def _calc_rest(self, game, side, profile, opp_profile):
        score, factors = 0.0, []
        if not profile or not opp_profile:
            return score, factors
        rest_diff = profile.days_of_rest - opp_profile.days_of_rest
        if rest_diff >= 2:
            if profile.days_of_rest >= 3 and opp_profile.back_to_back:
                score += 1.5
                factors.append("Fresh_vs_b2b:+1.5")
            else:
                score += 0.8
                factors.append("Rest_advantage:+0.8")
        elif rest_diff == 1:
            score += 0.3
            factors.append("Slight_rest:+0.3")
        elif rest_diff <= -2:
            if profile.back_to_back and opp_profile.days_of_rest >= 2:
                score -= 1.5
                factors.append("B2B_vs_fresh:-1.5")
            else:
                score -= 0.8
                factors.append("Rest_disadv:-0.8")
        if game.sport == SportType.NBA and profile.back_to_back:
            score -= 0.5
            factors.append("NBA_B2B:-0.5")
        if game.sport == SportType.NHL and profile.back_to_back:
            score -= 0.7
            factors.append("NHL_B2B:-0.7")
        return score, factors
    
    def _calc_travel(self, game, side, profile):
        score, factors = 0.0, []
        if not profile:
            return score, factors
        if side == "home":
            opp_travel = getattr(profile, "opponent_travel_distance", 0)
            if opp_travel > 2000:
                score += 0.5
                factors.append("Opp_long_travel:+0.5")
            elif opp_travel > 1500:
                score += 0.3
                factors.append("Opp_travel:+0.3")
        else:
            travel_dist = profile.travel_distance
            if travel_dist > 2000:
                score -= 0.6
                factors.append("Long_travel:-0.6")
            elif travel_dist > 1500:
                score -= 0.3
                factors.append("Travel:-0.3")
        return score, factors
    
    def _calc_schedule(self, game, side, profile, opp_profile):
        score, factors = 0.0, []
        if not profile or not opp_profile:
            return score, factors
        games_5d = getattr(profile, "games_in_5_days", 0)
        opp_games_5d = getattr(opp_profile, "games_in_5_days", 0)
        if games_5d >= 4 and opp_games_5d <= 2:
            score -= 0.8
            factors.append("Heavy_sched:-0.8")
        elif games_5d <= 2 and opp_games_5d >= 4:
            score += 0.8
            factors.append("Sched_adv:+0.8")
        return score, factors
    
    def _calc_motivation(self, game, side, profile, opp_profile):
        score, factors = 0.0, []
        if not profile or not opp_profile:
            return score, factors
        playoff = getattr(profile, "playoff_status", "middle")
        opp_playoff = getattr(opp_profile, "playoff_status", "middle")
        if playoff == "on_bubble" and opp_playoff == "locked":
            score += 0.5
            factors.append("Playoff_desperation:+0.5")
        elif playoff == "locked" and opp_playoff == "on_bubble":
            score -= 0.3
            factors.append("Opp_desperation:-0.3")
        revenge = getattr(profile, "last_matchup_margin_vs_opp", 0)
        if revenge and revenge < -15:
            score += 0.4
            factors.append("Revenge:+0.4")
        return score, factors
    
    def _calc_home(self, game, side, profile):
        score, factors = 0.0, []
        if side != "home" or not profile:
            return score, factors
        split = profile.home_away_split
        if split > 5.0:
            score += 0.4
            factors.append("Strong_home:+0.4")
        elif split > 2.0:
            score += 0.2
            factors.append("Good_home:+0.2")
        elif split < -2.0:
            score -= 0.2
            factors.append("Weak_home:-0.2")
        return score, factors
