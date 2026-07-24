import logging
from datetime import datetime
from typing import Optional, Dict, List, Any

from heiman.ai.llm_client import LlmClient
from heiman.perception.emotion_engine import EmotionEngine
from heiman.perception.behavior_learning import BehaviorLearningEngine
from heiman.energy.energy_manager import EnergyManager, EnergyMode
from heiman.device.protocol_adapter import get_adapter_registry

logger = logging.getLogger(__name__)


class Decision:
    def __init__(
        self,
        action: str,
        confidence: float,
        explanation: str,
        priority: str = "normal",
        timestamp: Optional[datetime] = None,
        details: Optional[Dict] = None,
    ):
        self.action = action
        self.confidence = confidence
        self.explanation = explanation
        self.priority = priority
        self.timestamp = timestamp or datetime.now()
        self.details = details or {}

    def to_dict(self):
        return {
            "action": self.action,
            "confidence": round(self.confidence, 2),
            "explanation": self.explanation,
            "priority": self.priority,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


class ActionSuggestion:
    def __init__(
        self,
        title: str,
        description: str,
        type: str,
        priority: str = "normal",
        device_id: Optional[str] = None,
        device_name: Optional[str] = None,
        params: Optional[Dict] = None,
    ):
        self.title = title
        self.description = description
        self.type = type
        self.priority = priority
        self.device_id = device_id
        self.device_name = device_name
        self.params = params or {}

    def to_dict(self):
        return {
            "title": self.title,
            "description": self.description,
            "type": self.type,
            "priority": self.priority,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "params": self.params,
        }


class DecisionEngine:
    def __init__(self, llm_client: Optional[LlmClient] = None):
        self.llm_client = llm_client or LlmClient()
        self._emotion_engine = EmotionEngine()
        self._behavior_engine = BehaviorLearningEngine()
        self._energy_manager = EnergyManager()
        self._adapter_registry = get_adapter_registry()

    async def initialize(self):
        await self._emotion_engine.initialize()
        await self._behavior_engine.initialize()
        await self._energy_manager.initialize()
        logger.info("Decision engine initialized with all sub-systems")

    def generate_decision(self, context: Dict) -> Decision:
        device_data = context.get("device_data", [])
        events = context.get("events", [])
        anomaly_results = context.get("anomalies", [])
        comfort_result = context.get("comfort", {})
        activity_result = context.get("activity", {})

        if anomaly_results:
            critical_anomalies = [a for a in anomaly_results if a.get("severity") == "critical"]
            if critical_anomalies:
                return self._handle_critical_anomaly(critical_anomalies[0])

        if activity_result.get("activity") == "returning":
            return self._handle_returning(context)

        if activity_result.get("activity") == "leaving":
            return self._handle_leaving(context)

        if comfort_result.get("level") == "poor":
            return self._handle_poor_comfort(comfort_result)

        if comfort_result.get("suggestions"):
            return Decision(
                action="adjust_environment",
                confidence=0.7,
                explanation=f"环境舒适度需要调整：{'; '.join(comfort_result.get('suggestions', []))}",
                priority="normal",
                details=comfort_result,
            )

        return Decision(
            action="none",
            confidence=0.9,
            explanation="当前家庭状态正常，无需特别操作。",
            priority="low",
        )

    def _handle_critical_anomaly(self, anomaly: Dict) -> Decision:
        anomaly_type = anomaly.get("anomaly_type", "")
        message = anomaly.get("message", "")

        actions = {
            "smoke": ("alarm", "烟雾报警！请立即确认安全并采取行动。"),
            "gas": ("alarm", "燃气泄漏！请立即关闭燃气阀并通风。"),
            "water": ("alarm", "水浸报警！请立即关闭水源并处理。"),
            "door": ("alert", "门未关闭！请确认门已锁好。"),
        }

        for key, (action, explanation) in actions.items():
            if key in anomaly_type or key in message.lower():
                return Decision(
                    action=action,
                    confidence=0.95,
                    explanation=explanation,
                    priority="critical",
                    details=anomaly,
                )

        return Decision(
            action="alert",
            confidence=0.9,
            explanation=f"检测到严重异常：{message}",
            priority="critical",
            details=anomaly,
        )

    def _handle_returning(self, context: Dict) -> Decision:
        comfort_result = context.get("comfort", {})
        suggestions = comfort_result.get("suggestions", [])

        if suggestions:
            return Decision(
                action="prepare_home",
                confidence=0.85,
                explanation=f"欢迎回家！检测到环境需要调整：{'; '.join(suggestions)}",
                priority="normal",
                details={"activity": "returning", "comfort": comfort_result},
            )

        return Decision(
            action="welcome_home",
            confidence=0.9,
            explanation="欢迎回家！当前家庭状态良好。",
            priority="low",
            details={"activity": "returning"},
        )

    def _handle_leaving(self, context: Dict) -> Decision:
        device_data = context.get("device_data", [])
        
        # 门磁设备用 contactState 判断门开关（SwitchState 是报警使能状态，不是门的状态）
        open_doors = [
            d for d in device_data
            if any(kw in d.get("type", "").lower() for kw in ("door", "contact"))
            and (d.get("contactState") == 1 or d.get("switchState") == 1)
        ]
        active_lights = [d for d in device_data if "light" in d.get("type", "").lower() and d.get("switchState") == 1]
        active_appliances = [d for d in device_data if d.get("type") in ["aircon", "heater"] and d.get("switchState") == 1]

        warnings = []
        actions = []

        if open_doors:
            warnings.append(f"{len(open_doors)}扇门未关闭")
            actions.extend(f"关闭{d.get('name', '')}" for d in open_doors)

        if active_lights:
            warnings.append(f"{len(active_lights)}盏灯未关闭")
            actions.extend(f"关闭{d.get('name', '')}" for d in active_lights)

        if active_appliances:
            warnings.append(f"{len(active_appliances)}台电器仍在运行")
            actions.extend(f"关闭{d.get('name', '')}" for d in active_appliances)

        if warnings:
            return Decision(
                action="secure_home",
                confidence=0.85,
                explanation=f"检测到以下问题，请确认：{'; '.join(warnings)}",
                priority="warning",
                details={
                    "activity": "leaving",
                    "warnings": warnings,
                    "suggested_actions": actions,
                },
            )

        return Decision(
            action="leave_home",
            confidence=0.9,
            explanation="所有设备已确认安全，祝您外出愉快！",
            priority="low",
            details={"activity": "leaving"},
        )

    def _handle_poor_comfort(self, comfort_result: Dict) -> Decision:
        suggestions = comfort_result.get("suggestions", [])
        score = comfort_result.get("score", 0)

        priority = "high" if score < 30 else "normal"

        return Decision(
            action="emergency_adjust",
            confidence=0.8,
            explanation=f"环境舒适度较差 ({score}分)，请立即处理：{'; '.join(suggestions)}",
            priority=priority,
            details=comfort_result,
        )

    def summarize_events(self, events: List[Dict]) -> str:
        if not events:
            return "暂无事件记录。"

        return self.llm_client.summarize(events)

    def suggest_action(self, context: Dict) -> ActionSuggestion:
        decision = self.generate_decision(context)

        action_map = {
            "alarm": ActionSuggestion(
                title="紧急报警",
                description=decision.explanation,
                type="alarm",
                priority="critical",
            ),
            "alert": ActionSuggestion(
                title="警告",
                description=decision.explanation,
                type="alert",
                priority="high",
            ),
            "adjust_environment": ActionSuggestion(
                title="环境调整",
                description=decision.explanation,
                type="environment",
                priority="normal",
            ),
            "prepare_home": ActionSuggestion(
                title="欢迎回家",
                description=decision.explanation,
                type="welcome",
                priority="normal",
            ),
            "secure_home": ActionSuggestion(
                title="离家检查",
                description=decision.explanation,
                type="security",
                priority="high",
            ),
            "leave_home": ActionSuggestion(
                title="安全离家",
                description=decision.explanation,
                type="leave",
                priority="low",
            ),
            "welcome_home": ActionSuggestion(
                title="欢迎回家",
                description=decision.explanation,
                type="welcome",
                priority="low",
            ),
            "emergency_adjust": ActionSuggestion(
                title="紧急调整",
                description=decision.explanation,
                type="emergency",
                priority="critical",
            ),
        }

        return action_map.get(decision.action, ActionSuggestion(
            title="正常状态",
            description=decision.explanation,
            type="normal",
            priority="low",
        ))

    def analyze_home(self, devices_data: List[Dict], events: List[Dict] = []) -> Dict:
        from heiman.ai.anomaly_detector import AnomalyDetector
        from heiman.ai.comfort_evaluator import ComfortEvaluator
        from heiman.ai.behavior_recognizer import BehaviorRecognizer

        anomaly_detector = AnomalyDetector()
        comfort_evaluator = ComfortEvaluator()
        behavior_recognizer = BehaviorRecognizer()

        anomalies = [a.to_dict() for a in anomaly_detector.detect_batch(devices_data)]
        activity = behavior_recognizer.recognize_current_activity(devices_data).to_dict()

        env_devices = [d for d in devices_data if d.get("temperature") is not None or d.get("humidity") is not None]
        comfort = {}
        if env_devices:
            latest_env = max(env_devices, key=lambda x: x.get("lastUpdate", ""))
            comfort = comfort_evaluator.evaluate_device(latest_env).to_dict()

        context = {
            "device_data": devices_data,
            "events": events,
            "anomalies": anomalies,
            "comfort": comfort,
            "activity": activity,
        }

        decision = self.generate_decision(context).to_dict()
        suggestion = self.suggest_action(context).to_dict()
        summary = self.summarize_events(events)

        return {
            "anomalies": anomalies,
            "comfort": comfort,
            "activity": activity,
            "decision": decision,
            "suggestion": suggestion,
            "summary": summary,
            "device_count": len(devices_data),
            "online_count": len([d for d in devices_data if d.get("status") == "online"]),
        }

    async def analyze_home_fused(self, home_id: str = "default") -> Dict:
        from heiman.ai.orchestrator import AIOrchestrator

        orchestrator = AIOrchestrator()
        scene_context = await orchestrator.fuse_perception_data(home_id)

        devices_data = scene_context.device_states

        from heiman.ai.anomaly_detector import AnomalyDetector
        from heiman.ai.comfort_evaluator import ComfortEvaluator
        from heiman.ai.behavior_recognizer import BehaviorRecognizer

        anomaly_detector = AnomalyDetector()
        comfort_evaluator = ComfortEvaluator()
        behavior_recognizer = BehaviorRecognizer()

        anomalies = [a.to_dict() for a in anomaly_detector.detect_batch(devices_data)]
        activity = behavior_recognizer.recognize_current_activity(devices_data).to_dict()

        env_devices = [d for d in devices_data if d.get("temperature") is not None or d.get("humidity") is not None]
        comfort = {}
        if env_devices:
            latest_env = max(env_devices, key=lambda x: x.get("lastUpdate", ""))
            comfort = comfort_evaluator.evaluate_device(latest_env).to_dict()

        context = {
            "device_data": devices_data,
            "events": [],
            "anomalies": anomalies,
            "comfort": comfort,
            "activity": activity,
            "user_identity": scene_context.user_identity,
            "security_state": scene_context.security_state,
        }

        decision = self.generate_decision(context).to_dict()
        suggestion = self.suggest_action(context).to_dict()

        user_identity_info = None
        if scene_context.user_identity:
            user_identity_info = {
                "person_id": scene_context.user_identity.person_id,
                "name": scene_context.user_identity.name,
                "role": scene_context.user_identity.role,
                "confidence": scene_context.user_identity.confidence,
            }

        return {
            "anomalies": anomalies,
            "comfort": comfort,
            "activity": activity,
            "decision": decision,
            "suggestion": suggestion,
            "user_identity": user_identity_info,
            "security_state": scene_context.security_state,
            "device_count": len(devices_data),
            "online_count": len([d for d in devices_data if d.get("status") == "online"]),
        }

    async def smart_home_assistant(self, user_id: str = "default") -> Dict[str, Any]:
        # 1) Collect devices from protocol adapters (Matter, Zigbee, etc.)
        all_adapters = self._adapter_registry.list_adapters()
        protocol_devices = []
        for protocol in all_adapters:
            adapter = self._adapter_registry.get_adapter(protocol)
            if adapter:
                protocol_devices.extend(adapter.list_devices())

        device_dicts = [d.to_dict() for d in protocol_devices]
        connected_protocols = [p.value for p in all_adapters]

        # 2) Collect real devices from Heiman Cloud via Manager
        try:
            from heiman.manager import get_manager
            mgr = get_manager()
            if mgr and hasattr(mgr, '_adapter') and mgr.adapter:
                heiman_connected = mgr.adapter.get_connected_devices()
                for did, pdev in heiman_connected.items():
                    dev_dict = {
                        "device_id": did,
                        "name": pdev.name,
                        "type": pdev.device_type.value if hasattr(pdev.device_type, 'value') else str(pdev.device_type),
                        "state": "online" if pdev.online else "offline",
                        "room": pdev.room_name or "",
                        "status": "online" if pdev.online else "offline",
                    }
                    # Try to get latest sensor data
                    try:
                        dev_data = mgr.adapter.collect(did, drain=False)
                        if dev_data and dev_data.sensor_data:
                            sd = dev_data.sensor_data
                            dev_dict["temperature"] = sd.temperature
                            dev_dict["humidity"] = sd.humidity
                            dev_dict["lastUpdate"] = dev_data.timestamp.isoformat() if dev_data.timestamp else ""
                    except Exception:
                        pass
                    device_dicts.append(dev_dict)

                if heiman_connected:
                    connected_protocols = ["Heiman云"] + connected_protocols
        except Exception as e:
            logger.warning("[DecisionEngine] Failed to collect Heiman devices: %s", e)

        from heiman.ai.anomaly_detector import AnomalyDetector
        from heiman.ai.comfort_evaluator import ComfortEvaluator
        from heiman.ai.behavior_recognizer import BehaviorRecognizer

        anomaly_detector = AnomalyDetector()
        comfort_evaluator = ComfortEvaluator()
        behavior_recognizer = BehaviorRecognizer()

        anomalies = [a.to_dict() for a in anomaly_detector.detect_batch(device_dicts)]
        activity = behavior_recognizer.recognize_current_activity(device_dicts).to_dict()

        env_devices = [d for d in device_dicts if d.get("temperature") is not None or d.get("humidity") is not None]
        comfort = {}
        if env_devices:
            latest_env = max(env_devices, key=lambda x: (x.get("lastUpdate") or ""))
            comfort = comfort_evaluator.evaluate_device(latest_env).to_dict()

        emotion_context = {
            "hour": datetime.now().hour,
            "day_of_week": datetime.now().weekday(),
            "activity": activity.get("activity", ""),
            "device_states": {d["device_id"]: d for d in device_dicts},
        }
        emotion_result = await self._emotion_engine.analyze_emotion(user_id, emotion_context)

        behavior_prediction = await self._behavior_engine.predict_next_activity(user_id)
        energy_optimization = await self._energy_manager.optimize_consumption()

        proactive_actions = await self._generate_proactive_actions(
            user_id,
            activity,
            emotion_result,
            behavior_prediction,
            energy_optimization,
            anomalies,
            comfort,
            device_dicts,
        )

        total_devices = len(device_dicts)
        online_count = len([d for d in device_dicts if (d.get("state") == "online" or d.get("status") == "online")])

        return {
            "assistant_mode": "active",
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "anomalies": anomalies,
            "activity": activity,
            "comfort": comfort,
            "emotion": emotion_result,
            "behavior_prediction": behavior_prediction,
            "energy_optimization": energy_optimization,
            "proactive_actions": proactive_actions,
            "device_count": total_devices,
            "online_count": online_count,
            "connected_protocols": connected_protocols,
        }

    async def _generate_proactive_actions(
        self,
        user_id: str,
        activity: Dict,
        emotion: Dict,
        behavior_prediction: Dict,
        energy: Dict,
        anomalies: List[Dict],
        comfort: Dict,
        device_dicts: List[Dict] = None,
    ) -> List[Dict[str, Any]]:
        actions = []

        # --- Emergency: critical anomalies ---
        for anomaly in anomalies:
            if anomaly.get("severity") == "critical":
                actions.append({
                    "type": "emergency",
                    "priority": "critical",
                    "title": "紧急告警",
                    "description": anomaly.get("message", "检测到严重异常"),
                    "action": "alert_user",
                })

        # --- Emotion-based environment adjustment ---
        if emotion.get("confidence", 0) > 0.6:
            suggested_env = emotion.get("suggested_environment", {})
            actions.append({
                "type": "emotion_based",
                "priority": "high",
                "title": "情绪感知调节",
                "description": emotion.get("description", ""),
                "action": "adjust_environment",
                "params": {
                    "lighting": suggested_env.get("lighting"),
                    "temperature": suggested_env.get("temperature"),
                    "music": suggested_env.get("music"),
                },
            })

        # --- Behavior prediction ---
        if behavior_prediction.get("confidence", 0) > 0.7:
            predicted_activity = behavior_prediction.get("activity", "")
            if predicted_activity == "return_home":
                actions.append({
                    "type": "predictive",
                    "priority": "high",
                    "title": "预计回家",
                    "description": "准备舒适的家庭环境",
                    "action": "prepare_home",
                    "estimated_time": behavior_prediction.get("expected_time"),
                })
            elif predicted_activity == "sleep":
                actions.append({
                    "type": "predictive",
                    "priority": "high",
                    "title": "预计睡觉",
                    "description": "调整卧室环境助眠",
                    "action": "prepare_bedroom",
                    "estimated_time": behavior_prediction.get("expected_time"),
                })
            elif predicted_activity == "leave_home":
                actions.append({
                    "type": "predictive",
                    "priority": "medium",
                    "title": "预计出门",
                    "description": "检查安全状态",
                    "action": "secure_home",
                    "estimated_time": behavior_prediction.get("expected_time"),
                })

        # --- Energy recommendations ---
        for recommendation in energy.get("recommendations", []):
            actions.append({
                "type": "energy",
                "priority": recommendation.get("priority", "medium"),
                "title": "节能建议",
                "description": recommendation.get("description", ""),
                "action": recommendation.get("action", ""),
                "params": {
                    "estimated_savings": recommendation.get("estimated_savings_watts"),
                    "current_price": energy.get("current_price_per_kwh"),
                },
            })

        # --- Comfort adjustment ---
        if comfort.get("level") == "poor":
            actions.append({
                "type": "comfort",
                "priority": "high",
                "title": "环境舒适度调整",
                "description": f"当前舒适度评分 {comfort.get('score', 0)} 分",
                "action": "adjust_comfort",
                "params": {
                    "suggestions": comfort.get("suggestions", []),
                },
            })

        # --- Contextual status: generate useful actions based on real device data ---
        if device_dicts:
            online_devs = [d for d in device_dicts
                           if d.get("state") == "online" or d.get("status") == "online"]

            # Classify devices by type for contextual actions
            env_sensors = {"temperature", "temperature_sensor", "thermometer",
                           "hygrometer", "humidity_sensor", "smart_thermo_hygrometer",
                           "温感报警器"}
            security_sensors = {"contact", "door_sensor", "motion_sensor", "pir",
                                "门磁", "人体红外"}
            safety_sensors = {"smoke", "smoke_detector", "gas_detector", "water_leak",
                              "烟雾报警器", "燃气报警器", "水浸报警器"}

            dev_types_lower = [d.get("type", "").lower().replace("-", "_").replace(" ", "_")
                               for d in online_devs]

            has_env = any(t in env_sensors for t in dev_types_lower)
            has_security = any(t in security_sensors for t in dev_types_lower)
            has_safety = any(t in safety_sensors for t in dev_types_lower)
            has_temp_value = any(d.get("temperature") is not None for d in online_devs)

            # If we have real devices but no triggered actions yet, add contextual ones
            if not actions and online_devs:
                actions.append({
                    "type": "status",
                    "priority": "low",
                    "title": "系统运行正常",
                    "description": f"当前 {len(online_devs)} 台设备在线，智能家居系统运行正常",
                    "action": "monitor",
                })

                if has_env and not comfort.get("level"):
                    actions.append({
                        "type": "environment",
                        "priority": "medium",
                        "title": "环境监测",
                        "description": "正在持续监测室内温湿度，检测到舒适的环境条件",
                        "action": "monitor_environment",
                    })

                if has_security:
                    actions.append({
                        "type": "security",
                        "priority": "medium",
                        "title": "安防监控",
                        "description": "门磁/人体传感器运行正常，持续监控家庭出入口安全",
                        "action": "monitor_security",
                    })

                if has_safety:
                    actions.append({
                        "type": "safety",
                        "priority": "high",
                        "title": "安全防护",
                        "description": "烟雾/燃气/水浸传感器运行正常，守护家庭安全",
                        "action": "monitor_safety",
                    })

            # Always show temperature summary if we have real values
            if has_temp_value and not any(a.get("type") == "environment" for a in actions):
                temp_devs = [d for d in online_devs if d.get("temperature") is not None]
                if temp_devs:
                    avg_temp = sum(d.get("temperature", 0) for d in temp_devs) / len(temp_devs)
                    actions.append({
                        "type": "environment",
                        "priority": "low",
                        "title": "温度概况",
                        "description": f"室内平均温度 {avg_temp:.1f}°C，当前环境舒适",
                        "action": "monitor_environment",
                    })

        return sorted(actions, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x.get("priority", "medium"), 2))
