import asyncio
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EmotionType(str, Enum):
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    CALM = "calm"
    STRESSED = "stressed"
    TIRED = "tired"
    EXCITED = "excited"
    ANXIOUS = "anxious"
    NEUTRAL = "neutral"


class EmotionContext(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    WEEKDAY = "weekday"
    WEEKEND = "weekend"


@dataclass
class EmotionRecord:
    emotion: EmotionType
    confidence: float
    timestamp: float
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmotionalProfile:
    user_id: str
    emotion_history: List[EmotionRecord] = field(default_factory=list)
    emotional_triggers: Dict[str, List[str]] = field(default_factory=dict)
    preferred_environments: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    created_at: float = 0.0


class EmotionEngine:
    def __init__(self):
        self._profiles: Dict[str, EmotionalProfile] = {}
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
                logger.info("No existing emotion model found at %s, starting fresh", model_path)
        else:
            logger.info("No emotion model path configured, starting fresh")

        self._initialized = True

    async def _load_model(self, path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                for user_id, profile_data in data.get("users", {}).items():
                    profile = EmotionalProfile(
                        user_id=user_id,
                        created_at=profile_data.get("created_at", 0),
                        emotional_triggers=profile_data.get("emotional_triggers", {}),
                        preferred_environments=profile_data.get("preferred_environments", {}),
                    )
                    for record_data in profile_data.get("emotion_history", []):
                        profile.emotion_history.append(EmotionRecord(
                            emotion=EmotionType(record_data["emotion"]),
                            confidence=record_data["confidence"],
                            timestamp=record_data["timestamp"],
                            context=record_data.get("context", {}),
                        ))
                    self._profiles[user_id] = profile
            logger.info(f"Loaded emotion model from {path}")
        except Exception as e:
            logger.error(f"Failed to load emotion model: {e}")

    async def _save_model(self):
        if not self._model_path:
            return

        try:
            data = {
                "users": {
                    user_id: {
                        "emotion_history": [
                            {
                                "emotion": record.emotion.value,
                                "confidence": record.confidence,
                                "timestamp": record.timestamp,
                                "context": record.context,
                            }
                            for record in profile.emotion_history
                        ],
                        "emotional_triggers": profile.emotional_triggers,
                        "preferred_environments": profile.preferred_environments,
                        "created_at": profile.created_at,
                    }
                    for user_id, profile in self._profiles.items()
                }
            }
            with open(self._model_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved emotion model to {self._model_path}")
        except Exception as e:
            logger.error(f"Failed to save emotion model: {e}")

    async def analyze_emotion(self, user_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if user_id not in self._profiles:
            self._profiles[user_id] = EmotionalProfile(
                user_id=user_id,
                created_at=datetime.now().timestamp(),
            )

        profile = self._profiles[user_id]
        emotion, confidence = self._infer_emotion(context)

        record = EmotionRecord(
            emotion=emotion,
            confidence=confidence,
            timestamp=datetime.now().timestamp(),
            context=context,
        )
        profile.emotion_history.append(record)

        if len(profile.emotion_history) > 500:
            profile.emotion_history = profile.emotion_history[-500:]

        await self._update_emotional_triggers(profile, record)
        await self._save_model()

        return {
            "emotion": emotion.value,
            "emotion_label": self._get_emotion_label(emotion),
            "confidence": confidence,
            "suggested_environment": self._suggest_environment(emotion),
        }

    def _infer_emotion(self, context: Dict[str, Any]) -> tuple[EmotionType, float]:
        hour = context.get("hour", datetime.now().hour)
        day_of_week = context.get("day_of_week", datetime.now().weekday())
        activity = context.get("activity", "")
        voice_tone = context.get("voice_tone", "")
        heart_rate = context.get("heart_rate")
        sleep_quality = context.get("sleep_quality", 0)
        device_states = context.get("device_states", {})

        scores = {emotion: 0.0 for emotion in EmotionType}

        if 22 <= hour or hour < 6:
            scores[EmotionType.TIRED] += 0.3
            scores[EmotionType.CALM] += 0.2
        elif 6 <= hour < 9:
            scores[EmotionType.CALM] += 0.2
            scores[EmotionType.EXCITED] += 0.1
        elif 9 <= hour < 18:
            scores[EmotionType.STRESSED] += 0.2
            scores[EmotionType.CALM] += 0.1
        elif 18 <= hour < 22:
            scores[EmotionType.HAPPY] += 0.2
            scores[EmotionType.CALM] += 0.2

        if day_of_week >= 5:
            scores[EmotionType.HAPPY] += 0.15
            scores[EmotionType.EXCITED] += 0.1
        else:
            scores[EmotionType.STRESSED] += 0.1

        activity_map = {
            "sleeping": EmotionType.TIRED,
            "awaking": EmotionType.CALM,
            "working": EmotionType.STRESSED,
            "cooking": EmotionType.HAPPY,
            "eating": EmotionType.HAPPY,
            "watching_tv": EmotionType.CALM,
            "showering": EmotionType.CALM,
            "cleaning": EmotionType.STRESSED,
        }
        if activity in activity_map:
            scores[activity_map[activity]] += 0.15

        if voice_tone:
            voice_map = {
                "happy": EmotionType.HAPPY,
                "sad": EmotionType.SAD,
                "angry": EmotionType.ANGRY,
                "calm": EmotionType.CALM,
                "excited": EmotionType.EXCITED,
            }
            if voice_tone in voice_map:
                scores[voice_map[voice_tone]] += 0.3

        if heart_rate:
            if heart_rate > 100:
                scores[EmotionType.EXCITED] += 0.15
                scores[EmotionType.STRESSED] += 0.1
            elif heart_rate < 60:
                scores[EmotionType.CALM] += 0.2
                scores[EmotionType.TIRED] += 0.1

        if sleep_quality < 5:
            scores[EmotionType.TIRED] += 0.2
            scores[EmotionType.STRESSED] += 0.1

        if device_states:
            lights_on = any(d.get("switchState") == 1 for d in device_states.values() if "light" in str(d.get("type", "")).lower())
            music_on = any(d.get("switchState") == 1 for d in device_states.values() if "speaker" in str(d.get("type", "")).lower())
            if lights_on and music_on:
                scores[EmotionType.HAPPY] += 0.1

        total = sum(scores.values())
        if total == 0:
            return EmotionType.NEUTRAL, 0.5

        best_emotion = max(scores, key=scores.get)
        confidence = scores[best_emotion] / total

        return best_emotion, round(confidence, 2)

    async def _update_emotional_triggers(self, profile: EmotionalProfile, record: EmotionRecord):
        emotion_str = record.emotion.value
        context_keys = list(record.context.keys())

        if emotion_str not in profile.emotional_triggers:
            profile.emotional_triggers[emotion_str] = []

        for key in context_keys:
            if key not in profile.emotional_triggers[emotion_str]:
                profile.emotional_triggers[emotion_str].append(key)

    def _get_emotion_label(self, emotion: EmotionType) -> str:
        labels = {
            EmotionType.HAPPY: "开心",
            EmotionType.SAD: "难过",
            EmotionType.ANGRY: "生气",
            EmotionType.CALM: "平静",
            EmotionType.STRESSED: "紧张",
            EmotionType.TIRED: "疲惫",
            EmotionType.EXCITED: "兴奋",
            EmotionType.ANXIOUS: "焦虑",
            EmotionType.NEUTRAL: "中性",
        }
        return labels[emotion]

    def _suggest_environment(self, emotion: EmotionType) -> Dict[str, Any]:
        suggestions = {
            EmotionType.HAPPY: {
                "description": "保持当前舒适环境",
                "lighting": "warm",
                "temperature": 24,
                "music": "upbeat",
            },
            EmotionType.SAD: {
                "description": "营造温暖舒适的氛围",
                "lighting": "warm_dim",
                "temperature": 25,
                "music": "soft",
            },
            EmotionType.ANGRY: {
                "description": "帮助放松心情",
                "lighting": "cool_dim",
                "temperature": 23,
                "music": "calming",
            },
            EmotionType.CALM: {
                "description": "维持平静环境",
                "lighting": "natural",
                "temperature": 24,
                "music": "ambient",
            },
            EmotionType.STRESSED: {
                "description": "缓解压力",
                "lighting": "warm",
                "temperature": 24,
                "music": "relaxing",
            },
            EmotionType.TIRED: {
                "description": "帮助休息",
                "lighting": "dim",
                "temperature": 23,
                "music": "sleep",
            },
            EmotionType.EXCITED: {
                "description": "匹配兴奋状态",
                "lighting": "bright",
                "temperature": 22,
                "music": "energetic",
            },
            EmotionType.ANXIOUS: {
                "description": "提供安全感",
                "lighting": "warm",
                "temperature": 24,
                "music": "peaceful",
            },
            EmotionType.NEUTRAL: {
                "description": "保持标准环境",
                "lighting": "natural",
                "temperature": 24,
                "music": None,
            },
        }
        return suggestions.get(emotion, suggestions[EmotionType.NEUTRAL])

    async def get_user_emotional_profile(self, user_id: str) -> Dict[str, Any]:
        if user_id not in self._profiles:
            return {"emotion_history": [], "triggers": {}, "preferences": {}}

        profile = self._profiles[user_id]
        recent_history = profile.emotion_history[-30:]

        return {
            "emotion_history": [
                {
                    "emotion": record.emotion.value,
                    "emotion_label": self._get_emotion_label(record.emotion),
                    "confidence": record.confidence,
                    "timestamp": record.timestamp,
                }
                for record in recent_history
            ],
            "triggers": profile.emotional_triggers,
            "preferences": profile.preferred_environments,
        }

    async def predict_emotion(self, user_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if user_id not in self._profiles:
            return {"emotion": "unknown", "confidence": 0.0}

        profile = self._profiles[user_id]
        recent_emotions = profile.emotion_history[-10:]

        if not recent_emotions:
            return {"emotion": "unknown", "confidence": 0.0}

        emotion_counts = {}
        for record in recent_emotions:
            emotion_counts[record.emotion] = emotion_counts.get(record.emotion, 0) + record.confidence

        most_likely = max(emotion_counts, key=emotion_counts.get)
        confidence = emotion_counts[most_likely] / len(recent_emotions)

        return {
            "emotion": most_likely.value,
            "emotion_label": self._get_emotion_label(most_likely),
            "confidence": round(confidence, 2),
            "suggested_environment": self._suggest_environment(most_likely),
        }