"""
Convergence Engine Module

Core engine for Bayesian fusion, confidence calculation, pick generation,
and portfolio optimization.
"""

from .fusion import ConvergenceEngine, fuse_grades
from .confidence import ConfidenceCalculator, calculate_convergence_confidence
from .pick_generator import PickGenerator, generate_pick, kelly_size
from .portfolio import PortfolioOptimizer, optimize_portfolio

__all__ = [
    "ConvergenceEngine",
    "fuse_grades",
    "ConfidenceCalculator",
    "calculate_convergence_confidence",
    "PickGenerator",
    "generate_pick",
    "kelly_size",
    "PortfolioOptimizer",
    "optimize_portfolio",
]
