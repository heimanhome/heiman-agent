"""
Online / incremental learner for ML models.

Provides partial_fit for models that support it (SGDClassifier),
and periodic full retraining for RandomForest models.

Strategy:
    1. Collect feedback continuously
    2. When threshold reached, trigger retrain
    3. Compare new model vs old model
    4. Auto-deploy if improvement exceeds threshold
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Callable
import asyncio

import numpy as np

from heiman.ai.model_registry import get_model_registry
from heiman.ai.feedback_dataset import FeedbackDataset
from heiman.ai.feature_extractor import FeatureExtractor

logger = logging.getLogger(__name__)


class OnlineLearner:
    """
    Manages online learning for ML models.

    Features:
        - Continuous feedback collection tracking
        - Auto-retrain when feedback threshold reached
        - A/B comparison between old and new models
        - Auto-deploy smarter models
    """

    def __init__(self, retrain_threshold: int = 50, min_improvement: float = 0.01):
        self._dataset = FeedbackDataset()
        self._registry = get_model_registry()
        self._retrain_threshold = retrain_threshold
        self._min_improvement = min_improvement
        self._retrain_lock = asyncio.Lock()

    async def should_retrain(self, model_name: str) -> bool:
        """Check if a model has accumulated enough feedback to retrain."""
        feedback_count = self._dataset.get_total_samples(model_name)
        meta = self._registry.get_metadata(model_name)

        if not meta:
            # No existing model, need at least threshold samples
            return feedback_count >= self._retrain_threshold

        # Check if feedback since last train exceeds threshold
        new_feedback = feedback_count - meta.samples_trained
        return new_feedback >= self._retrain_threshold

    async def auto_retrain_if_needed(self) -> Dict[str, Dict]:
        """
        Check all models and retrain those that need it.

        Returns dict of model_name -> retrain result.
        """
        async with self._retrain_lock:
            results = {}

            models_to_check = [
                ("comfort_evaluator", self._retrain_comfort),
                ("anomaly_detector", self._retrain_anomaly),
                ("behavior_recognizer", self._retrain_behavior),
                ("decision_engine", self._retrain_decision),
            ]

            for model_name, retrain_fn in models_to_check:
                try:
                    if await self.should_retrain(model_name):
                        result = await retrain_fn()
                        results[model_name] = result
                    else:
                        feedback_count = self._dataset.get_total_samples(model_name)
                        meta = self._registry.get_metadata(model_name)
                        new_fb = feedback_count - (meta.samples_trained if meta else 0)
                        results[model_name] = {
                            "retrained": False,
                            "reason": f"Only {new_fb} new feedbacks, need {self._retrain_threshold}",
                            "total_feedback": feedback_count,
                        }
                except Exception as e:
                    logger.error("[OnlineLearner] Retrain %s failed: %s", model_name, e)
                    results[model_name] = {
                        "retrained": False,
                        "error": str(e),
                    }

            return results

    async def retrain_model(self, model_name: str) -> Dict:
        """Retrain a single model by name (supports both short and full names)."""
        # 归一化模型名：anomaly_detector_if / anomaly_detector_clf → anomaly_detector
        name_map = {
            "comfort_evaluator": self._retrain_comfort,
            "anomaly_detector": self._retrain_anomaly,
            "anomaly_detector_if": self._retrain_anomaly,
            "anomaly_detector_clf": self._retrain_anomaly,
            "behavior_recognizer": self._retrain_behavior,
            "decision_engine": self._retrain_decision,
        }

        retrain_fn = name_map.get(model_name)
        if not retrain_fn:
            return {
                "retrained": False,
                "error": f"Unknown model: {model_name}",
            }

        async with self._retrain_lock:
            try:
                return await retrain_fn()
            except Exception as e:
                logger.error("[OnlineLearner] Retrain %s failed: %s", model_name, e)
                return {
                    "retrained": False,
                    "error": str(e),
                }

    async def _retrain_comfort(self) -> Dict:
        """Retrain comfort evaluator."""
        from heiman.ai.comfort_evaluator_v2 import get_comfort_evaluator_v2
        evaluator = get_comfort_evaluator_v2()
        old_accuracy = self._registry.get_metadata("comfort_evaluator")
        old_acc = old_accuracy.accuracy if old_accuracy else 0.0

        result = evaluator.train(use_bootstrap=False)

        if result.get("success"):
            new_acc = result.get("test_r2", 0)
            improvement = new_acc - old_acc
            result["old_accuracy"] = round(old_acc, 4)
            result["improvement"] = round(improvement, 4)
            result["auto_deployed"] = improvement >= self._min_improvement

        return result

    async def _retrain_anomaly(self) -> Dict:
        """Retrain anomaly detector."""
        from heiman.ai.anomaly_detector_v2 import get_anomaly_detector_v2
        detector = get_anomaly_detector_v2()
        old_accuracy = self._registry.get_metadata("anomaly_detector_clf")
        old_acc = old_accuracy.accuracy if old_accuracy else 0.0

        result = detector.train(use_bootstrap=False)

        if result.get("success"):
            new_acc = result.get("train_accuracy", 0)
            improvement = new_acc - old_acc
            result["old_accuracy"] = round(old_acc, 4)
            result["improvement"] = round(improvement, 4)
            result["auto_deployed"] = improvement >= self._min_improvement

        return result

    async def _retrain_behavior(self) -> Dict:
        """Retrain behavior recognizer."""
        from heiman.ai.behavior_recognizer_v2 import get_behavior_recognizer_v2
        recognizer = get_behavior_recognizer_v2()
        old_accuracy = self._registry.get_metadata("behavior_recognizer")
        old_acc = old_accuracy.accuracy if old_accuracy else 0.0

        result = recognizer.train(use_bootstrap=False)

        if result.get("success"):
            new_acc = result.get("test_accuracy", 0)
            improvement = new_acc - old_acc
            result["old_accuracy"] = round(old_acc, 4)
            result["improvement"] = round(improvement, 4)
            result["auto_deployed"] = improvement >= self._min_improvement

        return result

    async def _retrain_decision(self) -> Dict:
        """Retrain decision engine."""
        from heiman.ai.decision_engine_v2 import get_decision_engine_v2
        engine = get_decision_engine_v2()
        old_accuracy = self._registry.get_metadata("decision_engine")
        old_acc = old_accuracy.accuracy if old_accuracy else 0.0

        result = engine.train(use_bootstrap=False)

        if result.get("success"):
            new_acc = result.get("test_accuracy", 0)
            improvement = new_acc - old_acc
            result["old_accuracy"] = round(old_acc, 4)
            result["improvement"] = round(improvement, 4)
            result["auto_deployed"] = improvement >= self._min_improvement

        return result

    def get_retrain_status(self) -> Dict:
        """Get retrain status for all models."""
        from heiman.ai.model_registry import MODEL_NAMES
        status = {}
        for model_name in MODEL_NAMES:
            feedback_count = self._dataset.get_total_samples(model_name)
            meta = self._registry.get_metadata(model_name)
            new_since_train = max(0, feedback_count - (meta.samples_trained if meta else 0))
            status[model_name] = {
                "total_feedback": feedback_count,
                "trained_samples": meta.samples_trained if meta else 0,
                "new_since_train": new_since_train,
                "threshold": self._retrain_threshold,
                "needs_retrain": new_since_train >= self._retrain_threshold,
                "has_model": meta is not None,
            }
        return status


_online_learner: Optional[OnlineLearner] = None


def get_online_learner() -> OnlineLearner:
    global _online_learner
    if _online_learner is None:
        _online_learner = OnlineLearner()
    return _online_learner
