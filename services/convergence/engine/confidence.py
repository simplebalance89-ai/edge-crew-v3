"""
Confidence Calculation Algorithms

Multi-factor confidence calculation with calibration and uncertainty quantification.
"""

import logging
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from models import EngineGrade, AIGrade, Convergence, ConvergenceStatus

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceFactors:
    """Factors contributing to overall confidence calculation."""
    # Data quality factors
    data_completeness: float = 1.0  # 0-1 based on available data
    data_freshness: float = 1.0     # 0-1 based on recency
    sample_size_quality: float = 1.0  # Based on statistical sample size
    
    # Model factors
    model_calibration: float = 1.0   # Historical calibration accuracy
    model_agreement: float = 1.0     # Agreement between models
    
    # Market factors
    market_stability: float = 1.0    # Line stability
    market_liquidity: float = 1.0    # Available liquidity
    
    # Context factors
    injury_uncertainty: float = 1.0  # Penalty for injury uncertainty
    weather_uncertainty: float = 1.0  # For outdoor sports
    
    def calculate_overall(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Calculate weighted overall confidence."""
        default_weights = {
            "data_completeness": 0.20,
            "data_freshness": 0.15,
            "sample_size_quality": 0.15,
            "model_calibration": 0.20,
            "model_agreement": 0.20,
            "market_stability": 0.10,
        }
        
        w = weights or default_weights
        
        total_weight = 0
        weighted_sum = 0
        
        for factor_name, weight in w.items():
            factor_value = getattr(self, factor_name, 1.0)
            weighted_sum += factor_value * weight
            total_weight += weight
        
        # Apply penalties
        penalty = (1 - self.injury_uncertainty) * 0.1 + (1 - self.weather_uncertainty) * 0.05
        
        return max(0, min(1, weighted_sum / total_weight - penalty))


class ConfidenceCalculator:
    """
    Multi-factor confidence calculator for grades and convergences.
    
    Combines multiple data quality, model, and market factors to produce
    a calibrated confidence score.
    """
    
    def __init__(self):
        self.calibration_history: List[Tuple[float, bool]] = []  # (confidence, was_correct)
        logger.info("ConfidenceCalculator initialized")
    
    def calculate_engine_confidence(self, grade: EngineGrade) -> float:
        """
        Calculate refined confidence for an engine grade.
        
        Considers factor distribution and edge reasonableness.
        """
        base_confidence = grade.confidence
        
        # Factor consistency bonus
        factors = grade.factors
        if factors:
            factor_values = list(factors.values())
            factor_std = self._calculate_std(factor_values)
            
            # Lower std = more consistent factors = higher confidence
            consistency_bonus = max(0, 1 - factor_std) * 0.1
        else:
            consistency_bonus = 0
        
        # Edge reasonableness check
        edge_penalty = 0
        if abs(grade.edge_percent) > 15:
            # Very high edges reduce confidence (potential error)
            edge_penalty = min(0.2, (abs(grade.edge_percent) - 15) / 100)
        
        adjusted_confidence = base_confidence + consistency_bonus - edge_penalty
        return max(0, min(1, adjusted_confidence))
    
    def calculate_ai_confidence(self, grade: AIGrade) -> float:
        """
        Calculate refined confidence for an AI grade.
        
        Considers reasoning quality and model version.
        """
        base_confidence = grade.confidence
        
        # Reasoning quality indicator (based on length/structure as proxy)
        reasoning_bonus = 0
        if grade.reasoning:
            reasoning_length = len(grade.reasoning)
            if reasoning_length > 100:
                reasoning_bonus = min(0.05, reasoning_length / 10000)
        
        # Model version factor (newer versions generally more reliable)
        # This is a simplified check - in production, track version performance
        version_bonus = 0
        if grade.model_version and grade.model_version.startswith("3."):
            version_bonus = 0.02
        
        adjusted_confidence = base_confidence + reasoning_bonus + version_bonus
        return max(0, min(1, adjusted_confidence))
    
    def calculate_convergence_confidence(
        self, 
        convergence: Convergence,
        factors: Optional[ConfidenceFactors] = None
    ) -> float:
        """
        Calculate final confidence for a convergence.
        
        Combines base convergence confidence with external factors.
        """
        base_confidence = convergence.confidence
        
        if factors is None:
            # Use default factors
            factors = ConfidenceFactors()
        
        # Factor-based adjustment
        factor_confidence = factors.calculate_overall()
        
        # Status-based adjustment
        status_multiplier = {
            ConvergenceStatus.LOCK: 1.1,
            ConvergenceStatus.ALIGNED: 1.0,
            ConvergenceStatus.DIVERGENT: 0.85,
            ConvergenceStatus.CONFLICT: 0.6
        }.get(convergence.status, 1.0)
        
        # Variance penalty (high variance = lower confidence)
        variance_penalty = convergence.variance * 0.2
        
        # Combine all factors
        adjusted = base_confidence * factor_confidence * status_multiplier - variance_penalty
        
        logger.debug(
            f"Confidence calc for {convergence.game_id}: "
            f"base={base_confidence:.3f}, factor={factor_confidence:.3f}, "
            f"status_mult={status_multiplier:.2f}, final={adjusted:.3f}"
        )
        
        return max(0, min(1, adjusted))
    
    def calibrate_confidence(
        self, 
        confidence_scores: List[float], 
        outcomes: List[bool]
    ) -> Dict[str, float]:
        """
        Calibrate confidence scores against actual outcomes.
        
        Returns calibration metrics to help tune confidence calculations.
        """
        if len(confidence_scores) != len(outcomes):
            raise ValueError("Confidence scores and outcomes must have same length")
        
        if not confidence_scores:
            return {"reliability": 0, "calibration_error": 1.0}
        
        # Bin by confidence levels
        bins = {i/10: [] for i in range(10)}  # 0-0.1, 0.1-0.2, etc.
        
        for conf, outcome in zip(confidence_scores, outcomes):
            bin_key = min(int(conf * 10) / 10, 0.9)
            bins[bin_key].append(outcome)
        
        # Calculate calibration error (ECE - Expected Calibration Error)
        total_samples = len(confidence_scores)
        ece = 0
        
        for bin_conf, bin_outcomes in bins.items():
            if bin_outcomes:
                bin_acc = sum(bin_outcomes) / len(bin_outcomes)
                bin_weight = len(bin_outcomes) / total_samples
                ece += bin_weight * abs(bin_acc - (bin_conf + 0.05))
        
        # Overall accuracy at different confidence thresholds
        high_conf_correct = sum(
            1 for c, o in zip(confidence_scores, outcomes) 
            if c >= 0.7 and o
        )
        high_conf_total = sum(1 for c in confidence_scores if c >= 0.7)
        
        reliability = high_conf_correct / high_conf_total if high_conf_total > 0 else 0
        
        return {
            "reliability": reliability,
            "calibration_error": ece,
            "high_conf_accuracy": reliability,
            "samples_calibrated": total_samples
        }
    
    def calculate_data_freshness(
        self, 
        timestamp: datetime,
        max_age_minutes: int = 60
    ) -> float:
        """
        Calculate data freshness score based on age.
        
        Returns 1.0 for fresh data, decaying to 0.0 at max_age.
        """
        age = datetime.utcnow() - timestamp
        age_minutes = age.total_seconds() / 60
        
        if age_minutes <= 0:
            return 1.0
        
        # Exponential decay
        freshness = math.exp(-age_minutes / (max_age_minutes / 3))
        return max(0, min(1, freshness))
    
    def _calculate_std(self, values: List[float]) -> float:
        """Calculate standard deviation of a list of values."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)


def calculate_convergence_confidence(
    convergence: Convergence,
    data_freshness: float = 1.0,
    market_stability: float = 1.0
) -> float:
    """
    Convenience function for quick confidence calculation.
    
    Args:
        convergence: The convergence to evaluate
        data_freshness: 0-1 freshness of underlying data
        market_stability: 0-1 stability of market lines
        
    Returns:
        Calibrated confidence score
    """
    calculator = ConfidenceCalculator()
    
    factors = ConfidenceFactors(
        data_freshness=data_freshness,
        market_stability=market_stability
    )
    
    return calculator.calculate_convergence_confidence(convergence, factors)
