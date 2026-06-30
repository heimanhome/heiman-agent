import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    DEVICE_OFFLINE = "device_offline"
    ENVIRONMENT = "environment"
    BEHAVIOR = "behavior"
    COMBINATION = "combination"
    BATTERY_LOW = "battery_low"


class AnomalyResult:
    def __init__(
        self,
        anomaly_type: AnomalyType,
        severity: str,
        message: str,
        device_id: Optional[str] = None,
        device_name: Optional[str] = None,
        room_id: Optional[str] = None,
        room_name: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        details: Optional[Dict] = None,
    ):
        self.anomaly_type = anomaly_type
        self.severity = severity
        self.message = message
        self.device_id = device_id
        self.device_name = device_name
        self.room_id = room_id
        self.room_name = room_name
        self.timestamp = timestamp or datetime.now()
        self.details = details or {}

    def to_dict(self):
        return {
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity,
            "message": self.message,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "room_id": self.room_id,
            "room_name": self.room_name,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


class AnomalyDetector:
    def __init__(self):
        self.offline_threshold_minutes = 60
        self.temperature_normal_range = (15, 35)
        self.humidity_normal_range = (20, 80)
        self.co2_normal_limit = 1500
        self.pm25_normal_limit = 75
        self.battery_low_threshold = 20

    def detect(self, device_data: Dict) -> Optional[AnomalyResult]:
        results = []
        
        if not device_data.get("status") == "online":
            result = self._detect_device_offline(device_data)
            if result:
                results.append(result)
        
        if device_data.get("battery", -1) >= 0:
            result = self._detect_battery_low(device_data)
            if result:
                results.append(result)
        
        result = self._detect_environment_anomaly(device_data)
        if result:
            results.append(result)
        
        result = self._detect_sensor_state_anomaly(device_data)
        if result:
            results.append(result)
        
        if len(results) > 1:
            return self._combine_anomalies(results)
        
        return results[0] if results else None

    def _detect_device_offline(self, device_data: Dict) -> Optional[AnomalyResult]:
        status = device_data.get("status", "").lower()
        if status == "offline":
            return AnomalyResult(
                anomaly_type=AnomalyType.DEVICE_OFFLINE,
                severity="warning",
                message=f"设备 {device_data.get('name', '未知')} 已离线",
                device_id=device_data.get("id"),
                device_name=device_data.get("name"),
                room_id=device_data.get("room"),
                details={
                    "last_update": device_data.get("lastUpdate"),
                },
            )
        return None

    def _detect_battery_low(self, device_data: Dict) -> Optional[AnomalyResult]:
        battery = device_data.get("battery", -1)
        if battery >= 0 and battery <= self.battery_low_threshold:
            return AnomalyResult(
                anomaly_type=AnomalyType.BATTERY_LOW,
                severity="warning",
                message=f"设备 {device_data.get('name', '未知')} 电量低 ({battery}%)",
                device_id=device_data.get("id"),
                device_name=device_data.get("name"),
                room_id=device_data.get("room"),
                details={
                    "battery_level": battery,
                },
            )
        return None

    def _detect_environment_anomaly(self, device_data: Dict) -> Optional[AnomalyResult]:
        anomalies = []
        
        if device_data.get("temperature") is not None:
            temp = device_data["temperature"]
            if temp < self.temperature_normal_range[0]:
                anomalies.append(f"温度过低 ({temp}°C)")
            elif temp > self.temperature_normal_range[1]:
                anomalies.append(f"温度过高 ({temp}°C)")
        
        if device_data.get("humidity") is not None:
            humidity = device_data["humidity"]
            if humidity < self.humidity_normal_range[0]:
                anomalies.append(f"湿度太低 ({humidity}%RH)")
            elif humidity > self.humidity_normal_range[1]:
                anomalies.append(f"湿度太高 ({humidity}%RH)")
        
        if device_data.get("co2") is not None and device_data["co2"] > self.co2_normal_limit:
            anomalies.append(f"CO2浓度过高 ({device_data['co2']} ppm)")
        
        if device_data.get("pm25") is not None and device_data["pm25"] > self.pm25_normal_limit:
            anomalies.append(f"PM2.5超标 ({device_data['pm25']} μg/m³)")
        
        if anomalies:
            return AnomalyResult(
                anomaly_type=AnomalyType.ENVIRONMENT,
                severity="warning" if len(anomalies) <= 2 else "critical",
                message=f"环境异常: {', '.join(anomalies)}",
                device_id=device_data.get("id"),
                device_name=device_data.get("name"),
                room_id=device_data.get("room"),
                details={
                    "temperature": device_data.get("temperature"),
                    "humidity": device_data.get("humidity"),
                    "co2": device_data.get("co2"),
                    "pm25": device_data.get("pm25"),
                },
            )
        
        return None

    def _detect_sensor_state_anomaly(self, device_data: Dict) -> Optional[AnomalyResult]:
        device_type = device_data.get("type", "").lower()
        
        if "smoke" in device_type and device_data.get("smokeState") in (1, 2):
            return AnomalyResult(
                anomaly_type=AnomalyType.BEHAVIOR,
                severity="critical",
                message=f"烟雾报警！设备: {device_data.get('name', '未知')}",
                device_id=device_data.get("id"),
                device_name=device_data.get("name"),
                room_id=device_data.get("room"),
                details={"smoke_state": device_data.get("smokeState")},
            )
        
        if ("gas" in device_type or "co" in device_type) and device_data.get("gasState") in (1, 2):
            return AnomalyResult(
                anomaly_type=AnomalyType.BEHAVIOR,
                severity="critical",
                message=f"燃气泄漏报警！设备: {device_data.get('name', '未知')}",
                device_id=device_data.get("id"),
                device_name=device_data.get("name"),
                room_id=device_data.get("room"),
                details={"gas_state": device_data.get("gasState")},
            )
        
        if "water" in device_type and device_data.get("waterState") == 1:
            return AnomalyResult(
                anomaly_type=AnomalyType.BEHAVIOR,
                severity="critical",
                message=f"水浸报警！设备: {device_data.get('name', '未知')}",
                device_id=device_data.get("id"),
                device_name=device_data.get("name"),
                room_id=device_data.get("room"),
                details={"water_state": device_data.get("waterState")},
            )
        
        if device_data.get("tamperState") == 1:
            return AnomalyResult(
                anomaly_type=AnomalyType.BEHAVIOR,
                severity="warning",
                message=f"防拆触发！设备: {device_data.get('name', '未知')}",
                device_id=device_data.get("id"),
                device_name=device_data.get("name"),
                room_id=device_data.get("room"),
                details={"tamper_state": device_data.get("tamperState")},
            )
        
        if device_data.get("sensorLifeStatus") == 1:
            return AnomalyResult(
                anomaly_type=AnomalyType.ENVIRONMENT,
                severity="warning",
                message=f"传感器寿命到期！设备: {device_data.get('name', '未知')}",
                device_id=device_data.get("id"),
                device_name=device_data.get("name"),
                room_id=device_data.get("room"),
                details={"sensor_life_status": device_data.get("sensorLifeStatus")},
            )
        
        return None

    def _combine_anomalies(self, results: List[AnomalyResult]) -> AnomalyResult:
        messages = [r.message for r in results]
        severities = [r.severity for r in results]
        severity = "critical" if "critical" in severities else "warning"
        
        return AnomalyResult(
            anomaly_type=AnomalyType.COMBINATION,
            severity=severity,
            message=f"组合异常: {'；'.join(messages)}",
            timestamp=datetime.now(),
            details={"sub_anomalies": [r.to_dict() for r in results]},
        )

    def detect_batch(self, devices_data: List[Dict]) -> List[AnomalyResult]:
        results = []
        for device_data in devices_data:
            result = self.detect(device_data)
            if result:
                results.append(result)
        return results

    def detect_behavior_anomaly(
        self, events: List[Dict], current_time: Optional[datetime] = None
    ) -> Optional[AnomalyResult]:
        if not events:
            return None
        
        now = current_time or datetime.now()
        hour = now.hour
        
        door_events = [e for e in events if "door" in e.get("type", "").lower()]
        motion_events = [e for e in events if "motion" in e.get("type", "").lower()]
        
        is_night = hour < 6 or hour >= 22
        
        if is_night and door_events:
            return AnomalyResult(
                anomaly_type=AnomalyType.BEHAVIOR,
                severity="warning",
                message=f"夜间检测到开门事件，当前时间: {now.strftime('%H:%M')}",
                timestamp=now,
                details={
                    "hour": hour,
                    "door_events_count": len(door_events),
                    "motion_events_count": len(motion_events),
                },
            )
        
        if motion_events and not door_events and is_night:
            return AnomalyResult(
                anomaly_type=AnomalyType.BEHAVIOR,
                severity="warning",
                message=f"夜间检测到移动但无开门记录，可能存在异常",
                timestamp=now,
                details={
                    "hour": hour,
                    "motion_events_count": len(motion_events),
                },
            )
        
        return None
