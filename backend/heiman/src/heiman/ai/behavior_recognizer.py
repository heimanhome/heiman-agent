import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class ActivityType(Enum):
    SLEEPING = "sleeping"
    AWAKING = "awaking"
    WORKING = "working"
    COOKING = "cooking"
    EATING = "eating"
    LEAVING = "leaving"
    RETURNING = "returning"
    WATCHING_TV = "watching_tv"
    SHOWERING = "showering"
    CLEANING = "cleaning"
    UNKNOWN = "unknown"


class ActivityResult:
    def __init__(
        self,
        activity: ActivityType,
        confidence: float,
        room_id: Optional[str] = None,
        room_name: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        duration_minutes: Optional[int] = None,
        details: Optional[Dict] = None,
    ):
        self.activity = activity
        self.confidence = confidence
        self.room_id = room_id
        self.room_name = room_name
        self.timestamp = timestamp or datetime.now()
        self.duration_minutes = duration_minutes
        self.details = details or {}

    def to_dict(self):
        return {
            "activity": self.activity.value,
            "activity_label": self._get_activity_label(),
            "confidence": round(self.confidence, 2),
            "room_id": self.room_id,
            "room_name": self.room_name,
            "timestamp": self.timestamp.isoformat(),
            "duration_minutes": self.duration_minutes,
            "details": self.details,
        }

    def _get_activity_label(self) -> str:
        labels = {
            ActivityType.SLEEPING: "睡觉",
            ActivityType.AWAKING: "起床",
            ActivityType.WORKING: "工作",
            ActivityType.COOKING: "做饭",
            ActivityType.EATING: "用餐",
            ActivityType.LEAVING: "外出",
            ActivityType.RETURNING: "回家",
            ActivityType.WATCHING_TV: "看电视",
            ActivityType.SHOWERING: "洗澡",
            ActivityType.CLEANING: "打扫",
            ActivityType.UNKNOWN: "未知活动",
        }
        return labels[self.activity]


