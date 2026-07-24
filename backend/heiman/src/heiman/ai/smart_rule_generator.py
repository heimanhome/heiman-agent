import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import uuid4

from heiman.database.rule_suggestion_repo import RuleSuggestionRepo
from heiman.database.sensor_log_repo import SensorLogRepo
from heiman.perception.behavior_learning import BehaviorLearningEngine, HabitCategory
from heiman.schema.rule import RuleSuggestion, SuggestionStatus, RuleCondition, RuleAction, RuleActionType, Rule
from heiman.schema.sensor import SensorType

logger = logging.getLogger(__name__)


class SmartRuleGenerator:
    def __init__(self):
        self._behavior_engine = BehaviorLearningEngine()
        self._suggestion_repo = RuleSuggestionRepo()
        self._sensor_log_repo = SensorLogRepo()
        self._confidence_threshold = 0.6
        self._min_samples = 7

    async def initialize(self, config: Optional[Dict] = None):
        await self._behavior_engine.initialize(config)

    async def process_event_for_learning(self, event: Dict):
        await self._behavior_engine.process_event(event)

    async def generate_rule_suggestions(self, user_id: str, home_id: str) -> List[RuleSuggestion]:
        suggestions = []

        habits = await self._behavior_engine.get_user_habits(user_id)

        for habit in habits.get("habits", []):
            if habit.get("confidence", 0) < self._confidence_threshold:
                continue

            category = habit.get("category")
            average_time = habit.get("average_time")
            confidence = habit.get("confidence")

            if category == HabitCategory.RETURN_HOME.value:
                suggestion = await self._generate_return_home_rule(
                    user_id, home_id, average_time, confidence
                )
                if suggestion:
                    suggestions.append(suggestion)

            elif category == HabitCategory.LEAVE_HOME.value:
                suggestion = await self._generate_leave_home_rule(
                    user_id, home_id, average_time, confidence
                )
                if suggestion:
                    suggestions.append(suggestion)

            elif category == HabitCategory.WAKE_UP.value:
                suggestion = await self._generate_wake_up_rule(
                    user_id, home_id, average_time, confidence
                )
                if suggestion:
                    suggestions.append(suggestion)

            elif category == HabitCategory.SLEEP.value:
                suggestion = await self._generate_sleep_rule(
                    user_id, home_id, average_time, confidence
                )
                if suggestion:
                    suggestions.append(suggestion)

        for suggestion in suggestions:
            existing = self._suggestion_repo.get_by_user(user_id)
            exists = any(
                s.name == suggestion.name and s.pattern_type == suggestion.pattern_type
                and s.status == SuggestionStatus.PENDING
                for s in existing
            )
            if not exists:
                self._suggestion_repo.create(suggestion)

        return suggestions

    async def _generate_return_home_rule(self, user_id: str, home_id: str, time_str: str, confidence: float) -> Optional[RuleSuggestion]:
        plug_devices = await self._find_devices_by_type(home_id, SensorType.PLUG)

        if not plug_devices:
            return None

        hour, minute = map(int, time_str.split(":"))
        time_minutes = hour * 60 + minute

        rule_data = {
            "conditions": [
                {
                    "sensor_type": "CONTACT",
                    "operator": "==",
                    "threshold": 1,
                }
            ],
            "actions": [],
            "cooldown_minutes": 60,
        }

        for device in plug_devices[:3]:
            rule_data["actions"].append({
                "action_type": "device_control",
                "payload": {
                    "device_id": device["did"],
                    "device_name": device.get("name", ""),
                    "command": "turn_on",
                },
            })

        suggestion = RuleSuggestion(
            suggestion_id=str(uuid4()),
            user_id=user_id,
            home_id=home_id,
            name=f"回家自动开插座 ({time_str})",
            description=f"检测到您通常在{time_str}左右回家，建议在开门时自动打开常用插座",
            confidence=confidence,
            pattern_type="return_home",
            trigger_device_id="door_sensor",
            trigger_device_name="门磁传感器",
            action_device_id=plug_devices[0]["did"],
            action_device_name=plug_devices[0].get("name", ""),
            rule_data=rule_data,
            status=SuggestionStatus.PENDING,
        )

        return suggestion

    async def _generate_leave_home_rule(self, user_id: str, home_id: str, time_str: str, confidence: float) -> Optional[RuleSuggestion]:
        light_devices = await self._find_devices_by_type(home_id, SensorType.PLUG)
        plug_devices = await self._find_devices_by_type(home_id, SensorType.PLUG)

        all_devices = light_devices + plug_devices
        if not all_devices:
            return None

        rule_data = {
            "conditions": [
                {
                    "sensor_type": "CONTACT",
                    "operator": "==",
                    "threshold": 0,
                    "window_seconds": 300,
                },
                {
                    "sensor_type": "MOTION",
                    "operator": "==",
                    "threshold": 0,
                },
            ],
            "actions": [],
            "cooldown_minutes": 60,
        }

        for device in all_devices[:5]:
            rule_data["actions"].append({
                "action_type": "device_control",
                "payload": {
                    "device_id": device["did"],
                    "device_name": device.get("name", ""),
                    "command": "turn_off",
                },
            })

        suggestion = RuleSuggestion(
            suggestion_id=str(uuid4()),
            user_id=user_id,
            home_id=home_id,
            name=f"离家自动关设备 ({time_str})",
            description=f"检测到您通常在{time_str}左右离家，建议在关门后5分钟自动关闭所有电器设备",
            confidence=confidence,
            pattern_type="leave_home",
            trigger_device_id="door_sensor",
            trigger_device_name="门磁传感器",
            action_device_id=all_devices[0]["did"],
            action_device_name=all_devices[0].get("name", ""),
            rule_data=rule_data,
            status=SuggestionStatus.PENDING,
        )

        return suggestion

    async def _generate_wake_up_rule(self, user_id: str, home_id: str, time_str: str, confidence: float) -> Optional[RuleSuggestion]:
        light_devices = await self._find_devices_by_type(home_id, SensorType.PLUG)

        if not light_devices:
            return None

        rule_data = {
            "conditions": [
                {
                    "sensor_type": "MOTION",
                    "operator": "==",
                    "threshold": 1,
                }
            ],
            "actions": [],
            "cooldown_minutes": 180,
        }

        for device in light_devices[:2]:
            rule_data["actions"].append({
                "action_type": "device_control",
                "payload": {
                    "device_id": device["did"],
                    "device_name": device.get("name", ""),
                    "command": "turn_on",
                },
            })

        suggestion = RuleSuggestion(
            suggestion_id=str(uuid4()),
            user_id=user_id,
            home_id=home_id,
            name=f"起床自动开灯 ({time_str})",
            description=f"检测到您通常在{time_str}左右起床，建议在检测到卧室移动时自动打开灯光",
            confidence=confidence,
            pattern_type="wake_up",
            trigger_device_id="motion_sensor",
            trigger_device_name="红外传感器",
            action_device_id=light_devices[0]["did"],
            action_device_name=light_devices[0].get("name", ""),
            rule_data=rule_data,
            status=SuggestionStatus.PENDING,
        )

        return suggestion

    async def _generate_sleep_rule(self, user_id: str, home_id: str, time_str: str, confidence: float) -> Optional[RuleSuggestion]:
        light_devices = await self._find_devices_by_type(home_id, SensorType.PLUG)
        plug_devices = await self._find_devices_by_type(home_id, SensorType.PLUG)

        all_devices = light_devices + plug_devices
        if not all_devices:
            return None

        rule_data = {
            "conditions": [
                {
                    "sensor_type": "MOTION",
                    "operator": "==",
                    "threshold": 0,
                    "window_seconds": 600,
                }
            ],
            "actions": [],
            "cooldown_minutes": 180,
        }

        for device in all_devices[:3]:
            rule_data["actions"].append({
                "action_type": "device_control",
                "payload": {
                    "device_id": device["did"],
                    "device_name": device.get("name", ""),
                    "command": "turn_off",
                },
            })

        suggestion = RuleSuggestion(
            suggestion_id=str(uuid4()),
            user_id=user_id,
            home_id=home_id,
            name=f"睡觉自动关灯 ({time_str})",
            description=f"检测到您通常在{time_str}左右睡觉，建议在卧室10分钟无移动时自动关闭灯光",
            confidence=confidence,
            pattern_type="sleep",
            trigger_device_id="motion_sensor",
            trigger_device_name="红外传感器",
            action_device_id=all_devices[0]["did"],
            action_device_name=all_devices[0].get("name", ""),
            rule_data=rule_data,
            status=SuggestionStatus.PENDING,
        )

        return suggestion

    async def _find_devices_by_type(self, home_id: str, sensor_type: SensorType) -> List[Dict]:
        try:
            logs = self._sensor_log_repo.get_by_home(home_id)
            devices = {}

            for log in logs:
                if log.sensor_type == sensor_type and log.did not in devices:
                    devices[log.did] = {
                        "did": log.did,
                        "name": log.name,
                        "sensor_type": log.sensor_type.value,
                    }

            return list(devices.values())
        except Exception as e:
            logger.error("Failed to find devices by type: %s", e)
            return []

    async def approve_suggestion(self, suggestion_id: str) -> Optional[Rule]:
        suggestion = self._suggestion_repo.get_by_id(suggestion_id)
        if not suggestion or suggestion.status != SuggestionStatus.PENDING:
            return None

        self._suggestion_repo.update_status(suggestion_id, SuggestionStatus.APPROVED)

        conditions = []
        for cond_data in suggestion.rule_data.get("conditions", []):
            conditions.append(RuleCondition(
                sensor_type=SensorType(cond_data.get("sensor_type", "CONTACT").upper()),
                operator=cond_data.get("operator", "=="),
                threshold=cond_data.get("threshold"),
                window_seconds=cond_data.get("window_seconds"),
            ))

        actions = []
        for action_data in suggestion.rule_data.get("actions", []):
            action_type = RuleActionType(action_data.get("action_type", "DEVICE_CONTROL"))
            actions.append(RuleAction(
                action_type=action_type,
                payload=action_data.get("payload", {}),
            ))

        rule = Rule(
            rule_id=str(uuid4()),
            name=suggestion.name,
            description=suggestion.description,
            enabled=True,
            conditions=conditions,
            actions=actions,
            cooldown_minutes=suggestion.rule_data.get("cooldown_minutes", 5),
            home_id=suggestion.home_id,
        )

        from heiman.database.rule_repo import RuleRepo
        rule_repo = RuleRepo()
        rule_repo.create(rule)

        logger.info("[SmartRuleGenerator] Suggestion approved and rule created: %s", rule.name)
        return rule

    async def reject_suggestion(self, suggestion_id: str) -> bool:
        suggestion = self._suggestion_repo.get_by_id(suggestion_id)
        if not suggestion:
            return False

        self._suggestion_repo.update_status(suggestion_id, SuggestionStatus.REJECTED)
        logger.info("[SmartRuleGenerator] Suggestion rejected: %s", suggestion.name)
        return True