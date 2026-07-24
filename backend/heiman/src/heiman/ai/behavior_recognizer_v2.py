"""
ML-based behavior recognizer (V2).

Replaces the rule-based BehaviorRecognizer with a RandomForestClassifier
for 11-class activity recognition from multi-room device state data.

Bootstrap training from rule-based recognizer labels.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List

import numpy as np

from heiman.ai.behavior_recognizer import (
    BehaviorRecognizer, ActivityType, ActivityResult,
)
from heiman.ai.feature_extractor import FeatureExtractor
from heiman.ai.model_registry import get_model_registry, ModelRegistry

logger = logging.getLogger(__name__)

# Activity encoding matches feature_extractor.ACTIVITY_ENCODING
ACTIVITY_NAMES = {
    0: ActivityType.SLEEPING,
    1: ActivityType.AWAKING,
    2: ActivityType.WORKING,
    3: ActivityType.COOKING,
    4: ActivityType.EATING,
    5: ActivityType.LEAVING,
    6: ActivityType.RETURNING,
    7: ActivityType.WATCHING_TV,
    8: ActivityType.SHOWERING,
    9: ActivityType.CLEANING,
    10: ActivityType.UNKNOWN,
}


class BehaviorRecognizerV2:
    """
    ML-powered behavior recognizer.

    Uses RandomForestClassifier to predict user activity from
    room-level device states and temporal features.

    Fallback: Rule-based BehaviorRecognizer when model unavailable.
    """

    def __init__(self, model_registry: Optional[ModelRegistry] = None):
        self._registry = model_registry or get_model_registry()
        self._ml_model = None
        self._rule_recognizer = BehaviorRecognizer()

        self._load_model()

    @property
    def is_ml_ready(self) -> bool:
        return self._ml_model is not None

    def _load_model(self):
        try:
            model = self._registry.load_model("behavior_recognizer")
            if model is not None:
                self._ml_model = model
                meta = self._registry.get_metadata("behavior_recognizer")
                if meta:
                    logger.info(
                        "[BehaviorV2] Loaded ML model v%d (accuracy=%.4f, samples=%d)",
                        meta.version, meta.accuracy or 0, meta.samples_trained,
                    )
        except Exception as e:
            logger.warning("[BehaviorV2] Failed to load model: %s", e)

    def recognize_current_activity(
        self,
        devices_data: List[Dict],
        room_id: Optional[str] = None,
        current_time: Optional[datetime] = None,
    ) -> ActivityResult:
        """Recognize current activity using ML with rule-based fallback."""
        if self.is_ml_ready:
            try:
                return self._recognize_ml(devices_data, room_id, current_time)
            except Exception as e:
                logger.warning("[BehaviorV2] ML recognition failed: %s", e)

        return self._rule_recognizer.recognize_current_activity(
            devices_data, room_id, current_time,
        )

    def _recognize_ml(
        self,
        devices_data: List[Dict],
        room_id: Optional[str],
        current_time: Optional[datetime],
    ) -> ActivityResult:
        features = FeatureExtractor.extract_behavior_features(
            devices_data, room_id, current_time,
        )
        X = np.array([
            [features[name] for name in FeatureExtractor.BEHAVIOR_FEATURE_NAMES]
        ], dtype=np.float32)

        pred_idx = int(self._ml_model.predict(X)[0])
        proba = self._ml_model.predict_proba(X)[0]
        confidence = float(proba[pred_idx]) if pred_idx < len(proba) else 0.5

        activity = ACTIVITY_NAMES.get(pred_idx, ActivityType.UNKNOWN)

        # Try to determine primary room
        primary_room = room_id
        if not primary_room and activity in (ActivityType.SLEEPING, ActivityType.AWAKING):
            primary_room = "bedroom"
        elif activity in (ActivityType.COOKING, ActivityType.EATING):
            primary_room = "kitchen"
        elif activity == ActivityType.WORKING:
            primary_room = "study"
        elif activity == ActivityType.SHOWERING:
            primary_room = "bathroom"
        elif activity == ActivityType.WATCHING_TV:
            primary_room = "living_room"

        return ActivityResult(
            activity=activity,
            confidence=confidence,
            room_id=primary_room,
            details={
                "ml_confidence": round(confidence, 4),
                "top3_classes": self._get_top_classes(proba, k=3),
            },
        )

    def _get_top_classes(self, proba: np.ndarray, k: int = 3) -> List[Dict]:
        indices = np.argsort(proba)[::-1][:k]
        return [
            {
                "activity": ACTIVITY_NAMES.get(int(i), ActivityType.UNKNOWN).value,
                "confidence": round(float(proba[i]), 4),
            }
            for i in indices
        ]

    def get_daily_routine(self, events, date=None):
        """Use rule-based for daily routine analysis."""
        return self._rule_recognizer.get_daily_routine(events, date)

    def predict_next_activity(self, devices_data, current_activity):
        """Use rule-based for next activity prediction."""
        return self._rule_recognizer.predict_next_activity(devices_data, current_activity)

    def train(self, use_bootstrap: bool = True) -> Dict:
        """Train the behavior recognition model."""
        from heiman.ai.feedback_dataset import FeedbackDataset

        dataset = FeedbackDataset()
        X, y = dataset.build_behavior_dataset(min_samples=20)
        training_source = "real_feedback" if (X is not None and len(X) >= 50) else "bootstrap"

        if X is None or (use_bootstrap and len(X) < 50):
            X, y = self._generate_bootstrap_data(n_samples=600)
            training_source = "bootstrap"
            logger.info("[BehaviorV2] Using bootstrap data: %d samples", len(X))

        if X is None or len(X) < 10:
            return {"success": False, "error": "Insufficient data"}

        # Train/test split
        X_train, X_test, y_train, y_test = FeedbackDataset.train_test_split(
            X, y, test_size=0.2,
        )

        from sklearn.ensemble import RandomForestClassifier

        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)

        train_acc = float(model.score(X_train, y_train))
        test_acc = float(model.score(X_test, y_test))

        # Save
        version = self._registry.save_model(
            model=model,
            model_name="behavior_recognizer",
            model_type="RandomForestClassifier",
            feature_names=FeatureExtractor.BEHAVIOR_FEATURE_NAMES,
            accuracy=test_acc,
            samples_trained=len(X),
            training_source=training_source,
            params={
                "n_estimators": 200,
                "max_depth": 15,
                "train_accuracy": train_acc,
                "test_accuracy": test_acc,
                "num_classes": len(model.classes_),
            },
        )

        self._ml_model = model

        # Per-class stats
        class_stats = {}
        for cls_idx in model.classes_:
            cls_name = ACTIVITY_NAMES.get(int(cls_idx), ActivityType.UNKNOWN).value
            cls_mask = y_test == cls_idx
            if cls_mask.any():
                cls_acc = float(model.score(X_test[cls_mask], y_test[cls_mask]))
                cls_count = int(cls_mask.sum())
                class_stats[cls_name] = {
                    "accuracy": round(cls_acc, 4),
                    "samples": cls_count,
                }

        return {
            "success": True,
            "version": version,
            "model_type": "RandomForestClassifier",
            "samples": len(X),
            "training_source": training_source,
            "num_classes": len(model.classes_),
            "train_accuracy": round(train_acc, 4),
            "test_accuracy": round(test_acc, 4),
            "per_class": class_stats,
        }

    def _generate_bootstrap_data(self, n_samples: int = 600):
        """
        Generate bootstrap training data from rule-based recognizer.

        Uses time-correlated activity generation:
            - Night (22-6): sleeping
            - Morning (6-9): awaking, eating
            - Day (9-12): working, cleaning
            - Noon (12-14): cooking, eating
            - Afternoon (14-18): working
            - Evening (18-22): watching_tv, eating
        """
        np.random.seed(42)
        X_list, y_list = [], []

        # Activity-time distribution: [(activity, start_hour, end_hour, weight)]
        time_activity_map = [
            ("sleeping",    22, 6,  0.7),
            ("awaking",     6,  9,  0.4),
            ("eating",      7,  9,  0.4),
            ("working",     9,  12, 0.5),
            ("working",     14, 18, 0.5),
            ("cooking",     11, 13, 0.4),
            ("cooking",     17, 19, 0.4),
            ("eating",      12, 14, 0.5),
            ("eating",      18, 20, 0.5),
            ("leaving",     7,  9,  0.2),
            ("returning",   17, 20, 0.2),
            ("watching_tv", 19, 23, 0.5),
            ("showering",   7,  9,  0.2),
            ("showering",   21, 23, 0.2),
            ("cleaning",    9,  11, 0.3),
            ("cleaning",    14, 16, 0.3),
        ]

        rooms = ["bedroom", "study", "kitchen", "living_room", "bathroom"]
        activity_room_default = {
            "sleeping": "bedroom",
            "awaking": "bedroom",
            "working": "study",
            "cooking": "kitchen",
            "eating": "kitchen",
            "leaving": "living_room",
            "returning": "living_room",
            "watching_tv": "living_room",
            "showering": "bathroom",
            "cleaning": "living_room",
            "unknown": "living_room",
        }

        for _ in range(n_samples):
            # Weighted random hour
            while True:
                hour = np.random.randint(0, 24)
                valid_activities = [
                    (a, w) for a, sh, eh, w in time_activity_map
                    if (sh < eh and sh <= hour < eh) or (sh > eh and (hour >= sh or hour < eh))
                ]
                if valid_activities and np.random.random() < sum(w for _, w in valid_activities) / len(time_activity_map):
                    break

            if valid_activities:
                activities, weights = zip(*valid_activities) if valid_activities else ([], [])
                total_w = sum(weights)
                probs = [w/total_w for w in weights]
                activity_str = np.random.choice(activities, p=probs)
            else:
                activity_str = "unknown"

            active_room = activity_room_default.get(activity_str, "living_room")

            # Generate devices
            devices = []
            for room in rooms:
                room_key = {"bedroom": "bed", "study": "study", "kitchen": "kitchen",
                           "living_room": "living", "bathroom": "bath"}.get(room, room)

                is_active = room == active_room

                light_on = 0
                if is_active and np.random.random() < 0.8:
                    light_on = 1
                elif not is_active and np.random.random() < 0.05:
                    light_on = 1  # Occasional lights left on
                devices.append({"type": "light", "switchState": light_on, "room": room_key, "name": f"{room}_light"})

                motion_on = 0
                if is_active and np.random.random() < 0.7:
                    motion_on = 1
                devices.append({"type": "motion", "switchState": motion_on, "room": room_key, "name": f"{room}_motion"})

            # Kitchen cooking
            if activity_str == "cooking" and np.random.random() < 0.8:
                devices.append({"type": "smoke", "smokeState": 1, "room": "kitchen", "name": "kitchen_smoke"})

            # TV
            if activity_str == "watching_tv" and np.random.random() < 0.8:
                devices.append({"type": "tv", "switchState": 1, "room": "living", "name": "tv"})

            # Door open when leaving/returning
            if activity_str in ("leaving", "returning") and np.random.random() < 0.7:
                devices.append({"type": "door", "switchState": 1, "room": "main", "name": "door"})

            features = FeatureExtractor.extract_behavior_features(
                devices, current_time=datetime(2025, 1, 1, hour, 0),
            )
            X_list.append(np.array(
                [features[name] for name in FeatureExtractor.BEHAVIOR_FEATURE_NAMES],
                dtype=np.float32,
            ))

            activity_encoded = FeatureExtractor.ACTIVITY_ENCODING.get(activity_str, 10)
            y_list.append(float(activity_encoded))

        return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32)

    def get_model_info(self) -> Dict:
        meta = self._registry.get_metadata("behavior_recognizer")
        return {
            "ml_ready": self.is_ml_ready,
            "model_type": "RandomForestClassifier" if self.is_ml_ready else "rule_based",
            "version": meta.version if meta else None,
            "accuracy": meta.accuracy if meta else None,
            "samples_trained": meta.samples_trained if meta else 0,
        }


_behavior_recognizer_v2: Optional[BehaviorRecognizerV2] = None


def get_behavior_recognizer_v2() -> BehaviorRecognizerV2:
    global _behavior_recognizer_v2
    if _behavior_recognizer_v2 is None:
        _behavior_recognizer_v2 = BehaviorRecognizerV2()
    return _behavior_recognizer_v2
