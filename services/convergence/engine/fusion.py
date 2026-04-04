"""
Bayesian Fusion Engine

Precision-weighted fusion of Engine and AI grades with uncertainty propagation.
"""

import logging
from typing import Tuple, Optional
from dataclasses import dataclass

from models import EngineGrade, AIGrade, Convergence, ConvergenceStatus

logger = logging.getLogger(__name__)


@dataclass
class FusionParams:
    """Parameters for Bayesian fusion."""
    lock_delta_threshold: float = 0.5
    lock_variance_threshold: float = 0.5
    aligned_threshold: float = 1.5
    divergent_threshold: float = 2.5
    min_confidence: float = 0.1  # Minimum confidence to avoid division issues


class ConvergenceEngine:
    """
    Bayesian fusion engine that combines Engine and AI grades.
    
    Uses precision-weighted averaging where precision = confidence².
    Lower confidence = higher variance = less weight in fusion.
    """
    
    def __init__(self, params: Optional[FusionParams] = None):
        self.params = params or FusionParams()
        logger.info(f"ConvergenceEngine initialized with params: {self.params}")
    
    def fuse(self, our: EngineGrade, ai: AIGrade) -> Convergence:
        """
        Precision-weighted average with uncertainty propagation.
        
        Args:
            our: Engine grade from our process
            ai: AI grade from AI process
            
        Returns:
            Convergence result with fused score and status
        """
        logger.debug(f"Fusing grades for {our.game_id}: our={our.score}, ai={ai.score}")
        
        # Calculate precisions (inverse variances)
        our_precision = self._calculate_precision(our.confidence)
        ai_precision = self._calculate_precision(ai.confidence)
        
        # Total precision
        total_precision = our_precision + ai_precision
        
        if total_precision < 1e-10:
            logger.warning(f"Very low total precision for {our.game_id}, using equal weighting")
            total_precision = 2.0
            our_precision = 1.0
            ai_precision = 1.0
        
        # Precision-weighted fused score
        fused_score = (
            our.score * our_precision + 
            ai.score * ai_precision
        ) / total_precision
        
        # Uncertainty propagation: variance = 1 / total_precision
        variance = 1.0 / total_precision
        
        # Delta between grades
        delta = abs(our.score - ai.score)
        
        # Determine convergence status
        status = self._determine_status(delta, variance)
        
        # Combined confidence
        combined_confidence = self._calculate_combined_confidence(
            our.confidence, ai.confidence, delta
        )
        
        # Combined edge (weighted average)
        combined_edge = (
            our.edge_percent * our_precision +
            ai.edge_percent * ai_precision
        ) / total_precision
        
        logger.info(
            f"Fusion complete for {our.game_id}: "
            f"score={fused_score:.3f}, status={status.value}, "
            f"variance={variance:.3f}, delta={delta:.3f}"
        )
        
        return Convergence(
            game_id=our.game_id,
            sport=our.sport,
            market=our.market,
            selection=our.selection,
            score=fused_score,
            status=status,
            variance=variance,
            delta=delta,
            our_process=our,
            ai_process=ai,
            confidence=combined_confidence,
            edge_percent=combined_edge
        )
    
    def _calculate_precision(self, confidence: float) -> float:
        """
        Calculate precision from confidence.
        
        Precision = confidence² (higher confidence = lower variance = more precision)
        """
        safe_confidence = max(confidence, self.params.min_confidence)
        return safe_confidence ** 2
    
    def _determine_status(self, delta: float, variance: float) -> ConvergenceStatus:
        """
        Determine convergence status based on delta and variance.
        
        LOCK: High confidence agreement (tight delta, low variance)
        ALIGNED: General agreement (moderate delta)
        DIVERGENT: Disagreement (large delta)
        CONFLICT: Strong disagreement (very large delta)
        """
        if delta < self.params.lock_delta_threshold and variance < self.params.lock_variance_threshold:
            return ConvergenceStatus.LOCK
        elif delta < self.params.aligned_threshold:
            return ConvergenceStatus.ALIGNED
        elif delta < self.params.divergent_threshold:
            return ConvergenceStatus.DIVERGENT
        else:
            return ConvergenceStatus.CONFLICT
    
    def _calculate_combined_confidence(
        self, 
        our_confidence: float, 
        ai_confidence: float,
        delta: float
    ) -> float:
        """
        Calculate combined confidence accounting for agreement.
        
        When grades agree closely, confidence increases.
        When grades diverge, confidence decreases.
        """
        # Base combined confidence (geometric mean for independence assumption)
        base_confidence = (our_confidence * ai_confidence) ** 0.5
        
        # Agreement bonus/penalty
        if delta < 0.5:
            agreement_factor = 1.1  # 10% boost for strong agreement
        elif delta < 1.0:
            agreement_factor = 1.05  # 5% boost for good agreement
        elif delta < 1.5:
            agreement_factor = 1.0  # No change
        elif delta < 2.0:
            agreement_factor = 0.9  # 10% penalty for mild disagreement
        else:
            agreement_factor = 0.75  # 25% penalty for strong disagreement
        
        return min(base_confidence * agreement_factor, 1.0)
    
    def batch_fuse(
        self, 
        pairs: list[Tuple[EngineGrade, AIGrade]]
    ) -> list[Convergence]:
        """
        Fuse multiple grade pairs efficiently.
        
        Args:
            pairs: List of (engine_grade, ai_grade) tuples
            
        Returns:
            List of Convergence results
        """
        logger.info(f"Batch fusing {len(pairs)} grade pairs")
        results = []
        for our, ai in pairs:
            try:
                convergence = self.fuse(our, ai)
                results.append(convergence)
            except Exception as e:
                logger.error(f"Failed to fuse grades for {our.game_id}: {e}")
                # Continue with other pairs
        
        logger.info(f"Batch fusion complete: {len(results)}/{len(pairs)} successful")
        return results
    
    def calculate_agreement_metrics(
        self, 
        convergences: list[Convergence]
    ) -> dict:
        """
        Calculate aggregate agreement metrics across convergences.
        
        Returns dict with:
        - agreement_rate: % of LOCK + ALIGNED
        - avg_delta: Mean absolute difference
        - avg_variance: Mean uncertainty
        - conflict_rate: % of CONFLICT status
        """
        if not convergences:
            return {
                "agreement_rate": 0.0,
                "avg_delta": 0.0,
                "avg_variance": 0.0,
                "conflict_rate": 0.0
            }
        
        total = len(convergences)
        lock_count = sum(1 for c in convergences if c.status == ConvergenceStatus.LOCK)
        aligned_count = sum(1 for c in convergences if c.status == ConvergenceStatus.ALIGNED)
        conflict_count = sum(1 for c in convergences if c.status == ConvergenceStatus.CONFLICT)
        
        avg_delta = sum(c.delta for c in convergences) / total
        avg_variance = sum(c.variance for c in convergences) / total
        
        return {
            "agreement_rate": (lock_count + aligned_count) / total,
            "lock_rate": lock_count / total,
            "conflict_rate": conflict_count / total,
            "avg_delta": avg_delta,
            "avg_variance": avg_variance,
            "total_convergences": total
        }


def fuse_grades(our: EngineGrade, ai: AIGrade) -> Convergence:
    """
    Convenience function for one-off fusion.
    
    Args:
        our: Engine grade from our process
        ai: AI grade from AI process
        
    Returns:
        Convergence result
    """
    engine = ConvergenceEngine()
    return engine.fuse(our, ai)
