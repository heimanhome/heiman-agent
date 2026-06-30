import logging
from datetime import datetime
from typing import Optional, Dict, List
from heiman.ai.llm_client import LlmClient

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
        
        open_doors = [d for d in device_data if "door" in d.get("type", "").lower() and d.get("switchState") == 1]
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
