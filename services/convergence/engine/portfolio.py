"""
Portfolio Optimization using Modern Portfolio Theory

Quadratic programming approach to maximize returns while managing risk
through correlation-aware position sizing.
"""

import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import math

from models import Pick, Portfolio, Sport, MarketType

logger = logging.getLogger(__name__)


@dataclass
class PortfolioConstraints:
    """Constraints for portfolio optimization."""
    max_single_position: float = 0.05      # Max 5% per pick
    max_daily_exposure: float = 0.25       # Max 25% daily exposure
    max_sport_exposure: Dict[Sport, float] = None
    max_correlated_exposure: float = 0.08  # Max for correlated picks
    min_pick_confidence: float = 0.6
    target_sharpe: float = 1.0


class PortfolioOptimizer:
    """
    Portfolio optimizer using Modern Portfolio Theory principles.
    Optimizes position weights to maximize risk-adjusted returns.
    """
    
    def __init__(self, constraints: Optional[PortfolioConstraints] = None):
        self.constraints = constraints or PortfolioConstraints()
        self.max_sport_exposure = self.constraints.max_sport_exposure or {}
        logger.info(f"PortfolioOptimizer initialized: {self.constraints}")
    
    def optimize(
        self,
        picks: List[Pick],
        correlations: Optional[Dict[Tuple[str, str], float]] = None
    ) -> Portfolio:
        """Optimize portfolio weights for given picks."""
        if not picks:
            logger.warning("No picks provided for optimization")
            return self._empty_portfolio()
        
        qualified_picks = [
            p for p in picks 
            if p.confidence >= self.constraints.min_pick_confidence
        ]
        
        if not qualified_picks:
            logger.warning("No qualified picks after filtering")
            return self._empty_portfolio()
        
        corr_matrix = self._build_correlation_matrix(qualified_picks, correlations)
        expected_returns = [self._expected_return(p) for p in qualified_picks]
        risks = [self._calculate_risk(p) for p in qualified_picks]
        
        initial_weights = self._normalize_weights([
            p.recommended_units for p in qualified_picks
        ])
        
        optimal_weights = self._iterative_optimize(
            qualified_picks,
            initial_weights,
            expected_returns,
            risks,
            corr_matrix
        )
        
        final_weights = self._apply_constraints(qualified_picks, optimal_weights)
        
        metrics = self._calculate_metrics(
            qualified_picks, final_weights, expected_returns, corr_matrix
        )
        
        logger.info(
            f"Portfolio optimized: {len(qualified_picks)} picks, "
            f"total_allocation={sum(final_weights):.2%}, "
            f"sharpe={metrics['sharpe_ratio']:.2f}"
        )
        
        return Portfolio(
            picks=qualified_picks,
            weights=final_weights,
            max_single_position=self.constraints.max_single_position,
            max_daily_exposure=self.constraints.max_daily_exposure,
            expected_return=metrics['expected_return'],
            expected_variance=metrics['variance'],
            sharpe_ratio=metrics['sharpe_ratio'],
            total_allocation=sum(final_weights),
            num_positions=len(qualified_picks),
            var_95=metrics['var_95'],
            max_drawdown_estimate=metrics['max_drawdown']
        )
    
    def _iterative_optimize(
        self,
        picks: List[Pick],
        initial_weights: List[float],
        expected_returns: List[float],
        risks: List[float],
        corr_matrix: List[List[float]]
    ) -> List[float]:
        """Iterative optimization to approximate QP solution."""
        n = len(picks)
        weights = initial_weights.copy()
        
        for iteration in range(50):
            old_weights = weights.copy()
            
            for i in range(n):
                marginal_risk = sum(
                    weights[j] * risks[i] * risks[j] * corr_matrix[i][j]
                    for j in range(n)
                )
                
                if marginal_risk > 0:
                    risk_adj_return = expected_returns[i] / marginal_risk
                else:
                    risk_adj_return = expected_returns[i]
                
                target_weight = risk_adj_return / sum(expected_returns)
                weights[i] = 0.7 * weights[i] + 0.3 * target_weight
            
            weights = self._normalize_weights(weights)
            
            change = sum(abs(w - old_w) for w, old_w in zip(weights, old_weights))
            if change < 0.001:
                break
        
        return weights
    
    def _apply_constraints(
        self,
        picks: List[Pick],
        weights: List[float]
    ) -> List[float]:
        """Apply portfolio constraints to weights."""
        n = len(picks)
        adjusted = weights.copy()
        
        for i in range(n):
            adjusted[i] = min(adjusted[i], self.constraints.max_single_position)
        
        sport_exposure: Dict[Sport, float] = {}
        for i, pick in enumerate(picks):
            sport = pick.sport
            sport_exposure[sport] = sport_exposure.get(sport, 0) + adjusted[i]
        
        for sport, exposure in sport_exposure.items():
            max_exp = self.max_sport_exposure.get(sport, 0.15)
            if exposure > max_exp:
                scale = max_exp / exposure
                for i, pick in enumerate(picks):
                    if pick.sport == sport:
                        adjusted[i] *= scale
        
        total = sum(adjusted)
        if total > self.constraints.max_daily_exposure:
            scale = self.constraints.max_daily_exposure / total
            adjusted = [w * scale for w in adjusted]
        
        return adjusted
    
    def _calculate_metrics(
        self,
        picks: List[Pick],
        weights: List[float],
        expected_returns: List[float],
        corr_matrix: List[List[float]]
    ) -> Dict[str, float]:
        """Calculate portfolio risk and return metrics."""
        n = len(picks)
        
        portfolio_return = sum(
            w * r for w, r in zip(weights, expected_returns)
        )
        
        portfolio_variance = 0
        for i in range(n):
            for j in range(n):
                portfolio_variance += (
                    weights[i] * weights[j] * 
                    expected_returns[i] * expected_returns[j] * 
                    corr_matrix[i][j]
                )
        
        portfolio_std = math.sqrt(max(0, portfolio_variance))
        sharpe = portfolio_return / portfolio_std if portfolio_std > 0 else 0
        
        var_95 = 1.645 * portfolio_std
        max_drawdown = 2 * portfolio_std
        
        return {
            'expected_return': portfolio_return,
            'variance': portfolio_variance,
            'sharpe_ratio': sharpe,
            'var_95': var_95,
            'max_drawdown': max_drawdown
        }
    
    def _expected_return(self, pick: Pick) -> float:
        """Calculate expected return for a pick."""
        edge_decimal = pick.edge_percent / 100
        return edge_decimal * pick.confidence
    
    def _calculate_risk(self, pick: Pick) -> float:
        """Calculate risk proxy for a pick."""
        base_risk = 0.5
        confidence_adj = 1 - pick.confidence
        edge_risk = 1 / (1 + abs(pick.edge_percent) / 5)
        return base_risk * confidence_adj * edge_risk
    
    def _build_correlation_matrix(
        self,
        picks: List[Pick],
        correlations: Optional[Dict[Tuple[str, str], float]]
    ) -> List[List[float]]:
        """Build correlation matrix for picks."""
        n = len(picks)
        matrix = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        
        if not correlations:
            for i in range(n):
                for j in range(i + 1, n):
                    corr = self._estimate_correlation(picks[i], picks[j])
                    matrix[i][j] = corr
                    matrix[j][i] = corr
        else:
            for i in range(n):
                for j in range(i + 1, n):
                    key = (picks[i].game_id, picks[j].game_id)
                    reverse_key = (picks[j].game_id, picks[i].game_id)
                    corr = correlations.get(key) or correlations.get(reverse_key) or 0.0
                    matrix[i][j] = corr
                    matrix[j][i] = corr
        
        return matrix
    
    def _estimate_correlation(self, pick1: Pick, pick2: Pick) -> float:
        """Estimate correlation between two picks."""
        if pick1.game_id == pick2.game_id:
            return 0.7
        if pick1.sport == pick2.sport:
            return 0.3
        return 0.1
    
    def _normalize_weights(self, weights: List[float]) -> List[float]:
        """Normalize weights to sum to 1."""
        total = sum(weights)
        if total == 0:
            n = len(weights)
            return [1.0 / n] * n
        return [w / total for w in weights]
    
    def _empty_portfolio(self) -> Portfolio:
        """Create empty portfolio."""
        return Portfolio(
            picks=[],
            weights=[],
            expected_return=0.0,
            expected_variance=0.0,
            sharpe_ratio=0.0,
            total_allocation=0.0,
            num_positions=0,
            var_95=0.0,
            max_drawdown_estimate=0.0
        )


def optimize_portfolio(
    picks: List[Pick],
    max_single_position: float = 0.05,
    max_daily_exposure: float = 0.25
) -> Portfolio:
    """Convenience function for portfolio optimization."""
    constraints = PortfolioConstraints(
        max_single_position=max_single_position,
        max_daily_exposure=max_daily_exposure
    )
    optimizer = PortfolioOptimizer(constraints)
    return optimizer.optimize(picks)