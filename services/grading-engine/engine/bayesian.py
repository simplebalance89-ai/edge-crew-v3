"""
Bayesian Network for Probability Fusion

Combines multiple evidence sources using Bayesian updating
for final grade probability calculation.
"""
import logging
import math
from typing import Any, Dict, List, Optional
from models import Chain, Grade, SportType

logger = logging.getLogger(__name__)


class BayesianFusion:
    """
    Bayesian network for fusing multiple scoring components.
    
    Combines prior beliefs (Sintonia score) with evidence
    from situational, rules-based, and validation components.
    """
    
    # Base probabilities for each grade
    PRIOR_PROBABILITIES = {
        Grade.A_PLUS: 0.02,
        Grade.A: 0.05,
        Grade.A_MINUS: 0.08,
        Grade.B_PLUS: 0.10,
        Grade.B: 0.15,
        Grade.B_MINUS: 0.15,
        Grade.C_PLUS: 0.15,
        Grade.C: 0.15,
        Grade.C_MINUS: 0.10,
        Grade.D: 0.03,
        Grade.F: 0.02,
    }
    
    # Evidence weights by source
    EVIDENCE_WEIGHTS = {
        "sintonia": 0.35,
        "edge": 0.20,
        "peter_rules": 0.25,
        "renzo": 0.15,
        "market": 0.05,
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def update(self, prior: float, evidence: List[float],
               evidence_weights: Optional[List[float]] = None) -> float:
        """
        Bayesian update of prior with evidence.
        
        Args:
            prior: Prior score (from Sintonia, -5 to +5)
            evidence: List of evidence scores (each -5 to +5)
            evidence_weights: Optional weights for each evidence
            
        Returns:
            Posterior score (-5 to +5)
        """
        if evidence_weights is None:
            evidence_weights = [0.25] * len(evidence)
        
        # Normalize weights
        total_weight = sum(evidence_weights)
        if total_weight > 0:
            evidence_weights = [w / total_weight for w in evidence_weights]
        
        # Convert prior to probability
        prior_prob = self._score_to_probability(prior)
        
        # Apply each evidence using Bayesian updating
        posterior_prob = prior_prob
        for ev_score, weight in zip(evidence, evidence_weights):
            ev_prob = self._score_to_probability(ev_score)
            # Bayesian update with weighted evidence
            posterior_prob = self._bayesian_update(posterior_prob, ev_prob, weight)
        
        # Convert back to score
        posterior = self._probability_to_score(posterior_prob)
        
        self.logger.debug(
            f"Bayesian update: prior={prior:.2f}, evidence={evidence}, "
            f"posterior={posterior:.2f}"
        )
        
        return posterior
    
    def fuse_components(self, components: Dict[str, float],
                        confidence_scores: Optional[Dict[str, float]] = None) -> float:
        """
        Fuse multiple component scores into final score.
        
        Args:
            components: Dict of component name to score
            confidence_scores: Dict of component name to confidence (0-1)
            
        Returns:
            Fused score (-5 to +5)
        """
        if not components:
            return 0.0
        
        if confidence_scores is None:
            confidence_scores = {k: 0.8 for k in components.keys()}
        
        # Weighted average with confidence weighting
        weighted_sum = 0.0
        total_weight = 0.0
        
        for name, score in components.items():
            weight = self.EVIDENCE_WEIGHTS.get(name, 0.1)
            confidence = confidence_scores.get(name, 0.5)
            adjusted_weight = weight * confidence
            
            weighted_sum += score * adjusted_weight
            total_weight += adjusted_weight
        
        if total_weight == 0:
            return 0.0
        
        fused_score = weighted_sum / total_weight
        
        # Apply Bayesian smoothing toward prior
        prior = 0.0  # Neutral prior
        smoothing_factor = 0.1
        smoothed = (1 - smoothing_factor) * fused_score + smoothing_factor * prior
        
        return max(-5.0, min(5.0, smoothed))
    
    def calculate_grade_probability(self, score: float, 
                                     target_grade: Grade) -> float:
        """
        Calculate probability of achieving a specific grade.
        
        Args:
            score: Current score (-5 to +5)
            target_grade: Target grade to evaluate
            
        Returns:
            Probability (0 to 1)
        """
        # Map grades to score thresholds
        grade_thresholds = {
            Grade.A_PLUS: 4.5,
            Grade.A: 4.0,
            Grade.A_MINUS: 3.5,
            Grade.B_PLUS: 2.5,
            Grade.B: 1.5,
            Grade.B_MINUS: 0.5,
            Grade.C_PLUS: -0.5,
            Grade.C: -1.5,
            Grade.C_MINUS: -2.5,
            Grade.D: -3.5,
            Grade.F: -5.0,
        }
        
        threshold = grade_thresholds.get(target_grade, 0.0)
        
        # Use sigmoid to calculate probability
        # Higher score = higher probability of good grades
        if score >= threshold:
            return 0.5 + 0.5 * math.tanh((score - threshold) / 2)
        else:
            return 0.5 - 0.5 * math.tanh((threshold - score) / 2)
    
    def _bayesian_update(self, prior_prob: float, 
                         likelihood: float,
                         weight: float) -> float:
        """
        Perform Bayesian update with weighted evidence.
        
        Uses a modified Bayesian approach where evidence
        is weighted by confidence.
        """
        # Ensure valid probabilities
        prior_prob = max(0.01, min(0.99, prior_prob))
        likelihood = max(0.01, min(0.99, likelihood))
        
        # Weighted likelihood
        weighted_likelihood = weight * likelihood + (1 - weight) * prior_prob
        
        # Bayesian update
        posterior = (weighted_likelihood * prior_prob) / (
            weighted_likelihood * prior_prob + 
            (1 - weighted_likelihood) * (1 - prior_prob)
        )
        
        return max(0.01, min(0.99, posterior))
    
    def _score_to_probability(self, score: float) -> float:
        """Convert score (-5 to +5) to probability (0 to 1)."""
        # Use sigmoid function
        return 1.0 / (1.0 + math.exp(-score))
    
    def _probability_to_score(self, prob: float) -> float:
        """Convert probability (0 to 1) to score (-5 to +5)."""
        # Clip to avoid log(0)
        prob = max(0.001, min(0.999, prob))
        # Inverse sigmoid (logit)
        score = math.log(prob / (1 - prob))
        # Scale to -5 to +5 range
        return max(-5.0, min(5.0, score * 2))
    
    def calculate_confidence_interval(self, score: float,
                                       confidence: float = 0.9) -> tuple:
        """
        Calculate confidence interval for score.
        
        Returns:
            (lower_bound, upper_bound)
        """
        # Standard error decreases with higher confidence
        std_error = 1.5 * (1 - confidence + 0.1)
        
        lower = max(-5.0, score - 1.96 * std_error)
        upper = min(5.0, score + 1.96 * std_error)
        
        return (lower, upper)
