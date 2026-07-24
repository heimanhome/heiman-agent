"""
ML-based anomaly detector (V2).

Replaces the rule-based AnomalyDetector with a two-stage ML pipeline:
    1. IsolationForest for unsupervised outlier/anomaly detection
    2. RandomForestClassifier for anomaly type classification

Bootstrap training from rule-based evaluator labels.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List

import numpy as np

from heiman.ai.anomaly_detector import (
    AnomalyDetector, AnomalyType, AnomalyResult,
)
from heiman.ai.feature_extractor import FeatureExtractor
from heiman.ai.model_registry import get_model_registry, ModelRegistry

logger = logging.getLogger(__name__)

ANOMALY_TYPE_ENCODING = {
    "device_offline": 0,
    "environment": 1,
    "battery_low": 2,
    "behavior": 3,
    "combination": 4,
    "no_anomaly": 5,
}

ANOMALY_TYPE_NAMES = {v: k for k, v in ANOMALY_TYPE_ENCODING.items()}


class AnomalyDetectorV2:
    """
    ML-powered anomaly detector.

    Pipeline:
        1. IsolationForest screens for any anomaly (score)
        2. RandomForestClassifier determines anomaly type
        3. Rule-based fallback if ML unavailable
    """

    def __init__(self, model_registry: Optional[ModelRegistry] = None):
        self._registry = model_registry or get_model_registry()
        self._if_model = None       # IsolationForest
        self._clf_model = None      # RandomForestClassifier
        self._rule_detector = AnomalyDetector()

        self._load_models()

    @property
    def is_ml_ready(self) -> bool:
        return self._if_model is not None and self._clf_model is not None

    def _load_models(self):
        try:
            self._if_model = self._registry.load_model("anomaly_detector_if")
            self._clf_model = self._registry.load_model("anomaly_detector_clf")
            if self._if_model and self._clf_model:
                meta = self._registry.get_metadata("anomaly_detector_clf")
                if meta:
                    logger.info(
                        "[AnomalyV2] Loaded ML models v%d (accuracy=%.4f, samples=%d)",
                        meta.version, meta.accuracy or 0, meta.samples_trained,
                    )
        except Exception as e:
            logger.warning("[AnomalyV2] Failed to load models: %s", e)

    def detect(self, device_data: Dict) -> Optional[AnomalyResult]:
        # Critical sensors ALWAYS use rule-based (safety first)
        device_type = device_data.get("type", "").lower()
        if any(t in device_type for t in ["smoke", "gas", "co"]):
            return self._rule_detector.detect(device_data)

        if self.is_ml_ready:
            try:
                return self._detect_ml(device_data)
            except Exception as e:
                logger.warning("[AnomalyV2] ML detection failed: %s", e)

        return self._rule_detector.detect(device_data)

    def _detect_ml(self, device_data: Dict) -> Optional[AnomalyResult]:
        features = FeatureExtractor.extract_anomaly_features(device_data)
        X = np.array([
            [features[name] for name in FeatureExtractor.ANOMALY_FEATURE_NAMES]
        ], dtype=np.float32)

        # Quick rule-based pre-check for obvious anomalies
        temperature = device_data.get("temperature")
        humidity = device_data.get("humidity")
        co2 = device_data.get("co2")
        pm25 = device_data.get("pm25")
        battery = device_data.get("battery")
        status = device_data.get("status", "").lower()

        obvious_anomaly_type = None
        if status == "offline":
            obvious_anomaly_type = "device_offline"
        elif battery is not None and battery < 10:
            obvious_anomaly_type = "battery_low"
        elif temperature is not None and (temperature > 38 or temperature < 8):
            obvious_anomaly_type = "environment"
        elif humidity is not None and (humidity > 92 or humidity < 8):
            obvious_anomaly_type = "environment"

        # Stage 1: IsolationForest outlier detection
        if_pred = self._if_model.predict(X)[0]
        if_score = self._if_model.decision_function(X)[0]

        # Combine: IF indicates anomaly OR obvious rule hit
        is_anomaly = (if_pred == -1 or if_score < 0.0) or obvious_anomaly_type is not None

        if not is_anomaly:
            return None

        # Stage 2: Classify anomaly type
        if obvious_anomaly_type:
            anomaly_type_str = obvious_anomaly_type
            max_proba = 0.95
        else:
            type_idx = int(self._clf_model.predict(X)[0])
            type_proba = self._clf_model.predict_proba(X)[0]
            max_proba = float(type_proba[type_idx]) if len(type_proba) > type_idx else 0.5
            anomaly_type_str = ANOMALY_TYPE_NAMES.get(type_idx, "environment")

        try:
            anomaly_type = AnomalyType(anomaly_type_str)
        except ValueError:
            anomaly_type = AnomalyType.ENVIRONMENT

        # Determine severity
        severity = "warning"
        if if_score < -0.15 or obvious_anomaly_type in ("battery_low", "device_offline"):
            severity = "critical" if obvious_anomaly_type == "device_offline" else "warning"
        if battery is not None and battery < 5:
            severity = "critical"

        # Build message
        messages = []
        temperature = device_data.get("temperature")
        humidity = device_data.get("humidity")
        co2 = device_data.get("co2")
        pm25 = device_data.get("pm25")
        battery = device_data.get("battery")

        if anomaly_type == AnomalyType.ENVIRONMENT:
            if temperature is not None and (temperature < 15 or temperature > 35):
                messages.append(f"温度异常 ({temperature}°C)")
            if humidity is not None and (humidity < 20 or humidity > 80):
                messages.append(f"湿度异常 ({humidity}%RH)")
            if co2 is not None and co2 > 1500:
                messages.append(f"CO2过高 ({co2} ppm)")
            if pm25 is not None and pm25 > 75:
                messages.append(f"PM2.5超标 ({pm25})")
        elif anomaly_type == AnomalyType.BATTERY_LOW:
            messages.append(f"电量低 ({battery}%)")
        elif anomaly_type == AnomalyType.DEVICE_OFFLINE:
            messages.append("设备离线")
        elif anomaly_type == AnomalyType.BEHAVIOR:
            messages.append(f"异常行为 (score={if_score:.4f})")

        if not messages:
            messages.append(f"ML检测异常 (score={if_score:.4f})")

        return AnomalyResult(
            anomaly_type=anomaly_type,
            severity=severity,
            message=f"设备 {device_data.get('name', '未知')}: {', '.join(messages)}",
            device_id=device_data.get("id"),
            device_name=device_data.get("name"),
            room_id=device_data.get("room"),
            details={
                "ml_score": round(float(if_score), 4),
                "ml_confidence": round(max_proba, 4),
                "anomaly_type_ml": anomaly_type_str,
                "temperature": temperature,
                "humidity": humidity,
                "co2": co2,
                "pm25": pm25,
            },
        )

    def detect_batch(self, devices_data: List[Dict]) -> List[AnomalyResult]:
        results = []
        for device_data in devices_data:
            result = self.detect(device_data)
            if result:
                results.append(result)
        return results

    def detect_behavior_anomaly(self, events, current_time=None):
        """Always use rule-based for behavior anomaly detection (safety)."""
        return self._rule_detector.detect_behavior_anomaly(events, current_time)

    def train(self, use_bootstrap: bool = True) -> Dict:
        """Train the anomaly detection models."""
        from heiman.ai.feedback_dataset import FeedbackDataset

        dataset = FeedbackDataset()
        X, y_anomaly = dataset.build_anomaly_dataset(min_samples=20)
        training_source = "real_feedback" if (X is not None and len(X) >= 50) else "bootstrap"

        if X is None or (use_bootstrap and len(X) < 50):
            X, y_anomaly = self._generate_bootstrap_data(n_samples=500)
            training_source = "bootstrap"
            logger.info("[AnomalyV2] Using bootstrap data: %d samples", len(X))

        if X is None or len(X) < 10:
            return {"success": False, "error": "Insufficient data"}

        # Train IsolationForest (unsupervised — no accuracy score)
        from sklearn.ensemble import IsolationForest

        if_model = IsolationForest(
            n_estimators=100,
            contamination=0.1,
            max_samples="auto",
            random_state=42,
            n_jobs=-1,
        )
        if_model.fit(X)

        # Generate anomaly types for classifier
        y_type = self._generate_type_labels(X, y_anomaly)

        # Train RandomForestClassifier with honest train/test split
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split

        X_train, X_test, y_train_type, y_test_type = train_test_split(
            X, y_type, test_size=0.2, random_state=42, stratify=y_type,
        )

        clf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=12,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1,
        )
        clf_model.fit(X_train, y_train_type)

        # Honest test-set evaluation
        train_acc = float(clf_model.score(X_train, y_train_type))
        test_acc = float(clf_model.score(X_test, y_test_type))
        anomaly_ratio = float(y_anomaly.mean()) if y_anomaly is not None else 0.1

        # Save IF model (unsupervised — no accuracy, use contamination as metric)
        if_version = self._registry.save_model(
            model=if_model,
            model_name="anomaly_detector_if",
            model_type="IsolationForest",
            feature_names=FeatureExtractor.ANOMALY_FEATURE_NAMES,
            samples_trained=len(X),
            training_source=training_source,
            params={
                "contamination": 0.1,
                "n_estimators": 100,
                "strategy": "IF_outlier + rule_precheck",
                "note": "IsolationForest is unsupervised — no accuracy metric applies",
            },
        )
        clf_version = self._registry.save_model(
            model=clf_model,
            model_name="anomaly_detector_clf",
            model_type="RandomForestClassifier",
            feature_names=FeatureExtractor.ANOMALY_FEATURE_NAMES,
            accuracy=test_acc,
            samples_trained=len(X_train),
            training_source=training_source,
            params={
                "if_version": if_version,
                "n_estimators": 100,
                "max_depth": 12,
                "train_accuracy": train_acc,
                "test_accuracy": test_acc,
                "test_samples": len(X_test),
            },
        )

        self._if_model = if_model
        self._clf_model = clf_model

        return {
            "success": True,
            "if_version": if_version,
            "clf_version": clf_version,
            "model_type": "IsolationForest + RandomForestClassifier",
            "samples": len(X),
            "anomaly_ratio": round(anomaly_ratio, 4),
            "training_source": training_source,
            "train_accuracy": round(train_acc, 4),
            "test_accuracy": round(test_acc, 4),
            "if_note": "IsolationForest is unsupervised — no accuracy score",
        }

    def _generate_bootstrap_data(self, n_samples: int = 500):
        """
        Generate bootstrap training data from rule-based detector.

        Uses realistic distributions:
            - 80% normal devices (temp ~ N(24, 4), battery > 50%)
            - 20% anomalous devices (extreme temps, low battery, offline)
        """
        np.random.seed(42)
        X_list, y_list = [], []

        device_types = [
            "sensor_temp", "sensor_humidity", "sensor_air", "smoke_sensor",
            "gas_sensor", "water_sensor", "door_sensor", "motion_sensor",
        ]

        n_normal = int(n_samples * 0.8)
        n_anomaly = n_samples - n_normal

        # Generate normal devices
        for _ in range(n_normal):
            dtype = np.random.choice(device_types)
            hour = np.random.randint(0, 24)
            device = {
                "type": dtype,
                "status": "online",
                "battery": int(np.clip(np.random.normal(85, 10), 30, 100)),
                "id": f"normal_{_}",
                "name": f"设备{_}",
                "room": np.random.choice(["bedroom", "kitchen", "living", "bathroom"]),
            }

            if "sensor" in dtype:
                if np.random.random() > 0.2:
                    device["temperature"] = float(np.clip(np.random.normal(24, 3), 10, 40))
                if np.random.random() > 0.2:
                    device["humidity"] = float(np.clip(np.random.normal(50, 10), 20, 80))
                if np.random.random() > 0.5:
                    device["co2"] = int(np.clip(np.random.normal(600, 200), 300, 2500))
                if np.random.random() > 0.5:
                    device["pm25"] = int(np.clip(np.random.normal(30, 20), 0, 500))

            features = FeatureExtractor.extract_anomaly_features(device)
            X_list.append(np.array(
                [features[name] for name in FeatureExtractor.ANOMALY_FEATURE_NAMES],
                dtype=np.float32,
            ))
            y_list.append(0.0)  # Normal

        # Generate anomalous devices
        anomaly_types = ["offline", "low_battery", "high_temp", "high_co2", "sensor_trigger"]
        for i in range(n_anomaly):
            atype = np.random.choice(anomaly_types)
            dtype = np.random.choice(device_types)
            device = {
                "type": dtype,
                "status": "online",
                "battery": int(np.clip(np.random.normal(85, 10), 30, 100)),
                "id": f"anomaly_{i}",
                "name": f"异常设备{i}",
                "room": np.random.choice(["bedroom", "kitchen", "living", "bathroom"]),
            }

            if atype == "offline":
                device["status"] = "offline"
                device["battery"] = 0
            elif atype == "low_battery":
                device["battery"] = int(np.random.uniform(1, 10))
            elif atype == "high_temp":
                device["temperature"] = float(np.random.uniform(36, 45))
                device["humidity"] = float(np.random.uniform(10, 30))
            elif atype == "high_co2":
                device["temperature"] = float(np.clip(np.random.normal(24, 3), 15, 35))
                device["co2"] = int(np.random.uniform(1500, 3000))
            elif atype == "sensor_trigger":
                if "smoke" in dtype:
                    device["smokeState"] = 1
                elif "gas" in dtype:
                    device["gasState"] = 1
                elif "water" in dtype:
                    device["waterState"] = 1

            features = FeatureExtractor.extract_anomaly_features(device)
            X_list.append(np.array(
                [features[name] for name in FeatureExtractor.ANOMALY_FEATURE_NAMES],
                dtype=np.float32,
            ))
            y_list.append(1.0)  # Anomaly

        return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32)

    def _generate_type_labels(self, X: np.ndarray, y_anomaly: np.ndarray) -> np.ndarray:
        """Generate anomaly type labels for classification training."""
        np.random.seed(42)
        y_type = np.full(len(X), ANOMALY_TYPE_ENCODING["no_anomaly"], dtype=int)

        for i, is_anomaly in enumerate(y_anomaly):
            if is_anomaly > 0.5:
                # Parse features to determine likely anomaly type
                features = X[i]
                # Feature indices: see ANOMALY_FEATURE_NAMES
                temp_out = features[8]   # temp_out_of_range
                humid_out = features[9]  # humidity_out_of_range
                co2_exc = features[10]   # co2_exceeded
                pm25_exc = features[11]  # pm25_exceeded
                battery = features[2]    # battery_normalized
                offline = features[0]    # is_online (0=offline, 1=online)
                smoke = features[20]     # smoke_active
                gas = features[21]       # gas_active
                water = features[22]     # water_active

                if smoke > 0.5 or gas > 0.5 or water > 0.5:
                    y_type[i] = ANOMALY_TYPE_ENCODING["behavior"]
                elif offline < 0.5:
                    y_type[i] = ANOMALY_TYPE_ENCODING["device_offline"]
                elif battery < 0.2:
                    y_type[i] = ANOMALY_TYPE_ENCODING["battery_low"]
                elif temp_out > 0.5 or humid_out > 0.5 or co2_exc > 0.5 or pm25_exc > 0.5:
                    y_type[i] = ANOMALY_TYPE_ENCODING["environment"]
                else:
                    y_type[i] = ANOMALY_TYPE_ENCODING["behavior"]

        return y_type

    def get_model_info(self) -> Dict:
        meta_if = self._registry.get_metadata("anomaly_detector_if")
        meta_clf = self._registry.get_metadata("anomaly_detector_clf")
        return {
            "ml_ready": self.is_ml_ready,
            "model_type": "IsolationForest + RandomForestClassifier" if self.is_ml_ready else "rule_based",
            "if_version": meta_if.version if meta_if else None,
            "clf_version": meta_clf.version if meta_clf else None,
            "accuracy": meta_clf.accuracy if meta_clf else None,
            "samples_trained": meta_clf.samples_trained if meta_clf else 0,
        }


_anomaly_detector_v2: Optional[AnomalyDetectorV2] = None


def get_anomaly_detector_v2() -> AnomalyDetectorV2:
    global _anomaly_detector_v2
    if _anomaly_detector_v2 is None:
        _anomaly_detector_v2 = AnomalyDetectorV2()
    return _anomaly_detector_v2
