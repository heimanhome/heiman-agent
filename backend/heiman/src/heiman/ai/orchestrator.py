import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import uuid4


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
    recent_events: List[Dict] = field(default_factory=list)
    sensor_history: Dict[str, List[Dict]] = field(default_factory=dict)


class AIOrchestrator:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._perception_engine = None
        self._identity_engine = None
        self._heiman_layer = None
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
        from heiman.perception.heiman import HeimanLayer, HeimanConfig
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
        self._heiman_layer = HeimanLayer(HeimanConfig())
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
        
        from heiman.config import get_settings
        settings = get_settings()
        heiman_model = getattr(settings, "model", None)
        
        if heiman_model and hasattr(heiman_model, "heiman"):
            active_profile = heiman_model.heiman
            model_name = getattr(active_profile, "model", "qwen3:8b")
            base_url = getattr(active_profile, "base_url", "http://localhost:11434")
            
            if base_url and "ollama" in base_url.lower():
                provider = "ollama"
            elif base_url and "dashscope" in base_url.lower():
                provider = "dashscope"
            else:
                provider = "ollama"
            
            model_config = {
                "id": "llm_default",
                "name": model_name,
                "provider": provider,
                "model": model_name,
                "config": {
                    "base_url": base_url,
                },
            }
            logger.info(f"[AI] Loading configured model: {model_name} from {base_url}")
        else:
            model_config = {
                "id": "llm_default",
                "name": "default_llm",
                "provider": "ollama",
                "model": "qwen3:8b",
                "config": {"base_url": "http://localhost:11434"},
            }
            logger.info("[AI] No model config found, using default: qwen3:8b")
        
        self._current_model_config = model_config
        await self._edge_inference.initialize([model_config])

        # 从数据库加载真实人员数据
        from heiman.database.person_repo import get_person_repo
        person_repo = get_person_repo()
        real_persons = person_repo.get_all()
        if real_persons:
            for p in real_persons:
                role = p.role or "family"
                self._identity_engine.add_person(p.id, p.name, role)
            logger.info(f"[AI] Loaded {len(real_persons)} persons from database")
        else:
            logger.warning("[AI] No persons found in database, identity engine is empty")

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

        # 收集历史事件和设备传感器历史
        recent_events = await self._get_recent_iot_events(mgr, hours=24, limit=20)
        sensor_history = await self._get_recent_sensor_history(mgr, limit_per_device=10)

        return SceneContext(
            home_id=home_id,
            timestamp=asyncio.get_event_loop().time(),
            user_identity=user_identity,
            activities=fused_activity.get("activities", []),
            environment=comfort.get("factors", {}),
            security_state=self._assess_security(heiman_devices, perception_events),
            device_states=heiman_devices,
            recent_events=recent_events,
            sensor_history=sensor_history,
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

    async def _get_recent_iot_events(self, mgr, hours: int = 24, limit: int = 20) -> List[Dict]:
        """获取近期的 IoT 历史事件（告警、设备上下线、异常等）。"""
        try:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(hours=hours)
            events = mgr.event_repo.query(after=cutoff, limit=limit)
            if not events:
                return []
            result = []
            for e in events:
                result.append({
                    "event_id": getattr(e, "id", getattr(e, "event_id", "")),
                    "device_id": getattr(e, "device_id", getattr(e, "did", "")),
                    "event_type": getattr(e, "event_type", getattr(e, "type", "")),
                    "severity": getattr(e, "severity", getattr(e, "level", "")),
                    "message": getattr(e, "message", getattr(e, "description", "")),
                    "timestamp": str(getattr(e, "timestamp", getattr(e, "created_at", ""))),
                })
            logger.info("[Orchestrator] Collected %d recent IoT events", len(result))
            return result
        except Exception as e:
            logger.warning("[Orchestrator] Failed to collect IoT events: %s", e)
            return []

    async def _get_recent_sensor_history(self, mgr, limit_per_device: int = 10) -> Dict[str, List[Dict]]:
        """获取每个设备的近期传感器读数历史，用于趋势分析。"""
        try:
            logs = mgr.sensor_log_repo.query(limit=300)
            if not logs:
                return {}
            # 按 did 分组，每组取最近 limit_per_device 条
            from collections import defaultdict
            grouped: Dict[str, List] = defaultdict(list)
            for log_item in logs:
                did = getattr(log_item, "did", getattr(log_item, "device_id", ""))
                grouped[did].append({
                    "sensor_type": getattr(log_item, "sensor_type", ""),
                    "value": getattr(log_item, "value", 0),
                    "unit": getattr(log_item, "unit", ""),
                    "timestamp": str(getattr(log_item, "timestamp", "")),
                    "temperature": getattr(log_item, "temperature", None),
                    "humidity": getattr(log_item, "humidity", None),
                    "co2": getattr(log_item, "co2", None),
                    "pm25": getattr(log_item, "pm25", None),
                })
            result = {}
            for did, items in grouped.items():
                result[did] = items[-limit_per_device:]
            logger.info("[Orchestrator] Collected sensor history for %d devices", len(result))
            return result
        except Exception as e:
            logger.warning("[Orchestrator] Failed to collect sensor history: %s", e)
            return {}

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
        """获取真实设备数据（含传感器读数），与 smart_home_assistant 使用相同数据源。"""
        try:
            perception_devices = mgr.adapter.get_connected_devices()
            if not perception_devices:
                logger.warning("[AIOrchestrator] No connected devices from adapter")
                return []

            result = []
            for did, pdev in perception_devices.items():
                device_data = {
                    "id": did,
                    "name": pdev.name,
                    "type": pdev.device_type.value if hasattr(pdev.device_type, 'value') else str(pdev.device_type),
                    "status": "online" if pdev.online else "offline",
                    "room": pdev.room_name or "",
                    "lastUpdate": datetime.now().isoformat(),
                }
                # 获取传感器实时读数（从 sensor_data_cache）
                try:
                    dev_data = mgr.adapter.collect(did, drain=False)
                    if dev_data and dev_data.sensor_data:
                        sd = dev_data.sensor_data
                        device_data["temperature"] = sd.temperature
                        device_data["humidity"] = sd.humidity
                        device_data["co2"] = sd.co2
                        device_data["pm25"] = sd.pm25
                        device_data["switchState"] = sd.switchState
                        device_data["motionState"] = sd.motionState
                        device_data["smokeState"] = sd.smokeState
                        device_data["gasState"] = sd.gasState
                        device_data["waterState"] = sd.waterState
                        device_data["contactState"] = sd.contactState
                        device_data["alarmState"] = sd.alarmState
                        device_data["battery"] = sd.battery
                        device_data["rssi"] = sd.rssi
                        if dev_data.timestamp:
                            device_data["lastUpdate"] = dev_data.timestamp.isoformat()
                except Exception:
                    pass
                result.append(device_data)

            logger.info("[AIOrchestrator] Collected %d real devices for perception fusion", len(result))
            return result
        except Exception as e:
            logger.error(f"Failed to get heiman devices: {e}")
            return []

    def _get_current_model_config(self) -> Dict:
        from heiman.config import get_settings
        settings = get_settings()
        heiman_model = getattr(settings, "model", None)
        
        if heiman_model and hasattr(heiman_model, "heiman"):
            active_profile = heiman_model.heiman
            model_name = getattr(active_profile, "model", "qwen3:8b")
            base_url = getattr(active_profile, "base_url", "http://localhost:11434")
            api_key = getattr(active_profile, "api_key", "")
            
            if base_url and "dashscope" in base_url.lower():
                provider = "dashscope"
            elif base_url and "openai" in base_url.lower() and "ollama" not in base_url.lower():
                provider = "openai"
            else:
                provider = "ollama"
            
            return {
                "name": model_name,
                "provider": provider,
                "model": model_name,
                "base_url": base_url,
                "api_key": api_key,
            }
        
        return {
            "name": "qwen3:8b",
            "provider": "ollama",
            "model": "qwen3:8b",
            "base_url": "http://localhost:11434",
            "api_key": "",
        }

    async def generate_intent_response(self, scene_context: SceneContext, user_query: str) -> Dict:
        context_prompt = self._build_context_prompt(scene_context)

        if self._heiman_layer:
            from heiman.perception.heiman import HeimanContext

            heiman_context = HeimanContext(
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

            result = await self._heiman_layer.run(heiman_context, user_query)
            response = result.response
            model_config = self._get_current_model_config()
        else:
            from heiman.ai.llm_client import LlmClient
            
            model_config = self._get_current_model_config()
            provider = model_config.get("provider", "ollama")
            model_name = model_config.get("model", "qwen3:8b")
            base_url = model_config.get("base_url", "http://localhost:11434")
            api_key = model_config.get("api_key", "")
            
            llm_client = LlmClient(provider=provider, api_key=api_key, base_url=base_url)
            response = llm_client.generate(
                f"""你是一个智能家庭助手。
当前场景上下文：
{context_prompt}

用户问题：{user_query}

请根据上下文提供准确、友好的回答和建议。""",
                model=model_name
            )

        return {"response": response, "context": scene_context, "model": model_config.get("name", model_name)}

    def _build_context_prompt(self, context: SceneContext) -> str:
        parts = []

        # 当前在家人员
        if context.user_identity:
            parts.append(f"当前在家人员：{context.user_identity.name} ({context.user_identity.role})")

        # 当前活动
        if context.activities:
            parts.append(f"当前活动：{', '.join(context.activities)}")

        # 环境状态
        if context.environment:
            env_str = ", ".join([f"{k}: {v}" for k, v in context.environment.items()])
            parts.append(f"环境状态：{env_str}")

        # 安全状态
        if context.security_state:
            parts.append(f"安全状态：{context.security_state.get('status')}")

        # 近期历史事件（告警、异常、设备上下线等）
        if context.recent_events:
            event_lines = []
            for evt in context.recent_events[:10]:  # 最多10条，避免 token 过多
                ts = str(evt.get("timestamp", ""))[:19]
                etype = evt.get("event_type", "")
                msg = evt.get("message", "")
                sev = evt.get("severity", "")
                event_lines.append(f"  [{ts}] [{sev}] {etype}: {msg}")
            if event_lines:
                parts.append("近期事件历史（最近24小时）：\n" + "\n".join(event_lines))

        # 传感器历史趋势（摘要）
        if context.sensor_history:
            trend_lines = []
            for did, readings in list(context.sensor_history.items())[:5]:  # 最多5个设备
                if not readings:
                    continue
                latest = readings[-1] if readings else {}
                # 只展示有意义的变化指标
                trend_summary = self._summarize_sensor_trend(did, readings)
                if trend_summary:
                    trend_lines.append(trend_summary)
            if trend_lines:
                parts.append("传感器趋势（近期变化）：\n" + "\n".join(trend_lines))

        return "\n".join(parts)

    def _summarize_sensor_trend(self, did: str, readings: List[Dict]) -> str:
        """生成单个设备的传感器趋势摘要。"""
        from collections import defaultdict
        by_type = defaultdict(list)
        for r in readings:
            stype = r.get("sensor_type", "")
            value = r.get("value")
            if stype and value is not None:
                try:
                    by_type[stype].append(float(value))
                except (ValueError, TypeError):
                    pass

        summary_parts = []
        for stype, values in by_type.items():
            if not values:
                continue
            first = values[0]
            last = values[-1]
            avg = sum(values) / len(values)
            # 只展示有明显变化或在关注范围的指标
            variation = abs(last - first) if len(values) > 1 else 0
            if variation > 0.1 or stype in ("temperature", "humidity", "co2", "pm25"):
                summary_parts.append(f"{stype} 均值{avg:.1f} (变化{last - first:+.1f})")

        if summary_parts:
            return f"  设备 {did}: " + " | ".join(summary_parts)
        return ""

    async def analyze_with_heiman(self, home_id: str, query: str) -> Dict:
        start_ms = time.time() * 1000
        success = False
        error_msg = None
        try:
            scene_context = await self.fuse_perception_data(home_id)
            result = await self.generate_intent_response(scene_context, query)
            success = True
            return result
        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            duration_ms = time.time() * 1000 - start_ms
            self._record_agent_run(
                source="heiman_orchestrator",
                query=query[:500],
                duration_ms=duration_ms,
                success=success,
                error_msg=error_msg,
            )

    def _record_agent_run(self, source: str, query: str, duration_ms: float, success: bool, error_msg: str | None = None):
        """Record an AI orchestration run as an agent run in the observability DB."""
        try:
            from heiman.observability.recorder import get_recorder
            recorder = get_recorder()
            if recorder:
                recorder.record_agent_run(
                    run_id=str(uuid4()),
                    trace_id=str(uuid4()),
                    source=source,
                    query=query,
                    duration_ms=duration_ms,
                    success=success,
                    error_msg=error_msg,
                )
        except Exception as e:
            logger.debug("[AIOrchestrator] Failed to record agent run: %s", e)

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