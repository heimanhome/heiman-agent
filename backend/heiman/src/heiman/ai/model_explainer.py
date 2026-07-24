"""
Model explainability and interpretability (Phase 4).

Provides feature importance analysis, permutation importance,
and SHAP-like explanation for model predictions.

Without heavy SHAP dependency, uses:
    1. Built-in feature_importances_ from tree-based models
    2. Permutation importance (model-agnostic)
    3. PDP (Partial Dependence) approximation
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

import numpy as np

logger = logging.getLogger(__name__)


class ModelExplainer:
    """
    Explain ML model predictions.

    Methods:
        - Feature importance (built-in)
        - Permutation importance (score drop when shuffling a feature)
        - Top contributing features for a single prediction
    """

    def __init__(self):
        pass

    def explain_prediction(
        self,
        model: Any,
        feature_names: List[str],
        X: np.ndarray,
        prediction_idx: int = 0,
    ) -> Dict:
        """
        Explain a single prediction.

        For RandomForest models, uses feature contribution approximation
        by comparing leaf paths.
        """
        X_single = X[prediction_idx:prediction_idx+1].copy()

        prediction = None
        if hasattr(model, "predict"):
            prediction = model.predict(X_single)[0]
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X_single)[0]
        else:
            proba = None

        # Permutation-based feature importance for this single prediction
        baseline = None
        if hasattr(model, "predict_proba"):
            baseline = float(model.predict_proba(X_single)[0].max())
        else:
            baseline = float(model.predict(X_single)[0])

        contributions = []
        for i, name in enumerate(feature_names):
            X_perturbed = X_single.copy()
            X_perturbed[0, i] = np.random.permutation(X[:, i])[0]

            if hasattr(model, "predict_proba"):
                new_score = float(model.predict_proba(X_perturbed)[0].max())
            else:
                new_score = float(model.predict(X_perturbed)[0])

            delta = baseline - new_score
            contributions.append({
                "feature": name,
                "value": round(float(X_single[0, i]), 4),
                "importance": round(delta, 6),
                "absolute_importance": round(abs(delta), 6),
            })

        contributions.sort(key=lambda x: x["absolute_importance"], reverse=True)

        return {
            "prediction": prediction.tolist() if hasattr(prediction, "tolist") else prediction,
            "confidence": round(float(proba.max()), 4) if proba is not None else None,
            "predicted_class": int(prediction) if proba is not None else None,
            "top_features": contributions[:10],
            "feature_count": len(feature_names),
        }

    def compute_permutation_importance(
        self,
        model: Any,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        n_repeats: int = 5,
    ) -> List[Dict]:
        """
        Compute permutation feature importance.

        For each feature, shuffle its values and measure accuracy drop.
        """
        from sklearn.metrics import accuracy_score, r2_score

        is_classifier = hasattr(model, "predict_proba")
        baseline_pred = model.predict(X)

        if is_classifier and len(y.shape) <= 1:
            baseline_score = accuracy_score(y, baseline_pred)
        else:
            baseline_score = r2_score(y, baseline_pred)

        importances = []
        for i, name in enumerate(feature_names):
            scores = []
            for _ in range(n_repeats):
                X_permuted = X.copy()
                np.random.shuffle(X_permuted[:, i])
                permuted_pred = model.predict(X_permuted)

                if is_classifier and len(y.shape) <= 1:
                    scores.append(accuracy_score(y, permuted_pred))
                else:
                    scores.append(r2_score(y, permuted_pred))

            mean_drop = baseline_score - np.mean(scores)
            std_drop = np.std(scores)

            importances.append({
                "feature": name,
                "importance": round(mean_drop, 6),
                "std": round(std_drop, 6),
                "positive": mean_drop > 0,  # True = feature is useful
            })

        importances.sort(key=lambda x: x["importance"], reverse=True)
        return importances

    def get_feature_importance_report(
        self,
        model: Any,
        feature_names: List[str],
        X: Optional[np.ndarray] = None,
        y: Optional[np.ndarray] = None,
    ) -> Dict:
        """Generate a comprehensive feature importance report."""
        built_in = []
        if hasattr(model, "feature_importances_"):
            importances = list(zip(feature_names, model.feature_importances_))
            importances.sort(key=lambda x: x[1], reverse=True)
            built_in = [
                {"feature": name, "importance": round(float(imp), 6)}
                for name, imp in importances
            ]

        permutation = None
        if X is not None and y is not None and len(X) >= 50:
            try:
                permutation = self.compute_permutation_importance(
                    model, X, y, feature_names, n_repeats=3,
                )
            except Exception as e:
                logger.warning("[Explainer] Permutation importance failed: %s", e)

        return {
            "model_type": type(model).__name__,
            "n_features": len(feature_names),
            "built_in_importance": built_in[:10] if built_in else [],
            "permutation_importance": permutation[:10] if permutation else [],
            "top_features_agreement": self._compare_rankings(built_in[:5], permutation[:5]) if built_in and permutation else 0,
        }

    def _compare_rankings(self, built_in: List, permutation: List) -> float:
        """Compare agreement between two feature importance rankings (Jaccard similarity)."""
        bi_names = {item["feature"] for item in built_in}
        pi_names = {item["feature"] for item in permutation}
        if not bi_names or not pi_names:
            return 0.0
        intersection = bi_names & pi_names
        union = bi_names | pi_names
        return len(intersection) / len(union)


    def explain_model(
        self,
        model_name: str,
        n_examples: int = 3,
    ) -> Dict:
        """Explain a specific model with examples and feature importance."""
        from heiman.ai.model_registry import get_model_registry
        from heiman.ai.feedback_dataset import FeedbackDataset

        registry = get_model_registry()
        model = registry.load_model(model_name)
        metadata = registry.get_metadata(model_name)
        dataset = FeedbackDataset()

        if model is None:
            return {"error": f"Model '{model_name}' not found"}

        feature_names = metadata.feature_names if metadata else []

        # Get built-in importance
        report = self.get_feature_importance_report(model, feature_names)

        # Get sample predictions
        sample_predictions = []
        if metadata and len(feature_names) > 0:
            # Try to load some real data for examples
            try:
                build_fn = {
                    "comfort_evaluator": dataset.build_comfort_dataset,
                    "behavior_recognizer": dataset.build_behavior_dataset,
                    "decision_engine": dataset.build_decision_dataset,
                }.get(model_name)

                if build_fn:
                    X, y = build_fn(min_samples=1)
                    if X is not None and len(X) >= n_examples:
                        for i in range(min(n_examples, len(X))):
                            explanation = self.explain_prediction(
                                model, feature_names, X, i,
                            )
                            sample_predictions.append(explanation)
            except Exception as e:
                logger.debug("[Explainer] Sample predictions failed: %s", e)

        return {
            "model_name": model_name,
            "model_type": report["model_type"],
            "n_features": report["n_features"],
            "accuracy": metadata.accuracy if metadata else None,
            "samples_trained": metadata.samples_trained if metadata else 0,
            "feature_importance": report["built_in_importance"],
            "sample_predictions": sample_predictions,
        }


_explainer: Optional[ModelExplainer] = None


def get_explainer() -> ModelExplainer:
    global _explainer
    if _explainer is None:
        _explainer = ModelExplainer()
    return _explainer
