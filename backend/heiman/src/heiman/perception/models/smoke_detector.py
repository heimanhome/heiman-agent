"""Smoke detection model based on sensor data."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any

from heiman.perception.models.sensor_detector import SensorDetector

_LOGGER = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = str(
    Path(__file__).resolve().parent / "smoke_detection.onnx"
)


class SmokeDetector(SensorDetector):
    INPUT_FEATURES = [
        "smoke_concentration",
        "temperature",
        "humidity",
        "co_level",
        "voc_level",
    ]

    OUTPUT_CLASSES = ["no_smoke", "smoke_detected", "fire_detected"]

    def __init__(
        self,
        model_path: str = _DEFAULT_MODEL_PATH,
        use_gpu: bool = False,
        num_threads: int | None = None,
        threshold: float = 0.6,
    ):
        super().__init__(
            model_path=model_path,
            input_features=self.INPUT_FEATURES,
            output_classes=self.OUTPUT_CLASSES,
            use_gpu=use_gpu,
            num_threads=num_threads,
        )
        self.threshold = threshold

    def detect(self, sensor_data: Dict[str, float]) -> Dict[str, Any]:
        result = self.infer(sensor_data)

        if not result.get("success"):
            return result

        class_name = result.get("class", "unknown")
        confidence = result.get("confidence", 0.0)

        is_smoke = class_name in ["smoke_detected", "fire_detected"] and confidence >= self.threshold
        is_fire = class_name == "fire_detected" and confidence >= self.threshold

        return {
            **result,
            "is_smoke": is_smoke,
            "is_fire": is_fire,
            "threshold": self.threshold,
        }

    def detect_from_raw(self, smoke_concentration: float, temperature: float, humidity: float, co_level: float = 0.0, voc_level: float = 0.0) -> Dict[str, Any]:
        sensor_data = {
            "smoke_concentration": smoke_concentration,
            "temperature": temperature,
            "humidity": humidity,
            "co_level": co_level,
            "voc_level": voc_level,
        }
        return self.detect(sensor_data)