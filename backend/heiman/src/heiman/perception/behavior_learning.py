import asyncio
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


logger = logging.getLogger(__name__)


class HabitCategory(str, Enum):
    WAKE_UP = "wake_up"
    SLEEP = "sleep"
    LEAVE_HOME = "leave_home"
    RETURN_HOME = "return_home"
    MEAL = "meal"
    WORK = "work"
    RELAX = "relax"
    EXERCISE = "exercise"


@dataclass
class HabitPattern:
    category: HabitCategory
    times: List[int] = field(default_factory=list)
    weekdays: List[int] = field(default_factory=list)
    confidence: float = 0.0
    last_updated: Optional[float] = None


@dataclass
class UserProfile:
    user_id: str
    habits: Dict[str, HabitPattern] = field(default_factory=dict)
    preferences: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0


class BehaviorLearningEngine:
    def __init__(self):
        self._user_profiles: Dict[str, UserProfile] = {}
        self._event_history: List[Dict] = []
        self._model_path = None
        self._initialized = False

    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        model_path = config.get("model_path")

        if model_path:
            self._model_path = model_path
            path_obj = Path(model_path)
            if path_obj.exists():
                await self._load_model(path_obj)
            else:
                logger.info("No existing model found at %s, starting fresh", model_path)
        else:
            logger.info("No model path configured, starting fresh")

        self._initialized = True

    async def _load_model(self, path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                for user_id, profile_data in data.get("users", {}).items():
                    profile = UserProfile(
                        user_id=user_id,
                        preferences=profile_data.get("preferences", {}),
                        created_at=profile_data.get("created_at", 0),
                    )
                    for habit_name, habit_data in profile_data.get("habits", {}).items():
                        profile.habits[habit_name] = HabitPattern(
                            category=HabitCategory(habit_name),
                            times=habit_data.get("times", []),
                            weekdays=habit_data.get("weekdays", []),
                            confidence=habit_data.get("confidence", 0),
                            last_updated=habit_data.get("last_updated"),
                        )
                    self._user_profiles[user_id] = profile
            logger.info(f"Loaded model from {path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")

    async def _save_model(self):
        if not self._model_path:
            return

        try:
            data = {
                "users": {
                    user_id: {
                        "habits": {
                            habit.category.value: {
                                "times": habit.times,
                                "weekdays": habit.weekdays,
                                "confidence": habit.confidence,
                                "last_updated": habit.last_updated,
                            }
                            for habit in profile.habits.values()
                        },
                        "preferences": profile.preferences,
                        "created_at": profile.created_at,
                    }
                    for user_id, profile in self._user_profiles.items()
                }
            }
            with open(self._model_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved model to {self._model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    async def process_event(self, event: Dict):
        self._event_history.append(event)

        if len(self._event_history) > 1000:
            self._event_history = self._event_history[-1000:]

        user_id = event.get("user_id", "default")
        await self._update_habit_pattern(user_id, event)

        await self._save_model()

    async def _update_habit_pattern(self, user_id: str, event: Dict):
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = UserProfile(
                user_id=user_id,
                created_at=datetime.now().timestamp(),
            )

        profile = self._user_profiles[user_id]
        event_type = event.get("type", "")
        timestamp = event.get("timestamp", datetime.now().timestamp())
        dt = datetime.fromtimestamp(timestamp)
        hour_minute = dt.hour * 60 + dt.minute
        weekday = dt.weekday()

        habit_category = self._classify_event(event_type)
        if not habit_category:
            return

        if habit_category.value not in profile.habits:
            profile.habits[habit_category.value] = HabitPattern(
                category=habit_category,
            )

        habit = profile.habits[habit_category.value]
        habit.times.append(hour_minute)
        habit.weekdays.append(weekday)

        if len(habit.times) >= 7:
            habit.confidence = self._calculate_confidence(habit)

        habit.last_updated = timestamp

    def _classify_event(self, event_type: str) -> Optional[HabitCategory]:
        event_map = {
            "wake_up": HabitCategory.WAKE_UP,
            "sleep": HabitCategory.SLEEP,
            "leave_home": HabitCategory.LEAVE_HOME,
            "return_home": HabitCategory.RETURN_HOME,
            "motion_detected": HabitCategory.WAKE_UP,
            "door_open": HabitCategory.LEAVE_HOME,
            "door_close": HabitCategory.RETURN_HOME,
        }

        for key, category in event_map.items():
            if key in event_type.lower():
                return category
        return None

    def _calculate_confidence(self, habit: HabitPattern) -> float:
        if len(habit.times) < 3:
            return 0.0

        times = sorted(habit.times)
        mean_time = sum(times) / len(times)
        variance = sum((t - mean_time) ** 2 for t in times) / len(times)
        std_dev = variance ** 0.5

        weekday_distribution = len(set(habit.weekdays)) / 7

        time_consistency = max(0, 1 - std_dev / 120)
        day_consistency = weekday_distribution

        return round((time_consistency * 0.7 + day_consistency * 0.3), 2)

    async def predict_next_activity(self, user_id: str) -> Dict[str, Any]:
        if user_id not in self._user_profiles:
            return {"activity": "unknown", "confidence": 0.0}

        profile = self._user_profiles[user_id]
        current_time = datetime.now()
        current_minutes = current_time.hour * 60 + current_time.minute
        current_weekday = current_time.weekday()

        best_match = None
        best_score = 0.0

        for habit in profile.habits.values():
            if habit.confidence < 0.5:
                continue

            mean_time = sum(habit.times) / len(habit.times)
            time_diff = abs(current_minutes - mean_time)

            if time_diff < 60:
                score = (1 - time_diff / 60) * habit.confidence
                if score > best_score:
                    best_score = score
                    best_match = habit.category

        if best_match:
            return {
                "activity": best_match.value,
                "confidence": best_score,
                "expected_time": datetime.fromtimestamp(
                    datetime.now().timestamp() + (mean_time - current_minutes) * 60
                ).strftime("%H:%M"),
            }

        return {"activity": "unknown", "confidence": 0.0}

    async def get_user_habits(self, user_id: str) -> Dict[str, Any]:
        if user_id not in self._user_profiles:
            return {"habits": [], "preferences": {}}

        profile = self._user_profiles[user_id]
        habits = []

        for habit in profile.habits.values():
            if habit.times:
                mean_time = sum(habit.times) / len(habit.times)
                habits.append({
                    "category": habit.category.value,
                    "average_time": f"{int(mean_time // 60):02d}:{int(mean_time % 60):02d}",
                    "confidence": habit.confidence,
                    "weekdays": sorted(set(habit.weekdays)),
                    "sample_count": len(habit.times),
                })

        return {
            "habits": habits,
            "preferences": profile.preferences,
        }

    async def update_user_preference(self, user_id: str, key: str, value: Any):
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = UserProfile(
                user_id=user_id,
                created_at=datetime.now().timestamp(),
            )

        self._user_profiles[user_id].preferences[key] = value
        await self._save_model()

    async def suggest_action(self, user_id: str, context: Dict) -> Dict[str, Any]:
        habits = await self.get_user_habits(user_id)
        prediction = await self.predict_next_activity(user_id)

        suggestions = []

        if prediction["confidence"] > 0.7:
            activity = prediction["activity"]
            if activity == "return_home":
                suggestions.append({
                    "action": "prepare_home",
                    "description": "预计即将回家，准备舒适环境",
                    "confidence": prediction["confidence"],
                })
            elif activity == "sleep":
                suggestions.append({
                    "action": "prepare_bedroom",
                    "description": "预计即将睡觉，调整卧室环境",
                    "confidence": prediction["confidence"],
                })
            elif activity == "leave_home":
                suggestions.append({
                    "action": "secure_home",
                    "description": "预计即将出门，检查安全状态",
                    "confidence": prediction["confidence"],
                })

        return {
            "suggestions": suggestions,
            "prediction": prediction,
            "habits": habits,
        }