"""
Feedback dataset builder for ML training.

Converts model_feedback DB records into training data (X, y) pairs
for scikit-learn models.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np

from heiman.ai.feature_extractor import FeatureExtractor, FeatureGroup

logger = logging.getLogger(__name__)


class FeedbackDataset:
    """
    Builds training datasets from the model_feedback table.

    Each feedback record contains:
        - input_features: raw input to the model
        - predicted_output: what the model predicted
        - actual_output: ground truth (if user provided feedback)
        - feedback_type: correct/incorrect/uncertain/manual_override

    For training, we use records where actual_output is available
    (i.e., user corrected the prediction).
    """

    def __init__(self, feedback_collector=None):
        from heiman.ai.self_learning_system import FeedbackCollector
        self._collector = feedback_collector or FeedbackCollector()

    def build_comfort_dataset(
        self,
        min_samples: int = 10,
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Build (X, y) for comfort evaluation model.

        X: feature vectors from extract_comfort_features
        y: comfort score (0-100), extracted from actual_output

        If actual_output is unavailable, falls back to predicted_output
        as a proxy (using the rule-based evaluator's scores).
        """
        feedback = self._collector.get_feedback_by_model(
            "comfort_evaluator", limit=5000
        )

        X_list, y_list = [], []

        for record in feedback:
            input_feats = record.get("input_features", {})
            actual = record.get("actual_output") or {}
            predicted = record.get("predicted_output") or {}

            # Try actual_output first, then predicted as fallback
            score = actual.get("score") or predicted.get("score")
            if score is None:
                continue

            # Extract features from the input_features stored in feedback
            features = FeatureExtractor.extract_comfort_features(
                temperature=input_feats.get("temperature"),
                humidity=input_feats.get("humidity"),
                co2=input_feats.get("co2"),
                pm25=input_feats.get("pm25"),
                hcho=input_feats.get("hcho"),
                current_time=self._parse_timestamp(record.get("timestamp")),
            )

            try:
                X_list.append(FeatureExtractor.comfort_features_to_array(features))
                y_list.append(float(score))
            except (ValueError, KeyError) as e:
                logger.debug("Skipping feedback record: %s", e)
                continue

        if len(X_list) < min_samples:
            logger.warning(
                "[FeedbackDataset] Insufficient comfort data: %d < %d",
                len(X_list), min_samples,
            )
            return None, None

        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.float32)
        logger.info(
            "[FeedbackDataset] Built comfort dataset: %d samples", len(X_list)
        )
        return X, y

    def build_anomaly_dataset(
        self,
        min_samples: int = 20,
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Build (X, y) for anomaly detection model.

        y: 1 if anomaly detected, 0 if no anomaly.
        """
        feedback = self._collector.get_feedback_by_model(
            "anomaly_detector", limit=5000
        )

        X_list, y_list = [], []

        for record in feedback:
            input_feats = record.get("input_features", {})
            predicted = record.get("predicted_output", {})
            actual = record.get("actual_output") or {}

            has_anomaly = actual.get("has_anomaly")
            if has_anomaly is None:
                has_anomaly = predicted.get("has_anomaly")

            device_data = input_feats.get("properties", {})
            device_data["type"] = input_feats.get("device_type", "")
            device_data["id"] = input_feats.get("device", "")

            features = FeatureExtractor.extract_anomaly_features(device_data)

            X_list.append(np.array(
                [features[name] for name in FeatureExtractor.ANOMALY_FEATURE_NAMES],
                dtype=np.float32,
            ))
            y_list.append(1.0 if has_anomaly else 0.0)

        if len(X_list) < min_samples:
            logger.warning(
                "[FeedbackDataset] Insufficient anomaly data: %d < %d",
                len(X_list), min_samples,
            )
            return None, None

        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.float32)
        logger.info(
            "[FeedbackDataset] Built anomaly dataset: %d samples, "
            "anomaly ratio=%.2f",
            len(X_list), y.mean(),
        )
        return X, y

    def build_behavior_dataset(
        self,
        min_samples: int = 20,
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Build (X, y) for behavior recognition model.

        y: encoded activity label (integer 0-10).
        """
        from heiman.ai.feature_extractor import FeatureExtractor

        feedback = self._collector.get_feedback_by_model(
            "behavior_recognizer", limit=5000
        )

        X_list, y_list = [], []

        for record in feedback:
            predicted = record.get("predicted_output", {})
            actual = record.get("actual_output") or {}

            activity_str = actual.get("activity") or predicted.get("activity")
            if activity_str is None:
                continue

            activity_encoded = FeatureExtractor.ACTIVITY_ENCODING.get(activity_str)
            if activity_encoded is None:
                continue

            # Behavior features would need device_data from feedback
            # For now, extract from input_features
            input_feats = record.get("input_features", {})
            devices = input_feats.get("devices", [])
            room_id = input_feats.get("room_id")

            features = FeatureExtractor.extract_behavior_features(
                devices, room_id,
                current_time=self._parse_timestamp(record.get("timestamp")),
            )

            X_list.append(np.array(
                [features[name] for name in FeatureExtractor.BEHAVIOR_FEATURE_NAMES],
                dtype=np.float32,
            ))
            y_list.append(float(activity_encoded))

        if len(X_list) < min_samples:
            logger.warning(
                "[FeedbackDataset] Insufficient behavior data: %d < %d",
                len(X_list), min_samples,
            )
            return None, None

        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.float32)
        logger.info(
            "[FeedbackDataset] Built behavior dataset: %d samples", len(X_list)
        )
        return X, y

    def build_decision_dataset(
        self,
        min_samples: int = 20,
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Build (X, y) for decision engine model.

        y: encoded action type (integer).
        """
        feedback = self._collector.get_feedback_by_model(
            "decision_engine", limit=5000
        )

        # Action encoding
        action_map = {
            "none": 0, "alarm": 1, "alert": 2, "adjust_environment": 3,
            "prepare_home": 4, "welcome_home": 5, "secure_home": 6,
            "leave_home": 7, "emergency_adjust": 8,
        }

        X_list, y_list = [], []

        for record in feedback:
            predicted = record.get("predicted_output", {})
            actual = record.get("actual_output") or {}

            action_str = actual.get("action") or predicted.get("action")
            if action_str is None:
                continue

            action_encoded = action_map.get(action_str)
            if action_encoded is None:
                continue

            input_feats = record.get("input_features", {})
            context = {
                "anomalies": input_feats.get("anomalies", []),
                "comfort": input_feats.get("comfort", {}),
                "activity": input_feats.get("activity", {}),
                "device_data": input_feats.get("device_data", []),
            }

            features = FeatureExtractor.extract_decision_features(context)

            X_list.append(np.array(
                [features[name] for name in FeatureExtractor.DECISION_FEATURE_NAMES],
                dtype=np.float32,
            ))
            y_list.append(float(action_encoded))

        if len(X_list) < min_samples:
            logger.warning(
                "[FeedbackDataset] Insufficient decision data: %d < %d",
                len(X_list), min_samples,
            )
            return None, None

        X = np.array(X_list, dtype=np.float32)
        y = np.array(y_list, dtype=np.float32)
        logger.info(
            "[FeedbackDataset] Built decision dataset: %d samples", len(X_list)
        )
        return X, y

    def get_total_samples(self, model_name: str) -> int:
        """Get total feedback count for a model."""
        return self._collector.get_feedback_count_by_model(model_name)

    @staticmethod
    def _parse_timestamp(ts: Optional[str]) -> Optional[datetime]:
        """Parse ISO timestamp string to datetime."""
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00").split("+")[0])
        except (ValueError, TypeError):
            return None

    @staticmethod
    def train_test_split(
        X: np.ndarray,
        y: np.ndarray,
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Simple train/test split without sklearn dependency."""
        np.random.seed(random_state)
        n = len(X)
        indices = np.random.permutation(n)
        split_idx = int(n * (1 - test_size))

        train_idx = indices[:split_idx]
        test_idx = indices[split_idx:]

        return X[train_idx], X[test_idx], y[train_idx], y[test_idx]
