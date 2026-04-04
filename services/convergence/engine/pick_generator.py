"""
Pick Generator with Kelly Criterion Sizing

Generates betting picks with optimal position sizing based on edge and bankroll.
"""

import logging
from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime

from models import Convergence, Pick, ConvergenceStatus, MarketType

logger = logging.getLogger(__name__)


@dataclass
class KellyParams:
    """Parameters for Kelly criterion calculation."""
    fractional_kelly: float = 0.25  # Conservative fraction (quarter Kelly)
    max_bet_units: float = 5.0      # Maximum units per pick
    min_edge_threshold: float = 2.0  # Minimum edge to generate pick
    min_confidence: float = 0.6      # Minimum confidence to generate pick
    min_convergence_score: float = 7.0  # Minimum fused score


class PickGenerator:
    """
    Generates optimal betting picks from convergence data.
    
    Uses Kelly criterion for position sizing with fractional Kelly
    for risk management. Includes filters for quality thresholds.
    """
    
    def __init__(self, params: Optional[KellyParams] = None):
        self.params = params or KellyParams()
        logger.info(f"PickGenerator initialized: {self.params}")
    
    def generate(
        self,
        convergence: Convergence,
        odds: float,
        line: Optional[float] = None,
        bankroll_units: float = 100.0,
        notes: str = ""
    ) -> Optional[Pick]:
        """
        Generate a pick from convergence data.
        
        Args:
            convergence: Fused convergence result
            odds: American odds (e.g., -110, +150)
            line: Spread or total line if applicable
            bankroll_units: Total bankroll in betting units
            notes: Optional notes for the pick
            
        Returns:
            Pick object or None if doesn't meet criteria
        """
        # Validate inputs
        if not self._meets_criteria(convergence):
            logger.debug(f"Convergence {convergence.game_id} doesn't meet pick criteria")
            return None
        
        # Calculate Kelly sizing
        kelly_frac = self._calculate_kelly_fraction(convergence.edge_percent, odds)
        
        if kelly_frac <= 0:
            logger.debug(f"Negative Kelly fraction for {convergence.game_id}, skipping")
            return None
        
        # Apply fractional Kelly and constraints
        recommended_units = self._apply_position_sizing(kelly_frac, bankroll_units)
        
        if recommended_units < 0.1:  # Minimum bet size
            logger.debug(f"Recommended units too small for {convergence.game_id}")
            return None
        
        logger.info(
            f"Generated pick for {convergence.game_id}: "
            f"{convergence.selection} @ {odds}, "
            f"{recommended_units:.2f} units (Kelly: {kelly_frac:.3f})"
        )
        
        return Pick(
            convergence_id=convergence.id,
            game_id=convergence.game_id,
            sport=convergence.sport,
            market=convergence.market,
            selection=convergence.selection,
            odds=odds,
            line=line,
            convergence_score=convergence.score,
            confidence=convergence.confidence,
            edge_percent=convergence.edge_percent,
            kelly_fraction=kelly_frac,
            fractional_kelly=self.params.fractional_kelly,
            recommended_units=recommended_units,
            max_units=self.params.max_bet_units,
            notes=notes
        )
    
    def batch_generate(
        self,
        convergences: List[Convergence],
        odds_map: Dict[str, float],
        line_map: Optional[Dict[str, float]] = None,
        bankroll_units: float = 100.0
    ) -> List[Pick]:
        """
        Generate picks for multiple convergences.
        
        Args:
            convergences: List of convergence results
            odds_map: Dict mapping game_id to odds
            line_map: Optional dict mapping game_id to line
            bankroll_units: Total bankroll in units
            
        Returns:
            List of generated picks
        """
        picks = []
        line_map = line_map or {}
        
        for convergence in convergences:
            odds = odds_map.get(convergence.game_id)
            if odds is None:
                logger.warning(f"No odds found for {convergence.game_id}")
                continue
            
            line = line_map.get(convergence.game_id)
            
            pick = self.generate(
                convergence=convergence,
                odds=odds,
                line=line,
                bankroll_units=bankroll_units
            )
            
            if pick:
                picks.append(pick)
        
        logger.info(f"Batch generated {len(picks)}/{len(convergences)} picks")
        return picks
    
    def _meets_criteria(self, convergence: Convergence) -> bool:
        """Check if convergence meets minimum criteria for pick generation."""
        # Must be LOCK or ALIGNED status
        if convergence.status not in (ConvergenceStatus.LOCK, ConvergenceStatus.ALIGNED):
            logger.debug(f"Status {convergence.status.value} doesn't meet criteria")
            return False
        
        # Minimum convergence score
        if convergence.score < self.params.min_convergence_score:
            logger.debug(f"Score {convergence.score} below threshold")
            return False
        
        # Minimum confidence
        if convergence.confidence < self.params.min_confidence:
            logger.debug(f"Confidence {convergence.confidence} below threshold")
            return False
        
        # Minimum edge
        if convergence.edge_percent < self.params.min_edge_threshold:
            logger.debug(f"Edge {convergence.edge_percent}% below threshold")
            return False
        
        return True
    
    def _calculate_kelly_fraction(self, edge_percent: float, odds: float) -> float:
        """
        Calculate Kelly criterion fraction.
        
        Kelly = (bp - q) / b
        where:
        - b = decimal odds - 1 (net odds received)
        - p = probability of win (derived from edge)
        - q = 1 - p
        
        Args:
            edge_percent: Expected edge percentage
            odds: American odds
            
        Returns:
            Kelly fraction (0 to 1, negative means don't bet)
        """
        # Convert American odds to decimal
        if odds > 0:
            decimal_odds = odds / 100 + 1
        else:
            decimal_odds = 100 / abs(odds) + 1
        
        # Net odds (what you win per unit bet)
        b = decimal_odds - 1
        
        # Probability from edge
        # Edge = (p * decimal_odds) - 1
        # So: p = (edge + 1) / decimal_odds
        edge_decimal = edge_percent / 100
        p = min(0.99, max(0.01, (edge_decimal + 1) / decimal_odds))
        q = 1 - p
        
        # Kelly formula
        kelly = (b * p - q) / b
        
        logger.debug(
            f"Kelly calc: edge={edge_percent}%, odds={odds}, "
            f"b={b:.3f}, p={p:.3f}, kelly={kelly:.3f}"
        )
        
        return kelly
    
    def _apply_position_sizing(
        self, 
        kelly_fraction: float, 
        bankroll_units: float
    ) -> float:
        """
        Apply position sizing constraints.
        
        Args:
            kelly_fraction: Raw Kelly fraction
            bankroll_units: Total bankroll in units
            
        Returns:
            Recommended bet size in units
        """
        # Apply fractional Kelly
        adjusted_kelly = kelly_fraction * self.params.fractional_kelly
        
        # Calculate raw units
        raw_units = adjusted_kelly * bankroll_units
        
        # Apply max constraint
        capped_units = min(raw_units, self.params.max_bet_units)
        
        # Round to reasonable precision
        return round(capped_units, 2)
    
    def adjust_for_portfolio(
        self,
        picks: List[Pick],
        correlations: Optional[Dict[tuple, float]] = None
    ) -> List[Pick]:
        """
        Adjust pick sizes based on portfolio correlations.
        
        Reduces size for highly correlated bets to manage risk.
        
        Args:
            picks: List of picks to adjust
            correlations: Dict of (game_id1, game_id2) -> correlation
            
        Returns:
            Adjusted picks
        """
        if not correlations or len(picks) < 2:
            return picks
        
        adjusted = []
        for pick in picks:
            # Find correlations with other picks
            correlation_penalty = 0
            for other_pick in picks:
                if other_pick.id == pick.id:
                    continue
                
                key = (pick.game_id, other_pick.game_id)
                reverse_key = (other_pick.game_id, pick.game_id)
                
                corr = correlations.get(key) or correlations.get(reverse_key) or 0
                if corr > 0.7:  # High correlation
                    correlation_penalty += 0.1
            
            # Apply penalty
            adjustment_factor = max(0.5, 1 - correlation_penalty)
            
            adjusted_pick = pick.model_copy()
            adjusted_pick.recommended_units = round(
                pick.recommended_units * adjustment_factor, 2
            )
            adjusted.append(adjusted_pick)
        
        return adjusted