class BehaviorRecognizer:
    def __init__(self):
        self.room_activity_map = {
            "bedroom": [ActivityType.SLEEPING, ActivityType.AWAKING],
            "study": [ActivityType.WORKING],
            "kitchen": [ActivityType.COOKING, ActivityType.EATING],
            "living room": [ActivityType.WATCHING_TV, ActivityType.EATING],
            "bathroom": [ActivityType.SHOWERING],
        }
        
        self.door_threshold_minutes = 5
        self.motion_duration_threshold_minutes = 15

    def recognize_current_activity(
        self,
        devices_data: List[Dict],
        room_id: Optional[str] = None,
        current_time: Optional[datetime] = None,
    ) -> ActivityResult:
        now = current_time or datetime.now()
        hour = now.hour
        
        if room_id:
            return self._recognize_by_room(devices_data, room_id, now)
        
        return self._recognize_global(devices_data, now)

    def _recognize_by_room(self, devices_data: List[Dict], room_id: str, now: datetime) -> ActivityResult:
        room_devices = [d for d in devices_data if d.get("room") == room_id]
        
        if not room_devices:
            return ActivityResult(activity=ActivityType.UNKNOWN, confidence=0.0, room_id=room_id)
        
        room_name_lower = room_id.lower()
        possible_activities = []
        
        for room_name, activities in self.room_activity_map.items():
            if room_name in room_name_lower:
                possible_activities.extend(activities)
        
        lights_on = any(d.get("type") == "light" and d.get("switchState") == 1 for d in room_devices)
        motion_detected = any(d.get("type") == "motion" and d.get("switchState") == 1 for d in room_devices)
        
        if "bedroom" in room_name_lower:
            hour = now.hour
            if hour >= 22 or hour < 6:
                if not lights_on:
                    return ActivityResult(
                        activity=ActivityType.SLEEPING,
                        confidence=0.9,
                        room_id=room_id,
                        details={"lights_on": lights_on, "motion_detected": motion_detected},
                    )
                else:
                    return ActivityResult(
                        activity=ActivityType.AWAKING,
                        confidence=0.7,
                        room_id=room_id,
                        details={"lights_on": lights_on, "motion_detected": motion_detected},
                    )
            elif 6 <= hour < 10 and lights_on:
                return ActivityResult(
                    activity=ActivityType.AWAKING,
                    confidence=0.8,
                    room_id=room_id,
                    details={"lights_on": lights_on, "motion_detected": motion_detected},
                )
        
        if "study" in room_name_lower and lights_on and motion_detected:
            return ActivityResult(
                activity=ActivityType.WORKING,
                confidence=0.85,
                room_id=room_id,
                details={"lights_on": lights_on, "motion_detected": motion_detected},
            )
        
        if "kitchen" in room_name_lower and motion_detected:
            smoke_active = any(d.get("type") == "smoke" and d.get("smokeState") == 1 for d in room_devices)
            if smoke_active:
                return ActivityResult(
                    activity=ActivityType.COOKING,
                    confidence=0.9,
                    room_id=room_id,
                    details={"motion_detected": motion_detected, "smoke_active": smoke_active},
                )
            return ActivityResult(
                activity=ActivityType.EATING,
                confidence=0.6,
                room_id=room_id,
                details={"motion_detected": motion_detected},
            )
        
        if "living room" in room_name_lower and lights_on:
            tv_on = any(d.get("type") == "tv" and d.get("switchState") == 1 for d in room_devices)
            if tv_on:
                return ActivityResult(
                    activity=ActivityType.WATCHING_TV,
                    confidence=0.85,
                    room_id=room_id,
                    details={"lights_on": lights_on, "tv_on": tv_on},
                )
            return ActivityResult(
                activity=ActivityType.EATING,
                confidence=0.5,
                room_id=room_id,
                details={"lights_on": lights_on},
            )
        
        if "bathroom" in room_name_lower and motion_detected:
            return ActivityResult(
                activity=ActivityType.SHOWERING,
                confidence=0.7,
                room_id=room_id,
                details={"motion_detected": motion_detected},
            )
        
        return ActivityResult(activity=ActivityType.UNKNOWN, confidence=0.3, room_id=room_id)

    def _recognize_global(self, devices_data: List[Dict], now: datetime) -> ActivityResult:
        door_devices = [d for d in devices_data if "door" in d.get("type", "").lower()]
        motion_devices = [d for d in devices_data if "motion" in d.get("type", "").lower()]
        light_devices = [d for d in devices_data if "light" in d.get("type", "").lower()]
        
        all_doors_closed = all(d.get("switchState") == 0 for d in door_devices if d.get("switchState") is not None)
        any_motion = any(d.get("switchState") == 1 for d in motion_devices if d.get("switchState") is not None)
        all_lights_off = all(d.get("switchState") == 0 for d in light_devices if d.get("switchState") is not None)
        
        hour = now.hour
        
        if hour >= 22 or hour < 6:
            if all_lights_off and all_doors_closed:
                return ActivityResult(
                    activity=ActivityType.SLEEPING,
                    confidence=0.85,
                    details={"all_lights_off": all_lights_off, "all_doors_closed": all_doors_closed},
                )
        
        if 6 <= hour < 10:
            if any_motion and not all_lights_off:
                return ActivityResult(
                    activity=ActivityType.AWAKING,
                    confidence=0.8,
                    details={"any_motion": any_motion, "lights_off": all_lights_off},
                )
        
        if door_devices:
            front_door = next((d for d in door_devices if "main" in d.get("name", "").lower()), door_devices[0])
            if front_door.get("switchState") == 1:
                return ActivityResult(
                    activity=ActivityType.RETURNING,
                    confidence=0.85,
                    room_id=front_door.get("room"),
                    details={"door_open": True, "door_name": front_door.get("name")},
                )
        
        if all_doors_closed and not any_motion and all_lights_off:
            return ActivityResult(
                activity=ActivityType.LEAVING,
                confidence=0.8,
                details={"all_doors_closed": all_doors_closed, "no_motion": not any_motion, "all_lights_off": all_lights_off},
            )
        
        study_devices = [d for d in devices_data if d.get("room") and "study" in d.get("room").lower()]
        if study_devices:
            study_lights_on = any(d.get("type") == "light" and d.get("switchState") == 1 for d in study_devices)
            study_motion = any(d.get("type") == "motion" and d.get("switchState") == 1 for d in study_devices)
            if study_lights_on and study_motion:
                return ActivityResult(
                    activity=ActivityType.WORKING,
                    confidence=0.75,
                    room_id=study_devices[0].get("room"),
                    details={"study_lights_on": study_lights_on, "study_motion": study_motion},
                )
        
        kitchen_devices = [d for d in devices_data if d.get("room") and "kitchen" in d.get("room").lower()]
        if kitchen_devices:
            kitchen_motion = any(d.get("type") == "motion" and d.get("switchState") == 1 for d in kitchen_devices)
            kitchen_smoke = any(d.get("type") == "smoke" and d.get("smokeState") == 1 for d in kitchen_devices)
            if kitchen_motion and kitchen_smoke:
                return ActivityResult(
                    activity=ActivityType.COOKING,
                    confidence=0.85,
                    room_id=kitchen_devices[0].get("room"),
                    details={"kitchen_motion": kitchen_motion, "kitchen_smoke": kitchen_smoke},
                )
        
        return ActivityResult(activity=ActivityType.UNKNOWN, confidence=0.2)

    def get_daily_routine(self, events: List[Dict], date: Optional[datetime] = None) -> Dict:
        target_date = date or datetime.now()
        target_date_str = target_date.strftime("%Y-%m-%d")
        
        day_events = [e for e in events if e.get("timestamp", "").startswith(target_date_str)]
        
        routine = {
            "date": target_date_str,
            "wake_up_time": None,
            "sleep_time": None,
            "leave_home_times": [],
            "return_home_times": [],
            "activity_periods": [],
        }
        
        door_events = [e for e in day_events if "door" in e.get("type", "").lower()]
        light_events = [e for e in day_events if "light" in e.get("type", "").lower()]
        motion_events = [e for e in day_events if "motion" in e.get("type", "").lower()]
        
        for event in light_events:
            ts = event.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                hour = dt.hour
                if 5 <= hour < 12 and event.get("value") == 1:
                    if not routine["wake_up_time"]:
                        routine["wake_up_time"] = ts
                elif 20 <= hour or hour < 3 and event.get("value") == 0:
                    if not routine["sleep_time"]:
                        routine["sleep_time"] = ts
            except (ValueError, TypeError):
                continue
        
        for event in door_events:
            ts = event.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if event.get("value") == 1:
                    routine["return_home_times"].append(ts)
                else:
                    routine["leave_home_times"].append(ts)
            except (ValueError, TypeError):
                continue
        
        return routine

    def predict_next_activity(self, devices_data: List[Dict], current_activity: ActivityType) -> ActivityType:
        activity_transitions = {
            ActivityType.AWAKING: ActivityType.WORKING,
            ActivityType.WORKING: ActivityType.EATING,
            ActivityType.EATING: ActivityType.WORKING,
            ActivityType.COOKING: ActivityType.EATING,
            ActivityType.EATING: ActivityType.WATCHING_TV,
            ActivityType.WATCHING_TV: ActivityType.SLEEPING,
            ActivityType.RETURNING: ActivityType.EATING,
            ActivityType.LEAVING: ActivityType.RETURNING,
        }
        
        return activity_transitions.get(current_activity, ActivityType.UNKNOWN)
