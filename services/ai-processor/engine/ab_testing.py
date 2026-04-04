"""
A/B Testing framework for prompts and models.
"""
import json
import logging
import os
import random
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict

from models import ABTestConfig, GradeRequest, ModelProvider

logger = logging.getLogger(__name__)


@dataclass
class ABTestResult:
    test_id: str
    variant: str
    pick_id: str
    grade_score: float
    confidence: float
    timestamp: datetime
    metadata: Dict[str, Any]


class ABTestManager:
    """Manages A/B tests for prompts and models."""
    
    def __init__(self, storage_path: str = "ab_tests.json"):
        self.storage_path = storage_path
        self.tests: Dict[str, ABTestConfig] = {}
        self.results: List[ABTestResult] = []
        self._load_tests()
    
    def _load_tests(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    for test_data in data.get('tests', []):
                        test = ABTestConfig(**test_data)
                        self.tests[test.test_id] = test
            except Exception as e:
                logger.warning(f"Failed to load A/B tests: {e}")
    
    def _save_tests(self):
        try:
            data = {
                'tests': [asdict(t) for t in self.tests.values()],
                'saved_at': datetime.utcnow().isoformat()
            }
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to save A/B tests: {e}")
    
    def create_test(
        self,
        name: str,
        variant_a: str,
        variant_b: str,
        traffic_split: float = 0.5,
        metric: str = "grade_accuracy",
        duration_days: int = 14
    ) -> str:
        test_id = f"test_{name.lower().replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d')}"
        test = ABTestConfig(
            test_id=test_id,
            name=name,
            variant_a=variant_a,
            variant_b=variant_b,
            traffic_split=traffic_split,
            metric=metric,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=duration_days),
            status="running"
        )
        self.tests[test_id] = test
        self._save_tests()
        logger.info(f"Created A/B test: {test_id}")
        return test_id
    
    def get_variant(self, test_id: str, user_id: Optional[str] = None) -> Optional[str]:
        test = self.tests.get(test_id)
        if not test or test.status != "running":
            return None
        
        if datetime.utcnow() > test.end_date:
            test.status = "completed"
            self._save_tests()
            return None
        
        if user_id:
            hash_val = hash(f"{test_id}:{user_id}") % 100
            return test.variant_a if hash_val < (test.traffic_split * 100) else test.variant_b
        
        return test.variant_a if random.random() < test.traffic_split else test.variant_b
    
    def assign_variant(self, request: GradeRequest) -> Optional[str]:
        for test_id, test in self.tests.items():
            if test.status == "running":
                variant = self.get_variant(test_id, request.pick.id)
                if variant:
                    request.ab_test_variant = f"{test_id}:{variant}"
                    return variant
        return None
    
    def record_result(self, result: ABTestResult):
        self.results.append(result)
        logger.info(f"Recorded A/B result: {result.test_id} variant={result.variant}")
    
    def get_test_stats(self, test_id: str) -> Dict[str, Any]:
        test = self.tests.get(test_id)
        if not test:
            return {}
        
        variant_a_results = [r for r in self.results if r.test_id == test_id and r.variant == test.variant_a]
        variant_b_results = [r for r in self.results if r.test_id == test_id and r.variant == test.variant_b]
        
        def calc_stats(results: List[ABTestResult]) -> Dict[str, float]:
            if not results:
                return {"count": 0, "avg_grade": 0, "avg_confidence": 0}
            return {
                "count": len(results),
                "avg_grade": sum(r.grade_score for r in results) / len(results),
                "avg_confidence": sum(r.confidence for r in results) / len(results),
            }
        
        return {
            "test_id": test_id,
            "name": test.name,
            "status": test.status,
            "variant_a": calc_stats(variant_a_results),
            "variant_b": calc_stats(variant_b_results),
        }
    
    def list_active_tests(self) -> List[ABTestConfig]:
        return [t for t in self.tests.values() if t.status == "running"]


class ABTestTracker:
    """Tracks outcomes for A/B test analysis."""
    
    def __init__(self, storage_path: str = "ab_outcomes.json"):
        self.storage_path = storage_path
        self.outcomes: Dict[str, Dict[str, Any]] = {}
        self._load_outcomes()
    
    def _load_outcomes(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    self.outcomes = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load outcomes: {e}")
    
    def _save_outcomes(self):
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.outcomes, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save outcomes: {e}")
    
    def record_outcome(self, pick_id: str, variant: str, won: bool, profit: float = 0.0):
        key = f"{pick_id}:{variant}"
        self.outcomes[key] = {
            "pick_id": pick_id,
            "variant": variant,
            "won": won,
            "profit": profit,
            "timestamp": datetime.utcnow().isoformat()
        }
        self._save_outcomes()
    
    def get_variant_performance(self, test_id: str) -> Dict[str, Any]:
        test_prefix = f"{test_id}:"
        
        variant_a_wins = []
        variant_b_wins = []
        
        for key, outcome in self.outcomes.items():
            if key.startswith(test_prefix):
                if "variant_a" in key:
                    variant_a_wins.append(outcome)
                elif "variant_b" in key:
                    variant_b_wins.append(outcome)
        
        def summarize(results: List[Dict]) -> Dict[str, Any]:
            if not results:
                return {"count": 0, "wins": 0, "win_rate": 0, "total_profit": 0}
            wins = sum(1 for r in results if r.get("won"))
            profit = sum(r.get("profit", 0) for r in results)
            return {
                "count": len(results),
                "wins": wins,
                "win_rate": wins / len(results),
                "total_profit": profit,
            }
        
        return {
            "variant_a": summarize(variant_a_wins),
            "variant_b": summarize(variant_b_wins),
        }


# Global instances
_test_manager: Optional[ABTestManager] = None
_outcome_tracker: Optional[ABTestTracker] = None


def get_test_manager() -> ABTestManager:
    global _test_manager
    if _test_manager is None:
        _test_manager = ABTestManager()
    return _test_manager


def get_outcome_tracker() -> ABTestTracker:
    global _outcome_tracker
    if _outcome_tracker is None:
        _outcome_tracker = ABTestTracker()
    return _outcome_tracker
