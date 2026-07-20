"""CO level classification model."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any

from heiman.perception.models.sensor_detector import SensorDetector

_LOGGER = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = str(
    Path(__file__).resolve().parent / "co_alert.onnx"
)


class COAlertDetector(SensorDetector):
    INPUT_FEATURES = [
        "co_concentration",
        "temperature",
        "humidity",
        "time_of_day",
        "is_heating_on",
    ]

    OUTPUT_CLASSES = ["safe", "low", "medium", "high", "critical"]

    def __init__(
        self,
        model_path: str = _DEFAULT_MODEL_PATH,
        use_gpu: bool = False,
        num_threads: int | None = None,
        thresholds: Dict[str, float] | None = None,
    ):
        super().__init__(
            model_path=model_path,
            input_features=self.INPUT_FEATURES,
            output_classes=self.OUTPUT_CLASSES,
            use_gpu=use_gpu,
            num_threads=num_threads,
        )
        self.thresholds = thresholds or {
            "safe": 0.0,
            "low": 10.0,
            "medium": 50.0,
            "high": 100.0,
            "critical": 200.0,
        }

    def classify(self, sensor_data: Dict[str, float]) -> Dict[str, Any]:
        result = self.infer(sensor_data)

        if not result.get("success"):
            return result

        class_name = result.get("class", "unknown")
        confidence = result.get("confidence", 0.0)
        co_level = sensor_data.get("co_concentration", 0.0)

        alert_level = self._determine_alert_level(class_name, co_level)

        return {
            **result,
            "alert_level": alert_level,
            "co_level": co_level,
            "recommended_action": self._get_recommended_action(alert_level),
        }

    def _determine_alert_level(self, class_name: str, co_level: float) -> str:
        if class_name == "critical" or co_level >= self.thresholds["critical"]:
            return "critical"
        elif class_name == "high" or co_level >= self.thresholds["high"]:
            return "high"
        elif class_name == "medium" or co_level >= self.thresholds["medium"]:
            return "medium"
        elif class_name == "low" or co_level >= self.thresholds["low"]:
            return "low"
        return "safe"

    def _get_recommended_action(self, alert_level: str) -> str:
        actions = {
            "safe": "No action required",
            "low": "Increase ventilation",
            "medium": "Open windows and monitor",
            "high": "Evacuate and call emergency",
            "critical": "Immediate evacuation required",
        }
        return actions.get(alert_level, "Unknown")

    def classify_from_raw(self, co_concentration: float, temperature: float, humidity: float, time_of_day: float = 12.0, is_heating_on: float = 0.0) -> Dict[str, Any]:
        sensor_data = {
            "co_concentration": co_concentration,
            "temperature": temperature,
            "humidity": humidity,
            "time_of_day": time_of_day,
            "is_heating_on": is_heating_on,
        }
        return self.classify(sensor_data)