"""Temperature prediction model for next 24 hours."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any, List

from heiman.perception.models.sensor_detector import SensorDetector

_LOGGER = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = str(
    Path(__file__).resolve().parent / "temp_forecast.onnx"
)


class TempForecastDetector(SensorDetector):
    INPUT_FEATURES = [
        "current_temp",
        "current_humidity",
        "day_of_year",
        "hour_of_day",
        "weather_condition",
        "wind_speed",
        "sun_radiation",
        "indoor_outdoor_ratio",
    ]

    def __init__(
        self,
        model_path: str = _DEFAULT_MODEL_PATH,
        use_gpu: bool = False,
        num_threads: int | None = None,
    ):
        super().__init__(
            model_path=model_path,
            input_features=self.INPUT_FEATURES,
            output_classes=[],
            use_gpu=use_gpu,
            num_threads=num_threads,
        )

    def forecast(self, sensor_data: Dict[str, float], hours: int = 24) -> Dict[str, Any]:
        result = self.infer(sensor_data)

        if not result.get("success"):
            return result

        raw_output = result.get("raw_output", [])

        if isinstance(raw_output, list) and len(raw_output) >= hours:
            forecast_values = raw_output[:hours]
        elif isinstance(raw_output, (int, float)):
            forecast_values = [raw_output] * hours
        else:
            forecast_values = []

        return {
            **result,
            "forecast": forecast_values,
            "hours": hours,
            "min_temp": min(forecast_values) if forecast_values else None,
            "max_temp": max(forecast_values) if forecast_values else None,
            "avg_temp": sum(forecast_values) / len(forecast_values) if forecast_values else None,
        }

    def forecast_from_raw(self, current_temp: float, current_humidity: float, day_of_year: float = 180.0, hour_of_day: float = 12.0, weather_condition: float = 0.0, wind_speed: float = 5.0, sun_radiation: float = 500.0, indoor_outdoor_ratio: float = 0.5) -> Dict[str, Any]:
        sensor_data = {
            "current_temp": current_temp,
            "current_humidity": current_humidity,
            "day_of_year": day_of_year,
            "hour_of_day": hour_of_day,
            "weather_condition": weather_condition,
            "wind_speed": wind_speed,
            "sun_radiation": sun_radiation,
            "indoor_outdoor_ratio": indoor_outdoor_ratio,
        }
        return self.forecast(sensor_data)