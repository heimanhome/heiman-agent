"""Base detector for sensor data based ONNX models."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np

from heiman.perception.inference.ort_utils import make_session

_LOGGER = logging.getLogger(__name__)

_MODELS_DIR = str(
    Path(__file__).resolve().parent
)


class SensorDetector:
    def __init__(
        self,
        model_path: str,
        input_features: List[str],
        output_classes: Optional[List[str]] = None,
        use_gpu: bool = False,
        num_threads: Optional[int] = None,
    ):
        self.model_path = model_path
        self.input_features = input_features
        self.output_classes = output_classes or []
        self.use_gpu = use_gpu
        self.num_threads = num_threads

        self.session = None
        self.input_name = None
        self.input_shape = None
        self.output_name = None

        self._initialized = False

    def initialize(self) -> bool:
        try:
            self.session = make_session(self.model_path, use_gpu=self.use_gpu, num_threads=self.num_threads)

            if self.session is None:
                return False

            inputs = self.session.get_inputs()
            if len(inputs) > 0:
                self.input_name = inputs[0].name
                self.input_shape = inputs[0].shape
                _LOGGER.info("Input: name=%s, shape=%s", self.input_name, self.input_shape)

            outputs = self.session.get_outputs()
            if len(outputs) > 0:
                self.output_name = outputs[0].name
                _LOGGER.info("Output: name=%s, shape=%s", self.output_name, outputs[0].shape)

            self._initialized = True
            _LOGGER.info("SensorDetector initialized for %s", self.model_path)
            return True

        except Exception as e:
            _LOGGER.error("Failed to initialize detector: %s", e)
            return False

    def is_initialized(self) -> bool:
        return self._initialized and self.session is not None

    def preprocess(self, sensor_data: Dict[str, float]) -> np.ndarray:
        features = []
        for feature in self.input_features:
            features.append(sensor_data.get(feature, 0.0))

        input_array = np.array(features, dtype=np.float32)
        input_array = np.expand_dims(input_array, axis=0)

        return input_array

    def infer(self, sensor_data: Dict[str, float]) -> Dict[str, Any]:
        if not self.is_initialized():
            return {"error": "Detector not initialized"}

        try:
            input_tensor = self.preprocess(sensor_data)

            outputs = self.session.run([self.output_name], {self.input_name: input_tensor})

            result = outputs[0].squeeze()

            if isinstance(result, np.ndarray) and len(result) > 1 and self.output_classes:
                class_index = int(np.argmax(result))
                confidence = float(result[class_index])
                class_name = self.output_classes[class_index] if class_index < len(self.output_classes) else "unknown"

                return {
                    "success": True,
                    "class": class_name,
                    "class_index": class_index,
                    "confidence": confidence,
                    "raw_output": result.tolist(),
                }
            elif isinstance(result, np.ndarray) and len(result) == 1:
                return {
                    "success": True,
                    "value": float(result[0]),
                    "raw_output": result.tolist(),
                }
            else:
                return {
                    "success": True,
                    "value": float(result) if np.isscalar(result) else result.tolist(),
                    "raw_output": result.tolist() if hasattr(result, "tolist") else result,
                }

        except Exception as e:
            _LOGGER.error("Inference failed: %s", e)
            return {"success": False, "error": str(e)}

    def release(self):
        self.session = None
        self._initialized = False

    def __del__(self):
        self.release()