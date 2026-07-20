"""Water leak detection model."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any

from heiman.perception.models.sensor_detector import SensorDetector

_LOGGER = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = str(
    Path(__file__).resolve().parent / "water_leak.onnx"
)


class WaterLeakDetector(SensorDetector):
    INPUT_FEATURES = [
        "water_level",
        "temperature",
        "humidity",
        "pressure",
        "flow_rate",
        "battery_level",
    ]

    OUTPUT_CLASSES = ["no_leak", "leak_detected", "pipe_burst"]

    def __init__(
        self,
        model_path: str = _DEFAULT_MODEL_PATH,
        use_gpu: bool = False,
        num_threads: int | None = None,
        threshold: float = 0.55,
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

        is_leak = class_name in ["leak_detected", "pipe_burst"] and confidence >= self.threshold
        is_burst = class_name == "pipe_burst" and confidence >= self.threshold
        water_level = sensor_data.get("water_level", 0.0)

        return {
            **result,
            "is_leak": is_leak,
            "is_burst": is_burst,
            "water_level": water_level,
            "threshold": self.threshold,
            "severity": self._determine_severity(class_name, confidence),
        }

    def _determine_severity(self, class_name: str, confidence: float) -> str:
        if class_name == "pipe_burst" and confidence >= 0.8:
            return "critical"
        elif class_name == "pipe_burst":
            return "high"
        elif class_name == "leak_detected" and confidence >= 0.8:
            return "high"
        elif class_name == "leak_detected" and confidence >= 0.6:
            return "medium"
        elif class_name == "leak_detected":
            return "low"
        return "none"

    def detect_from_raw(self, water_level: float, temperature: float, humidity: float, pressure: float = 1.0, flow_rate: float = 0.0, battery_level: float = 100.0) -> Dict[str, Any]:
        sensor_data = {
            "water_level": water_level,
            "temperature": temperature,
            "humidity": humidity,
            "pressure": pressure,
            "flow_rate": flow_rate,
            "battery_level": battery_level,
        }
        return self.detect(sensor_data)