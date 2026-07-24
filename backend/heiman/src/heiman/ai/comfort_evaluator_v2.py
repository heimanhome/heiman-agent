"""
ML-based comfort evaluator (V2).

Replaces the rule-based ComfortEvaluator with a RandomForestRegressor
that learns from user feedback to predict comfort scores.

Architecture:
    1. Initial training: Use rule-based evaluator scores as bootstrap data
    2. Online learning: Fine-tune on real user feedback (actual_output)
    3. Fallback: If ML model unavailable, delegate to rule-based evaluator
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List

import numpy as np

from heiman.ai.comfort_evaluator import (
    ComfortEvaluator, ComfortResult, ComfortLevel,
)
from heiman.ai.feature_extractor import FeatureExtractor
from heiman.ai.model_registry import ModelRegistry, get_model_registry

logger = logging.getLogger(__name__)

# Retrain every N new feedback samples
RETRAIN_INTERVAL = 50


class ComfortEvaluatorV2:
    """
    ML-powered comfort evaluator.

    Uses RandomForestRegressor to predict a comfort score (0-100) from
    environmental sensor data.

    The model considers:
        - temperature, humidity, CO2, PM2.5, HCHO
        - deviations from ideal values
        - time of day / day of week
        - sensor availability count

    Fallback: Delegates to rule-based ComfortEvaluator when model unavailable.
    """

    def __init__(
        self,
        model_registry: Optional[ModelRegistry] = None,
    ):
        self._registry = model_registry or get_model_registry()
        self._ml_model = None
        self._rule_evaluator = ComfortEvaluator()
        self._feedback_since_train = 0

        # Try to load existing model
        self._load_model()

    @property
    def is_ml_ready(self) -> bool:
        """Whether the ML model is loaded and ready."""
        return self._ml_model is not None

    def _load_model(self):
        """Load the ML model from registry."""
        try:
            model = self._registry.load_model("comfort_evaluator")
            if model is not None:
                self._ml_model = model
                meta = self._registry.get_metadata("comfort_evaluator")
                if meta:
                    logger.info(
                        "[ComfortV2] Loaded ML model v%d (accuracy=%.4f, samples=%d)",
                        meta.version, meta.accuracy or 0, meta.samples_trained,
                    )
        except Exception as e:
            logger.warning("[ComfortV2] Failed to load ML model: %s", e)

    def evaluate(
        self,
        temperature: Optional[float] = None,
        humidity: Optional[float] = None,
        co2: Optional[int] = None,
        pm25: Optional[int] = None,
        hcho: Optional[float] = None,
    ) -> ComfortResult:
        """
        Evaluate comfort level using ML model with rule-based fallback.
        """
        # If ML model available, use it
        if self._ml_model is not None:
            try:
                return self._evaluate_ml(temperature, humidity, co2, pm25, hcho)
            except Exception as e:
                logger.warning("[ComfortV2] ML evaluation failed, falling back: %s", e)

        # Fallback to rule-based
        return self._rule_evaluator.evaluate(temperature, humidity, co2, pm25, hcho)

    def _evaluate_ml(
        self,
        temperature: Optional[float],
        humidity: Optional[float],
        co2: Optional[int],
        pm25: Optional[int],
        hcho: Optional[float],
    ) -> ComfortResult:
        """Use ML model for comfort evaluation."""
        features = FeatureExtractor.extract_comfort_features(
            temperature, humidity, co2, pm25, hcho,
        )
        X = FeatureExtractor.comfort_features_to_array(features).reshape(1, -1)

        score = float(self._ml_model.predict(X)[0])
        score = max(0.0, min(100.0, score))  # Clamp to [0, 100]

        # Get per-sensor analysis from rule-based evaluator for suggestions
        rule_result = self._rule_evaluator.evaluate(
            temperature, humidity, co2, pm25, hcho,
        )

        level = self._score_to_level(score)

        return ComfortResult(
            level=level,
            score=round(score),
            temperature=temperature,
            humidity=humidity,
            co2=co2,
            pm25=pm25,
            hcho=hcho,
            temperature_status=rule_result.temperature_status,
            humidity_status=rule_result.humidity_status,
            co2_status=rule_result.co2_status,
            pm25_status=rule_result.pm25_status,
            hcho_status=rule_result.hcho_status,
            suggestions=rule_result.suggestions,
        )

    def evaluate_device(self, device_data: Dict) -> ComfortResult:
        """Evaluate comfort from device data dict."""
        return self.evaluate(
            temperature=device_data.get("temperature"),
            humidity=device_data.get("humidity"),
            co2=device_data.get("co2"),
            pm25=device_data.get("pm25"),
            hcho=device_data.get("hcho"),
        )

    def train(
        self,
        X: Optional[np.ndarray] = None,
        y: Optional[np.ndarray] = None,
        use_bootstrap: bool = True,
    ) -> Dict:
        """
        Train the ML model.

        If X/y provided, uses that data.
        If use_bootstrap=True and no data provided, generates bootstrap data
        from the rule-based evaluator.

        Returns training summary dict.
        """
        from heiman.ai.feedback_dataset import FeedbackDataset

        dataset = FeedbackDataset()
        training_source = "bootstrap"  # default

        if X is None or y is None:
            # Try to get real feedback data first
            X_fb, y_fb = dataset.build_comfort_dataset(min_samples=10)

            if X_fb is not None and len(X_fb) >= 50:
                X, y = X_fb, y_fb
                training_source = "real_feedback"
                logger.info("[ComfortV2] Using real feedback data: %d samples", len(X))
            elif use_bootstrap:
                X, y = self._generate_bootstrap_data(n_samples=500)
                training_source = "bootstrap"
                logger.info("[ComfortV2] Using bootstrap data: %d samples", len(X))
            else:
                return {
                    "success": False,
                    "error": "No training data available",
                    "feedback_samples": len(X_fb) if X_fb is not None else 0,
                }

        if len(X) < 10:
            return {"success": False, "error": f"Insufficient data: {len(X)} samples"}

        # Train/test split
        X_train, X_test, y_train, y_test = FeedbackDataset.train_test_split(
            X, y, test_size=0.2,
        )

        # Build and train model
        from sklearn.ensemble import RandomForestRegressor

        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)

        # Evaluate
        train_score = model.score(X_train, y_train)
        test_score = model.score(X_test, y_test)

        # Save model
        version = self._registry.save_model(
            model=model,
            model_name="comfort_evaluator",
            model_type="RandomForestRegressor",
            feature_names=FeatureExtractor.COMFORT_FEATURE_NAMES,
            accuracy=float(test_score),
            samples_trained=len(X),
            training_source=training_source,
            params={
                "n_estimators": 100,
                "max_depth": 10,
                "train_r2": float(train_score),
                "test_r2": float(test_score),
            },
        )

        # Update in-memory model
        self._ml_model = model
        self._feedback_since_train = 0

        result = {
            "success": True,
            "version": version,
            "model_type": "RandomForestRegressor",
            "samples": len(X),
            "training_source": training_source,
            "train_r2": round(train_score, 4),
            "test_r2": round(test_score, 4),
        }

        # Feature importance
        if hasattr(model, "feature_importances_"):
            importances = list(zip(
                FeatureExtractor.COMFORT_FEATURE_NAMES,
                model.feature_importances_,
            ))
            importances.sort(key=lambda x: x[1], reverse=True)
            result["feature_importance"] = [
                {"feature": name, "importance": round(imp, 4)}
                for name, imp in importances[:10]
            ]

        logger.info(
            "[ComfortV2] Training complete: v%d, train_r2=%.4f, test_r2=%.4f",
            version, train_score, test_score,
        )
        return result

    def _generate_bootstrap_data(self, n_samples: int = 500) -> tuple:
        """
        Generate bootstrap training data using the rule-based evaluator.

        Creates synthetic samples across the full sensor range and labels
        them with rule-based scores.
        """
        np.random.seed(42)

        X_list, y_list = [], []

        for _ in range(n_samples):
            # Random sensor values across realistic ranges
            temp = np.random.uniform(10, 40)
            humidity = np.random.uniform(10, 95)
            co2 = np.random.randint(300, 2500)
            pm25 = np.random.randint(0, 400)
            hcho = np.random.uniform(0.0, 0.3)

            # Sometimes omit sensors (simulating partial data)
            if np.random.random() < 0.1:
                temp = None
            if np.random.random() < 0.1:
                humidity = None
            if np.random.random() < 0.2:
                co2 = None
            if np.random.random() < 0.2:
                pm25 = None
            if np.random.random() < 0.3:
                hcho = None

            # Rule-based evaluation as label
            result = self._rule_evaluator.evaluate(temp, humidity, co2, pm25, hcho)

            features = FeatureExtractor.extract_comfort_features(
                temp, humidity, co2, pm25, hcho,
            )
            X_list.append(FeatureExtractor.comfort_features_to_array(features))
            y_list.append(float(result.score))

        return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32)

    def get_model_info(self) -> Dict:
        """Get information about the current ML model."""
        meta = self._registry.get_metadata("comfort_evaluator")
        all_versions = self._registry.get_all_versions("comfort_evaluator")

        return {
            "ml_ready": self.is_ml_ready,
            "using_ml": self.is_ml_ready,
            "model_type": "RandomForestRegressor" if self.is_ml_ready else "rule_based",
            "current_version": meta.version if meta else None,
            "accuracy": meta.accuracy if meta else None,
            "samples_trained": meta.samples_trained if meta else 0,
            "all_versions": all_versions,
            "feedback_since_train": self._feedback_since_train,
        }

    @staticmethod
    def _score_to_level(score: float) -> ComfortLevel:
        """Map score to comfort level."""
        if score >= 85:
            return ComfortLevel.EXCELLENT
        elif score >= 70:
            return ComfortLevel.GOOD
        elif score >= 40:
            return ComfortLevel.FAIR
        else:
            return ComfortLevel.POOR


# Singleton
_comfort_evaluator_v2: Optional[ComfortEvaluatorV2] = None


def get_comfort_evaluator_v2() -> ComfortEvaluatorV2:
    """Get or create the global ML comfort evaluator."""
    global _comfort_evaluator_v2
    if _comfort_evaluator_v2 is None:
        _comfort_evaluator_v2 = ComfortEvaluatorV2()
    return _comfort_evaluator_v2