def kelly_size(edge: float, odds: float, bankroll: float, fraction: float = 0.25) -> float:
    """
    Calculate bet size using Kelly criterion with fractional Kelly.
    
    Args:
        edge: Edge percentage (e.g., 5.0 for 5% edge)
        odds: American odds (e.g., -110, +150)
        bankroll: Bankroll in betting units
        fraction: Kelly fraction (0.25 = quarter Kelly)
        
    Returns:
        Recommended bet size in units
    """
    # Convert American odds
    if odds > 0:
        decimal_odds = odds / 100 + 1
    else:
        decimal_odds = 100 / abs(odds) + 1
    
    # Kelly parameters
    b = decimal_odds - 1
    p = edge / 100
    q = 1 - p
    
    # Kelly fraction
    kelly = (b * p - q) / b
    
    # Apply fractional Kelly
    return bankroll * kelly * fraction


def generate_pick(
    convergence: Convergence,
    odds: float,
    line: Optional[float] = None,
    bankroll_units: float = 100.0
) -> Optional[Pick]:
    """
    Convenience function for one-off pick generation.
    
    Args:
        convergence: Fused convergence result
        odds: American odds
        line: Optional spread/total line
        bankroll_units: Total bankroll in units
        
    Returns:
        Pick or None if criteria not met
    """
    generator = PickGenerator()
    return generator.generate(convergence, odds, line, bankroll_units)
