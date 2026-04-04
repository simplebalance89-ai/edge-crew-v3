import asyncio
import logging
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from collections import defaultdict
import statistics

from models import ModelProvider, SportType, ModelPrediction, AIGrade, Pick, GradeLevel, GradeRequest
from models.clients import get_client_for_provider
from models.router import get_router
from engine.prompts import PromptManager

logger = logging.getLogger(__name__)


@dataclass
class EnsembleConfig:
    min_models_required: int = 2
    max_models: int = 5
    confidence_threshold: float = 0.6
    outlier_threshold: float = 20.0
    timeout_ms: int = 30000
    enable_outlier_detection: bool = True


class WeightedEnsemble:
    DEFAULT_WEIGHTS = {
        ModelProvider.CLAUDE: 0.25,
        ModelProvider.GPT5: 0.25,
        ModelProvider.GROK: 0.20,
        ModelProvider.DEEPSEEK: 0.15,
        ModelProvider.KIMI: 0.15,
    }
    
    SPORT_ADJUSTMENTS = {
        SportType.NFL: {ModelProvider.CLAUDE: 0.05, ModelProvider.GPT5: 0.03},
        SportType.NBA: {ModelProvider.GPT5: 0.05, ModelProvider.CLAUDE: 0.03},
        SportType.NCAAB: {ModelProvider.DEEPSEEK: 0.05, ModelProvider.KIMI: 0.03},
        SportType.MLB: {ModelProvider.GPT5: 0.04, ModelProvider.GROK: 0.03},
        SportType.NHL: {ModelProvider.DEEPSEEK: 0.04, ModelProvider.GPT5: 0.02},
        SportType.SOCCER: {ModelProvider.KIMI: 0.05, ModelProvider.DEEPSEEK: 0.03},
        SportType.UFC: {ModelProvider.CLAUDE: 0.05, ModelProvider.GROK: 0.03},
    }
    
    def __init__(self, config: Optional[EnsembleConfig] = None):
        self.config = config or EnsembleConfig()
        self.weights = self._load_weights()
        self.accuracy_history: Dict[ModelProvider, List[bool]] = defaultdict(list)
    
    def _load_weights(self) -> Dict[ModelProvider, float]:
        weights_file = os.getenv("ENSEMBLE_WEIGHTS_FILE", "weights.json")
        if os.path.exists(weights_file):
            try:
                with open(weights_file, 'r') as f:
                    data = json.load(f)
                    return {ModelProvider(k): v for k, v in data.items()}
            except Exception as e:
                logger.warning(f"Failed to load weights: {e}")
        return self.DEFAULT_WEIGHTS.copy()
    
    def _save_weights(self):
        weights_file = os.getenv("ENSEMBLE_WEIGHTS_FILE", "weights.json")
        try:
            with open(weights_file, 'w') as f:
                json.dump({k.value: v for k, v in self.weights.items()}, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save weights: {e}")
    
    def get_weights_for_sport(self, sport: SportType) -> Dict[ModelProvider, float]:
        base = self.weights.copy()
        adj = self.SPORT_ADJUSTMENTS.get(sport, {})
        adjusted = {p: base.get(p, 0.15) + adj.get(p, 0.0) for p in base}
        total = sum(adjusted.values())
        return {k: v / total for k, v in adjusted.items()} if total > 0 else base
    
    def weighted_average(self, predictions: List[ModelPrediction], sport: SportType) -> Tuple[float, GradeLevel]:
        if not predictions:
            return 50.0, GradeLevel.C
        weights = self.get_weights_for_sport(sport)
        total_weight = sum(weights.get(p.model, 0.15) for p in predictions)
        if total_weight == 0:
            avg_score = sum(p.score for p in predictions) / len(predictions)
        else:
            avg_score = sum(p.score * weights.get(p.model, 0.15) for p in predictions) / total_weight
        return avg_score, self._score_to_grade(avg_score)
    
    def _score_to_grade(self, score: float) -> GradeLevel:
        if score >= 97: return GradeLevel.A_PLUS
        elif score >= 93: return GradeLevel.A
        elif score >= 90: return GradeLevel.A_MINUS
        elif score >= 87: return GradeLevel.B_PLUS
        elif score >= 83: return GradeLevel.B
        elif score >= 80: return GradeLevel.B_MINUS
        elif score >= 77: return GradeLevel.C_PLUS
        elif score >= 73: return GradeLevel.C
        elif score >= 70: return GradeLevel.C_MINUS
        elif score >= 67: return GradeLevel.D_PLUS
        elif score >= 63: return GradeLevel.D
        elif score >= 60: return GradeLevel.D_MINUS
        else: return GradeLevel.F
    
    def calculate_confidence(self, predictions: List[ModelPrediction]) -> float:
        if len(predictions) < 2:
            return predictions[0].confidence if predictions else 0.5
        scores = [p.score for p in predictions]
        confidences = [p.confidence for p in predictions]
        try:
            std_dev = statistics.stdev(scores)
        except statistics.StatisticsError:
            std_dev = 0
        agreement = max(0.0, 1.0 - (std_dev / 50.0))
        avg_confidence = sum(confidences) / len(confidences)
        coverage = min(len(predictions) / 5, 1.0)
        combined = (agreement * 0.5) + (avg_confidence * 0.3) + (coverage * 0.2)
        return round(min(max(combined, 0.0), 1.0), 3)
    
    def detect_outliers(self, predictions: List[ModelPrediction]) -> Tuple[List[ModelPrediction], List[ModelPrediction]]:
        if len(predictions) < 3 or not self.config.enable_outlier_detection:
            return predictions, []
        median = statistics.median([p.score for p in predictions])
        valid, outliers = [], []
        for pred in predictions:
            if abs(pred.score - median) > self.config.outlier_threshold:
                outliers.append(pred)
                logger.warning(f"Outlier detected: {pred.model} score={pred.score}")
            else:
                valid.append(pred)
        return (predictions, []) if len(valid) < self.config.min_models_required else (valid, outliers)


class EnsembleEngine:
    def __init__(self, config: Optional[EnsembleConfig] = None):
        self.config = config or EnsembleConfig()
        self.ensemble = WeightedEnsemble(config)
        self.prompt_manager = PromptManager()
        self.router = get_router()
    
    async def grade(self, request: GradeRequest, timeout_ms: Optional[int] = None) -> AIGrade:
        start_time = datetime.utcnow()
        timeout = timeout_ms or self.config.timeout_ms
        pick = request.pick
        sport = pick.game.sport
        
        models = request.required_models or await self.router.get_models_for_request(
            sport=sport, required_count=self.config.max_models
        )
        if len(models) < self.config.min_models_required:
            raise ValueError(f"Insufficient models: {len(models)} < {self.config.min_models_required}")
        
        prompt = self.prompt_manager.build_grading_prompt(pick)
        system_prompt = self.prompt_manager.get_system_prompt(sport)
        
        predictions = await self._call_models_parallel(models, prompt, system_prompt, sport, timeout)
        valid = [p for p in predictions if not isinstance(p, Exception) and p.error is None]
        failed = [p for p in predictions if isinstance(p, Exception) or p.error is not None]
        
        if len(valid) < self.config.min_models_required:
            raise Exception(f"Insufficient successful predictions: {len(valid)} < {self.config.min_models_required}")
        
        valid, outliers = self.ensemble.detect_outliers(valid)
        consensus_score, grade = self.ensemble.weighted_average(valid, sport)
        confidence = self.ensemble.calculate_confidence(valid)
        
        latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return AIGrade(
            pick_id=pick.id,
            score=round(consensus_score, 2),
            grade=grade,
            confidence=confidence,
            consensus_score=round(consensus_score, 2),
            breakdown={p.model: p.score for p in valid},
            model_predictions=valid,
            reasoning=self._aggregate_reasoning(valid),
            key_factors=self._extract_key_factors(valid),
            red_flags=self._extract_red_flags(valid),
            timestamp=datetime.utcnow(),
            latency_ms=latency_ms,
            models_used=[p.model for p in valid],
            models_failed=[getattr(p, 'model', None) for p in failed if hasattr(p, 'model')],
            ab_test_variant=request.ab_test_variant,
        )
    
    async def _call_models_parallel(
        self, 
        models: List[ModelProvider], 
        prompt: str, 
        system_prompt: Optional[str],
        sport: SportType,
        timeout_ms: int
    ) -> List[Any]:
        async def call_with_timeout(model: ModelProvider):
            try:
                client = get_client_for_provider(model)
                return await asyncio.wait_for(
                    client.grade(prompt, sport, system_prompt),
                    timeout=timeout_ms / 1000 / len(models)
                )
            except asyncio.TimeoutError:
                logger.warning(f"Timeout calling {model}")
                return Exception(f"Timeout after {timeout_ms}ms")
            except Exception as e:
                logger.error(f"Error calling {model}: {e}")
                return e
        
        tasks = [call_with_timeout(m) for m in models]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def _aggregate_reasoning(self, predictions: List[ModelPrediction]) -> str:
        reasonings = [p.reasoning for p in predictions if p.reasoning]
        if not reasonings:
            return "No detailed reasoning available"
        return reasonings[0][:1000]
    
    def _extract_key_factors(self, predictions: List[ModelPrediction]) -> List[str]:
        factors = []
        for p in predictions:
            if p.reasoning:
                lines = p.reasoning.split('\n')
                for line in lines[:3]:
                    if ':' in line or '-' in line:
                        factors.append(line.strip()[:100])
        return list(set(factors))[:5]
    
    def _extract_red_flags(self, predictions: List[ModelPrediction]) -> List[str]:
        red_flags = []
        keywords = ['injur', 'suspension', 'doubt', 'risk', 'concern', 'avoid', 'bad']
        for p in predictions:
            if p.reasoning:
                for keyword in keywords:
                    if keyword in p.reasoning.lower():
                        red_flags.append(f"{p.model.value}: Mentioned {keyword}")
                        break
        return red_flags[:3]
