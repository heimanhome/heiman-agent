"""测试模型加载和推理功能"""
import sys
import types

sys.path.insert(0, "/Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src")


def _import_by_path(module_name, file_path):
    module = types.ModuleType(module_name)
    module.__file__ = file_path
    sys.modules[module_name] = module
    with open(file_path, 'r') as f:
        code = f.read()
    exec(code, module.__dict__)
    return module


ORT_UTILS_PATH = "/Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/perception/inference/ort_utils.py"
EDGE_INFERENCE_PATH = "/Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/perception/edge_inference.py"
BEHAVIOR_PATH = "/Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/perception/behavior_learning.py"
SENSOR_DETECTOR_PATH = "/Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/perception/models/sensor_detector.py"
SMOKE_DETECTOR_PATH = "/Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/perception/models/smoke_detector.py"
CO_ALERT_PATH = "/Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/perception/models/co_alert_detector.py"
TEMP_FORECAST_PATH = "/Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/perception/models/temp_forecast_detector.py"
WATER_LEAK_PATH = "/Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/perception/models/water_leak_detector.py"


class TestORTUtils:
    def test_make_session_import(self):
        module = _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        assert hasattr(module, 'make_session')
        assert callable(module.make_session)

    def test_make_session_basic(self):
        module = _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        assert hasattr(module, '_DEFAULT_NUM_THREADS')
        assert module._DEFAULT_NUM_THREADS == 4

    def test_ort_version_ge(self):
        module = _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        assert hasattr(module, '_ort_version_ge')
        assert callable(module._ort_version_ge)
        assert module._ort_version_ge(0, 0) is True
        assert module._ort_version_ge(999, 999) is False


class TestEdgeInferenceEngine:
    def test_engine_initialization(self):
        module = _import_by_path('heiman.perception.edge_inference', EDGE_INFERENCE_PATH)
        engine = module.EdgeInferenceEngine()
        assert isinstance(engine._models, dict)
        assert isinstance(engine._providers, dict)


class TestBehaviorLearningEngine:
    def test_engine_initialization(self):
        module = _import_by_path('heiman.perception.behavior_learning', BEHAVIOR_PATH)
        engine = module.BehaviorLearningEngine()
        assert isinstance(engine._user_profiles, dict)
        assert isinstance(engine._event_history, list)
        assert engine._initialized is False


class TestSensorDetector:
    def test_detector_initialization(self):
        _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        module = _import_by_path('heiman.perception.models.sensor_detector', SENSOR_DETECTOR_PATH)
        detector = module.SensorDetector(
            model_path='/fake/path/model.onnx',
            input_features=['feature1', 'feature2'],
            output_classes=['class1', 'class2'],
        )
        assert detector.input_features == ['feature1', 'feature2']
        assert detector.output_classes == ['class1', 'class2']
        assert detector.is_initialized() is False

    def test_preprocess(self):
        _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        module = _import_by_path('heiman.perception.models.sensor_detector', SENSOR_DETECTOR_PATH)
        detector = module.SensorDetector(
            model_path='/fake/path/model.onnx',
            input_features=['temp', 'humidity'],
        )

        sensor_data = {'temp': 25.5, 'humidity': 60.0}
        result = detector.preprocess(sensor_data)

        import numpy as np
        assert isinstance(result, np.ndarray)
        assert result.shape == (1, 2)
        assert result[0, 0] == 25.5
        assert result[0, 1] == 60.0

    def test_preprocess_missing_features(self):
        _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        module = _import_by_path('heiman.perception.models.sensor_detector', SENSOR_DETECTOR_PATH)
        detector = module.SensorDetector(
            model_path='/fake/path/model.onnx',
            input_features=['temp', 'humidity', 'pressure'],
        )

        sensor_data = {'temp': 25.0}
        result = detector.preprocess(sensor_data)

        import numpy as np
        assert result.shape == (1, 3)
        assert result[0, 0] == 25.0
        assert result[0, 1] == 0.0
        assert result[0, 2] == 0.0


class TestSmokeDetector:
    def test_detector_initialization(self):
        _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        _import_by_path('heiman.perception.models.sensor_detector', SENSOR_DETECTOR_PATH)
        module = _import_by_path('heiman.perception.models.smoke_detector', SMOKE_DETECTOR_PATH)
        detector = module.SmokeDetector()
        assert detector.INPUT_FEATURES == ['smoke_concentration', 'temperature', 'humidity', 'co_level', 'voc_level']
        assert detector.OUTPUT_CLASSES == ['no_smoke', 'smoke_detected', 'fire_detected']
        assert detector.threshold == 0.6

    def test_detect_from_raw(self):
        _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        _import_by_path('heiman.perception.models.sensor_detector', SENSOR_DETECTOR_PATH)
        module = _import_by_path('heiman.perception.models.smoke_detector', SMOKE_DETECTOR_PATH)
        detector = module.SmokeDetector()

        result = detector.detect_from_raw(0.1, 25.0, 50.0)
        assert result['error'] == 'Detector not initialized'


