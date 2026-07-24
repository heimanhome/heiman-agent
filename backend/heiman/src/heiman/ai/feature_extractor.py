"""
Feature extractor for ML models.

Converts raw device data and context into numerical feature vectors
that scikit-learn models can consume.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import numpy as np

logger = logging.getLogger(__name__)


class FeatureGroup(str, Enum):
    """Groups of features for different model types."""
    COMFORT = "comfort"
    ANOMALY = "anomaly"
    BEHAVIOR = "behavior"
    DECISION = "decision"
    RULE = "rule"


class FeatureExtractor:
    """
    Extract structured feature vectors from heterogeneous smart home data.

    Usage:
        extractor = FeatureExtractor()
        features = extractor.extract_comfort_features(temperature=24.5, humidity=55, ...)
        # features is a Dict[str, float] ready for model.predict()
    """

    # --- Comfort evaluation features ---

    COMFORT_FEATURE_NAMES = [
        "temperature",
        "humidity",
        "co2",
        "pm25",
        "hcho",
        "temp_deviation",       # |temperature - 24| (ideal temp deviation)
        "humidity_deviation",   # |humidity - 50| (ideal humidity deviation)
        "co2_normalized",       # co2 / 2000
        "pm25_normalized",      # pm25 / 500
        "hcho_normalized",      # hcho / 1.0
        "hour_sin",             # sin(2*pi*hour/24)
        "hour_cos",             # cos(2*pi*hour/24)
        "day_of_week",          # 0-6
        "is_weekend",           # 0 or 1
        "sensor_count",         # how many sensors provided data
    ]

    @staticmethod
    def extract_comfort_features(
        temperature: Optional[float] = None,
        humidity: Optional[float] = None,
        co2: Optional[int] = None,
        pm25: Optional[int] = None,
        hcho: Optional[float] = None,
        current_time: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """
        Extract features for comfort evaluation model.

        Missing sensor values are filled with -1 (sentinel for "missing").
        """
        now = current_time or datetime.now()
        hour = now.hour

        sensor_count = sum(1 for v in [temperature, humidity, co2, pm25, hcho] if v is not None)

        return {
            "temperature": temperature if temperature is not None else -1.0,
            "humidity": humidity if humidity is not None else -1.0,
            "co2": float(co2) if co2 is not None else -1.0,
            "pm25": float(pm25) if pm25 is not None else -1.0,
            "hcho": hcho if hcho is not None else -1.0,
            "temp_deviation": abs(temperature - 24.0) if temperature is not None else -1.0,
            "humidity_deviation": abs(humidity - 50.0) if humidity is not None else -1.0,
            "co2_normalized": (co2 / 2000.0) if co2 is not None else -1.0,
            "pm25_normalized": (pm25 / 500.0) if pm25 is not None else -1.0,
            "hcho_normalized": (hcho / 1.0) if hcho is not None else -1.0,
            "hour_sin": np.sin(2 * np.pi * hour / 24),
            "hour_cos": np.cos(2 * np.pi * hour / 24),
            "day_of_week": float(now.weekday()),
            "is_weekend": 1.0 if now.weekday() >= 5 else 0.0,
            "sensor_count": float(sensor_count),
        }

    @staticmethod
    def comfort_features_to_array(features: Dict[str, float]) -> np.ndarray:
        """Convert feature dict to numpy array in fixed order."""
        return np.array([features[name] for name in FeatureExtractor.COMFORT_FEATURE_NAMES], dtype=np.float32)

    @staticmethod
    def batch_comfort_features(feature_dicts: List[Dict[str, float]]) -> np.ndarray:
        """Convert list of feature dicts to 2D numpy array."""
        return np.array([
            [d[name] for name in FeatureExtractor.COMFORT_FEATURE_NAMES]
            for d in feature_dicts
        ], dtype=np.float32)

    # --- Anomaly detection features ---

    ANOMALY_FEATURE_NAMES = [
        "is_online",
        "battery_level",
        "battery_normalized",
        "temperature",
        "humidity",
        "co2",
        "pm25",
        "hcho",
        "temp_out_of_range",
        "humidity_out_of_range",
        "co2_exceeded",
        "pm25_exceeded",
        "hcho_exceeded",
        "hour_sin",
        "hour_cos",
        "is_night",
        "is_smoke_sensor",
        "is_gas_sensor",
        "is_water_sensor",
        "is_door_sensor",
        "is_motion_sensor",
        "smoke_active",
        "gas_active",
        "water_active",
        "tamper_active",
        "sensor_life_expired",
        "minutes_since_update",
    ]

    @staticmethod
    def extract_anomaly_features(
        device_data: Dict[str, Any],
        current_time: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """Extract features for anomaly detection model."""
        now = current_time or datetime.now()
        hour = now.hour

        device_type = device_data.get("type", "").lower()

        battery = device_data.get("battery")
        temperature = device_data.get("temperature")
        humidity = device_data.get("humidity")
        co2 = device_data.get("co2")
        pm25 = device_data.get("pm25")
        hcho = device_data.get("hcho")

        # Time since last update
        last_update = device_data.get("lastUpdate", "")
        minutes_since_update = -1.0
        if last_update:
            try:
                dt = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
                minutes_since_update = (now - dt.replace(tzinfo=None)).total_seconds() / 60
            except (ValueError, TypeError):
                pass

        return {
            "is_online": 1.0 if device_data.get("status") == "online" else 0.0,
            "battery_level": float(battery) if battery is not None else 100.0,
            "battery_normalized": (battery / 100.0) if battery is not None else 1.0,
            "temperature": float(temperature) if temperature is not None else -1.0,
            "humidity": float(humidity) if humidity is not None else -1.0,
            "co2": float(co2) if co2 is not None else -1.0,
            "pm25": float(pm25) if pm25 is not None else -1.0,
            "hcho": float(hcho) if hcho is not None else -1.0,
            "temp_out_of_range": 1.0 if temperature is not None and (temperature < 15 or temperature > 35) else 0.0,
            "humidity_out_of_range": 1.0 if humidity is not None and (humidity < 20 or humidity > 80) else 0.0,
            "co2_exceeded": 1.0 if co2 is not None and co2 > 1500 else 0.0,
            "pm25_exceeded": 1.0 if pm25 is not None and pm25 > 75 else 0.0,
            "hcho_exceeded": 1.0 if hcho is not None and hcho > 0.1 else 0.0,
            "hour_sin": np.sin(2 * np.pi * hour / 24),
            "hour_cos": np.cos(2 * np.pi * hour / 24),
            "is_night": 1.0 if hour < 6 or hour >= 22 else 0.0,
            "is_smoke_sensor": 1.0 if "smoke" in device_type else 0.0,
            "is_gas_sensor": 1.0 if "gas" in device_type or "co" in device_type else 0.0,
            "is_water_sensor": 1.0 if "water" in device_type else 0.0,
            "is_door_sensor": 1.0 if "door" in device_type else 0.0,
            "is_motion_sensor": 1.0 if "motion" in device_type else 0.0,
            "smoke_active": 1.0 if device_data.get("smokeState") in (1, 2) else 0.0,
            "gas_active": 1.0 if device_data.get("gasState") in (1, 2) else 0.0,
            "water_active": 1.0 if device_data.get("waterState") == 1 else 0.0,
            "tamper_active": 1.0 if device_data.get("tamperState") == 1 else 0.0,
            "sensor_life_expired": 1.0 if device_data.get("sensorLifeStatus") == 1 else 0.0,
            "minutes_since_update": minutes_since_update,
        }

    @staticmethod
    def batch_anomaly_features(feature_dicts: List[Dict[str, float]]) -> np.ndarray:
        """Convert list of anomaly feature dicts to 2D numpy array."""
        return np.array([
            [d[name] for name in FeatureExtractor.ANOMALY_FEATURE_NAMES]
            for d in feature_dicts
        ], dtype=np.float32)

    # --- Behavior recognition features ---

    BEHAVIOR_FEATURE_NAMES = [
        "hour_sin",
        "hour_cos",
        "day_of_week",
        "is_weekend",
        "is_night",
        "is_morning",
        "is_afternoon",
        "is_evening",
        "bedroom_lights_on",
        "bedroom_motion",
        "study_lights_on",
        "study_motion",
        "kitchen_motion",
        "kitchen_smoke",
        "living_lights_on",
        "living_tv_on",
        "bathroom_motion",
        "any_door_open",
        "all_lights_off",
        "total_motion_devices",
        "total_devices",
    ]

    @staticmethod
    def extract_behavior_features(
        devices_data: List[Dict],
        room_id: Optional[str] = None,
        current_time: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """Extract features for behavior recognition model."""
        now = current_time or datetime.now()
        hour = now.hour

        def in_room(room_key: str) -> List[Dict]:
            return [d for d in devices_data if d.get("room") and room_key in d.get("room", "").lower()]

        bedroom = in_room("bed")
        study = in_room("study")
        kitchen = in_room("kitchen")
        living = in_room("living")
        bathroom = in_room("bath")

        return {
            "hour_sin": np.sin(2 * np.pi * hour / 24),
            "hour_cos": np.cos(2 * np.pi * hour / 24),
            "day_of_week": float(now.weekday()),
            "is_weekend": 1.0 if now.weekday() >= 5 else 0.0,
            "is_night": 1.0 if hour < 6 or hour >= 22 else 0.0,
            "is_morning": 1.0 if 6 <= hour < 12 else 0.0,
            "is_afternoon": 1.0 if 12 <= hour < 18 else 0.0,
            "is_evening": 1.0 if 18 <= hour < 22 else 0.0,
            "bedroom_lights_on": 1.0 if any(d.get("type") == "light" and d.get("switchState") == 1 for d in bedroom) else 0.0,
            "bedroom_motion": 1.0 if any(d.get("type") == "motion" and d.get("switchState") == 1 for d in bedroom) else 0.0,
            "study_lights_on": 1.0 if any(d.get("type") == "light" and d.get("switchState") == 1 for d in study) else 0.0,
            "study_motion": 1.0 if any(d.get("type") == "motion" and d.get("switchState") == 1 for d in study) else 0.0,
            "kitchen_motion": 1.0 if any(d.get("type") == "motion" and d.get("switchState") == 1 for d in kitchen) else 0.0,
            "kitchen_smoke": 1.0 if any(d.get("type") == "smoke" and d.get("smokeState") == 1 for d in kitchen) else 0.0,
            "living_lights_on": 1.0 if any(d.get("type") == "light" and d.get("switchState") == 1 for d in living) else 0.0,
            "living_tv_on": 1.0 if any(d.get("type") == "tv" and d.get("switchState") == 1 for d in living) else 0.0,
            "bathroom_motion": 1.0 if any(d.get("type") == "motion" and d.get("switchState") == 1 for d in bathroom) else 0.0,
            "any_door_open": 1.0 if any(d.get("type") and "door" in d.get("type", "").lower() and d.get("switchState") == 1 for d in devices_data) else 0.0,
            "all_lights_off": 1.0 if all(d.get("switchState") == 0 for d in devices_data if d.get("type") == "light") else 0.0,
            "total_motion_devices": float(sum(1 for d in devices_data if "motion" in d.get("type", "").lower() and d.get("switchState") == 1)),
            "total_devices": float(len(devices_data)),
        }

    @staticmethod
    def batch_behavior_features(feature_dicts: List[Dict[str, float]]) -> np.ndarray:
        """Convert list of behavior feature dicts to 2D numpy array."""
        return np.array([
            [d[name] for name in FeatureExtractor.BEHAVIOR_FEATURE_NAMES]
            for d in feature_dicts
        ], dtype=np.float32)

    # --- Decision features ---

    DECISION_FEATURE_NAMES = [
        "anomaly_count",
        "has_critical_anomaly",
        "has_warning_anomaly",
        "comfort_score",
        "comfort_is_poor",
        "comfort_is_excellent",
        "activity_encoded",
        "hour_sin",
        "hour_cos",
        "day_of_week",
        "is_weekend",
        "is_night",
        "device_count",
        "online_ratio",
    ]

    ACTIVITY_ENCODING = {
        "sleeping": 0, "awaking": 1, "working": 2, "cooking": 3,
        "eating": 4, "leaving": 5, "returning": 6, "watching_tv": 7,
        "showering": 8, "cleaning": 9, "unknown": 10,
    }

    @staticmethod
    def extract_decision_features(context: Dict[str, Any]) -> Dict[str, float]:
        """Extract features for decision engine model."""
        now = datetime.now()
        hour = now.hour

        anomalies = context.get("anomalies", [])
        comfort = context.get("comfort", {})
        activity = context.get("activity", {})
        device_data = context.get("device_data", [])

        critical_count = sum(1 for a in anomalies if a.get("severity") == "critical")
        warning_count = sum(1 for a in anomalies if a.get("severity") == "warning")

        activity_type = activity.get("activity", "unknown")
        activity_encoded = float(FeatureExtractor.ACTIVITY_ENCODING.get(activity_type, 10))

        online_count = sum(1 for d in device_data if d.get("status") == "online")
        online_ratio = online_count / len(device_data) if device_data else 0.0

        return {
            "anomaly_count": float(len(anomalies)),
            "has_critical_anomaly": 1.0 if critical_count > 0 else 0.0,
            "has_warning_anomaly": 1.0 if warning_count > 0 else 0.0,
            "comfort_score": float(comfort.get("score", 50)),
            "comfort_is_poor": 1.0 if comfort.get("level") == "poor" else 0.0,
            "comfort_is_excellent": 1.0 if comfort.get("level") == "excellent" else 0.0,
            "activity_encoded": activity_encoded,
            "hour_sin": np.sin(2 * np.pi * hour / 24),
            "hour_cos": np.cos(2 * np.pi * hour / 24),
            "day_of_week": float(now.weekday()),
            "is_weekend": 1.0 if now.weekday() >= 5 else 0.0,
            "is_night": 1.0 if hour < 6 or hour >= 22 else 0.0,
            "device_count": float(len(device_data)),
            "online_ratio": online_ratio,
        }

    @staticmethod
    def batch_decision_features(feature_dicts: List[Dict[str, float]]) -> np.ndarray:
        """Convert list of decision feature dicts to 2D numpy array."""
        return np.array([
            [d[name] for name in FeatureExtractor.DECISION_FEATURE_NAMES]
            for d in feature_dicts
        ], dtype=np.float32)
