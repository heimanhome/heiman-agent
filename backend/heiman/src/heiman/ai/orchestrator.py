import asyncio
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


logger = logging.getLogger(__name__)


class PerceptionSource(str, Enum):
    HEIMAN = "heiman"
    PERCEPTION = "perception"
    FUSED = "fused"


@dataclass
class PerceptionData:
    source: PerceptionSource
    type: str
    payload: Dict[str, Any]
    timestamp: float
    confidence: float = 0.0


@dataclass
class UserIdentity:
    person_id: str
    name: str
    role: Optional[str] = None
    confidence: float = 0.0


@dataclass
class SceneContext:
    home_id: str
    timestamp: float
    user_identity: Optional[UserIdentity] = None
    activities: List[str] = field(default_factory=list)
    environment: Dict[str, Any] = field(default_factory=dict)
    security_state: Dict[str, Any] = field(default_factory=dict)
    device_states: List[Dict] = field(default_factory=list)


class AIOrchestrator:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._perception_engine = None
        self._identity_engine = None
        self._omni_layer = None
        self._collector = None
        self._behavior_engine = None
        self._edge_inference = None
        self._initialized = False
        self._cache: Dict[str, Any] = {}

    async def initialize(self):
        if self._initialized:
            return

        from heiman.perception.engine import PerceptionEngine
        from heiman.perception.identity import IdentityEngine
        from heiman.perception.omni import OmniLayer, OmniConfig
        from heiman.perception.collector import (
            PerceptionCollector,
            SensorCollector,
            CollectorConfig,
            CollectorType,
        )
        from heiman.perception.camera_adapter import CameraCollector
        from heiman.perception.asr_service import MicrophoneCollector
        from heiman.perception.behavior_learning import BehaviorLearningEngine
        from heiman.perception.edge_inference import EdgeInferenceEngine

        self._perception_engine = PerceptionEngine()
        self._identity_engine = IdentityEngine()
        self._omni_layer = OmniLayer(OmniConfig())
        self._collector = PerceptionCollector()
        self._behavior_engine = BehaviorLearningEngine()
        self._edge_inference = EdgeInferenceEngine()

        self._collector.set_engine(self._perception_engine)

        self._collector.add_collector(
            SensorCollector(CollectorConfig(
                type=CollectorType.SENSOR,
                name="sensor_collector",
                enabled=True,
                interval=5.0,
            ))
        )

        self._collector.add_collector(
            CameraCollector(CollectorConfig(
                type=CollectorType.CAMERA,
                name="camera_collector",
                enabled=True,
                interval=10.0,
                config={"camera_id": 0, "enable_face_detection": True},
            ))
        )

        self._collector.add_collector(
            MicrophoneCollector(CollectorConfig(
                type=CollectorType.MICROPHONE,
                name="microphone_collector",
                enabled=True,
                interval=8.0,
                config={"asr_provider": "mock", "asr_config": {}},
            ))
        )

        await self._perception_engine.start()
        await self._collector.start_all()
        await self._behavior_engine.initialize()
        await self._edge_inference.initialize([
            {
                "id": "llm_default",
                "name": "default_llm",
                "provider": "ollama",
                "model": "qwen3:8b",
                "config": {"base_url": "http://localhost:11434"},
            }
        ])

        self._identity_engine.add_person("pid_001", "张三", "owner")
        self._identity_engine.add_person("pid_002", "李四", "family")

        self._initialized = True
        logger.info("AI Orchestrator initialized with perception modules")

    async def fuse_perception_data(self, home_id: str) -> SceneContext:
        from heiman.manager import get_manager
        from heiman.ai.behavior_recognizer import BehaviorRecognizer
        from heiman.ai.comfort_evaluator import ComfortEvaluator

        if not self._initialized:
            await self.initialize()

        mgr = get_manager()

        heiman_devices = await self._get_heiman_devices(mgr)
        perception_events = await self._get_perception_events()
        identity_info = await self._get_identity_info()
        recent_activity = await self._get_recent_activity()

        behavior_recognizer = BehaviorRecognizer()
        comfort_evaluator = ComfortEvaluator()

        heiman_activity = behavior_recognizer.recognize_current_activity(heiman_devices)

        fused_activity = self._fuse_activities(
            heiman_activity.to_dict(),
            recent_activity
        )

        env_devices = [d for d in heiman_devices
                       if d.get("temperature") is not None or d.get("humidity") is not None]
        comfort = {}
        if env_devices:
            latest_env = max(env_devices, key=lambda x: x.get("lastUpdate", ""))
            comfort = comfort_evaluator.evaluate_device(latest_env).to_dict()

        user_identity = None
        if identity_info.get("current_persons"):
            present_persons = identity_info["current_persons"]
            if present_persons:
                user_identity = UserIdentity(
                    person_id=present_persons[0]["person_id"],
                    name=present_persons[0]["name"],
                    role=present_persons[0].get("role"),
                    confidence=0.9,
                )

        return SceneContext(
            home_id=home_id,
            timestamp=asyncio.get_event_loop().time(),
            user_identity=user_identity,
            activities=fused_activity.get("activities", []),
            environment=comfort.get("factors", {}),
            security_state=self._assess_security(heiman_devices, perception_events),
            device_states=heiman_devices,
        )

    async def _get_perception_events(self) -> List[Dict]:
        if self._perception_engine:
            events = await self._perception_engine.get_recent_events()
            return [
                {
                    "type": e.type.value,
                    "location": e.location,
                    "timestamp": e.timestamp,
                    "confidence": e.confidence,
                }
                for e in events
            ]
        return []

    async def _get_identity_info(self) -> Dict:
        if self._identity_engine:
            return await self._identity_engine.get_recent_activity()
        return {"current_persons": []}

    async def _get_recent_activity(self) -> Dict:
        return {
            "current_activity": "living",
            "location": "living_room",
            "participants": [],
            "confidence": 0.7,
        }

    def _fuse_activities(self, heiman_activity: Dict, perception_activity: Dict) -> Dict:
        activities = set()
        activities.add(heiman_activity.get("activity", "unknown"))
        activities.add(perception_activity.get("current_activity", "unknown"))

        confidence = (
            heiman_activity.get("confidence", 0.5) +
            perception_activity.get("confidence", 0.5)
        ) / 2

        return {
            "activities": list(activities),
            "main_activity": perception_activity.get("current_activity", heiman_activity.get("activity", "unknown")),
            "confidence": confidence,
        }

    def _assess_security(self, devices: List[Dict], events: List[Dict]) -> Dict:
        from heiman.ai.anomaly_detector import AnomalyDetector

        detector = AnomalyDetector()
        anomalies = detector.detect_batch(devices)

        security_events = [e for e in events if e.get("type") in ["motion", "person_identified"]]

        critical_anomalies = [a for a in anomalies if a.severity == "critical"]

        return {
            "status": "secure" if not critical_anomalies else "warning",
            "anomalies": [a.to_dict() for a in anomalies],
            "recent_events": security_events,
            "score": 100 - len(critical_anomalies) * 20,
        }

    async def _get_heiman_devices(self, mgr) -> List[Dict]:
        try:
            sensors = mgr.sensor_repo.get_all()
            return [s.to_dict() if hasattr(s, 'to_dict') else dict(s) for s in sensors]
        except Exception as e:
            logger.error(f"Failed to get heiman devices: {e}")
            return []

    async def generate_intent_response(self, scene_context: SceneContext, user_query: str) -> Dict:
        context_prompt = self._build_context_prompt(scene_context)

        if self._omni_layer:
            from heiman.perception.omni import OmniContext

            omni_context = OmniContext(
                home_id=scene_context.home_id,
                timestamp=scene_context.timestamp,
                persons=[{
                    "name": scene_context.user_identity.name,
                    "role": scene_context.user_identity.role,
                }] if scene_context.user_identity else [],
                events=[],
                device_states=scene_context.device_states,
                environment=scene_context.environment,
            )

            result = await self._omni_layer.run(omni_context, user_query)
            response = result.response
        else:
            from heiman.ai.llm_client import LlmClient
            llm_client = LlmClient()
            response = llm_client.generate_text(
                f"""你是一个智能家庭助手。
当前场景上下文：
{context_prompt}

用户问题：{user_query}

请根据上下文提供准确、友好的回答和建议。"""
            )

        return {"response": response, "context": scene_context}

    def _build_context_prompt(self, context: SceneContext) -> str:
        parts = []

        if context.user_identity:
            parts.append(f"当前在家人员：{context.user_identity.name} ({context.user_identity.role})")

        if context.activities:
            parts.append(f"当前活动：{', '.join(context.activities)}")

        if context.environment:
            env_str = ", ".join([f"{k}: {v}" for k, v in context.environment.items()])
            parts.append(f"环境状态：{env_str}")

        if context.security_state:
            parts.append(f"安全状态：{context.security_state.get('status')}")

        return "\n".join(parts)

    async def analyze_with_omni(self, home_id: str, query: str) -> Dict:
        scene_context = await self.fuse_perception_data(home_id)
        return await self.generate_intent_response(scene_context, query)

    def get_identity_engine(self):
        return self._identity_engine

    def get_perception_engine(self):
        return self._perception_engine

    def get_collector(self):
        return self._collector

    def get_behavior_engine(self):
        return self._behavior_engine

    def get_edge_inference(self):
        return self._edge_inference

    async def process_behavior_event(self, event: Dict):
        if self._behavior_engine:
            await self._behavior_engine.process_event(event)

    async def get_habits(self, user_id: str = "default") -> Dict:
        if self._behavior_engine:
            return await self._behavior_engine.get_user_habits(user_id)
        return {"habits": [], "preferences": {}}

    async def get_action_suggestions(self, user_id: str = "default", context: Optional[Dict] = None) -> Dict:
        if self._behavior_engine:
            return await self._behavior_engine.suggest_action(user_id, context or {})
        return {"suggestions": [], "prediction": {"activity": "unknown"}, "habits": []}

    async def update_preference(self, user_id: str, key: str, value: Any):
        if self._behavior_engine:
            await self._behavior_engine.update_user_preference(user_id, key, value)

    async def edge_infer(self, model_id: str, prompt: str, params: Optional[Dict] = None) -> Dict:
        if self._edge_inference:
            return await self._edge_inference.infer(model_id, prompt, params)
        return {"error": "Edge inference not initialized"}