class TestCOAlertDetector:
    def test_detector_initialization(self):
        _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        _import_by_path('heiman.perception.models.sensor_detector', SENSOR_DETECTOR_PATH)
        module = _import_by_path('heiman.perception.models.co_alert_detector', CO_ALERT_PATH)
        detector = module.COAlertDetector()
        assert detector.INPUT_FEATURES == ['co_concentration', 'temperature', 'humidity', 'time_of_day', 'is_heating_on']
        assert detector.OUTPUT_CLASSES == ['safe', 'low', 'medium', 'high', 'critical']

    def test_classify_from_raw(self):
        _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        _import_by_path('heiman.perception.models.sensor_detector', SENSOR_DETECTOR_PATH)
        module = _import_by_path('heiman.perception.models.co_alert_detector', CO_ALERT_PATH)
        detector = module.COAlertDetector()

        result = detector.classify_from_raw(5.0, 22.0, 45.0)
        assert result['error'] == 'Detector not initialized'

    def test_determine_alert_level(self):
        _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        _import_by_path('heiman.perception.models.sensor_detector', SENSOR_DETECTOR_PATH)
        module = _import_by_path('heiman.perception.models.co_alert_detector', CO_ALERT_PATH)
        detector = module.COAlertDetector()

        assert detector._determine_alert_level('safe', 0) == 'safe'
        assert detector._determine_alert_level('low', 5) == 'low'
        assert detector._determine_alert_level('medium', 30) == 'medium'
        assert detector._determine_alert_level('high', 80) == 'high'
        assert detector._determine_alert_level('critical', 200) == 'critical'


class TestTempForecastDetector:
    def test_detector_initialization(self):
        _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        _import_by_path('heiman.perception.models.sensor_detector', SENSOR_DETECTOR_PATH)
        module = _import_by_path('heiman.perception.models.temp_forecast_detector', TEMP_FORECAST_PATH)
        detector = module.TempForecastDetector()
        assert len(detector.INPUT_FEATURES) == 8

    def test_forecast_from_raw(self):
        _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        _import_by_path('heiman.perception.models.sensor_detector', SENSOR_DETECTOR_PATH)
        module = _import_by_path('heiman.perception.models.temp_forecast_detector', TEMP_FORECAST_PATH)
        detector = module.TempForecastDetector()

        result = detector.forecast_from_raw(25.0, 50.0)
        assert result['error'] == 'Detector not initialized'


class TestWaterLeakDetector:
    def test_detector_initialization(self):
        _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        _import_by_path('heiman.perception.models.sensor_detector', SENSOR_DETECTOR_PATH)
        module = _import_by_path('heiman.perception.models.water_leak_detector', WATER_LEAK_PATH)
        detector = module.WaterLeakDetector()
        assert detector.INPUT_FEATURES == ['water_level', 'temperature', 'humidity', 'pressure', 'flow_rate', 'battery_level']
        assert detector.OUTPUT_CLASSES == ['no_leak', 'leak_detected', 'pipe_burst']

    def test_detect_from_raw(self):
        _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        _import_by_path('heiman.perception.models.sensor_detector', SENSOR_DETECTOR_PATH)
        module = _import_by_path('heiman.perception.models.water_leak_detector', WATER_LEAK_PATH)
        detector = module.WaterLeakDetector()

        result = detector.detect_from_raw(0.0, 25.0, 50.0)
        assert result['error'] == 'Detector not initialized'

    def test_determine_severity(self):
        _import_by_path('heiman.perception.inference.ort_utils', ORT_UTILS_PATH)
        _import_by_path('heiman.perception.models.sensor_detector', SENSOR_DETECTOR_PATH)
        module = _import_by_path('heiman.perception.models.water_leak_detector', WATER_LEAK_PATH)
        detector = module.WaterLeakDetector()

        assert detector._determine_severity('no_leak', 0.9) == 'none'
        assert detector._determine_severity('leak_detected', 0.9) == 'high'
        assert detector._determine_severity('leak_detected', 0.7) == 'medium'
        assert detector._determine_severity('leak_detected', 0.5) == 'low'
        assert detector._determine_severity('pipe_burst', 0.9) == 'critical'
        assert detector._determine_severity('pipe_burst', 0.6) == 'high'