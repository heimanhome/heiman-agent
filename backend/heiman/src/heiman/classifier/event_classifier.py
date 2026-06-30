import logging
from datetime import datetime
from uuid import uuid4

from heiman.schema.sensor import (
    SensorData, SensorEvent, SensorEventLevel, SensorEventType, SensorStatus,
    SensorType,
)

logger = logging.getLogger(__name__)

ALARM_VALUE_MAP = {
    SensorType.SMOKE: [1, 2],
    SensorType.CO: [1, 2, 3],
    SensorType.WATER: [1],
    SensorType.CONTACT: [1],
    SensorType.MOTION: [1],
    SensorType.SIREN: [1, 3],
    SensorType.BUTTON: [1],
}


class EventClassifier:
    def classify(self, sensor_data: SensorData) -> list[SensorEvent]:
        events: list[SensorEvent] = []
        
        if sensor_data.status == SensorStatus.OFFLINE:
            events.append(self._create_offline_event(sensor_data))
        elif sensor_data.status == SensorStatus.ALARM:
            events.append(self._create_alarm_event(sensor_data))
        elif sensor_data.status == SensorStatus.WARNING:
            events.append(self._create_warning_event(sensor_data))
        elif sensor_data.status == SensorStatus.NORMAL:
            normal_event = self._create_normal_event(sensor_data)
            if normal_event:
                events.append(normal_event)
            
            if sensor_data.battery is not None and sensor_data.battery < 20:
                events.append(self._create_low_battery_event(sensor_data))
        
        return events
    
    def _create_offline_event(self, sensor_data: SensorData) -> SensorEvent:
        return SensorEvent(
            event_id=str(uuid4()),
            event_type=SensorEventType.DEVICE_OFFLINE,
            level=SensorEventLevel.WARNING,
            did=sensor_data.did,
            device_name=sensor_data.name,
            room_name=sensor_data.room_name or "未知区域",
            description=f"传感器 {sensor_data.name} 离线",
            raw_data=sensor_data.model_dump(),
            timestamp=sensor_data.timestamp,
            acknowledged=False,
        )
    
    def _create_alarm_event(self, sensor_data: SensorData) -> SensorEvent:
        descriptions = {
            SensorType.SMOKE: f"检测到烟雾！传感器 {sensor_data.name} 报警",
            SensorType.CO: f"检测到一氧化碳！浓度: {sensor_data.value} ppm",
            SensorType.WATER: f"检测到水浸！传感器 {sensor_data.name} 报警",
            SensorType.TEMPERATURE: f"温度过高！当前温度: {sensor_data.value}℃",
            SensorType.HUMIDITY: f"湿度异常！当前湿度: {sensor_data.value}%",
            SensorType.CONTACT: f"门窗被打开！传感器 {sensor_data.name} 报警",
            SensorType.MOTION: f"检测到移动！传感器 {sensor_data.name} 报警",
            SensorType.SIREN: f"声光警号触发！传感器 {sensor_data.name} 报警",
            SensorType.BUTTON: f"紧急按钮被触发！传感器 {sensor_data.name} 报警",
            SensorType.PLUG: f"设备状态异常！传感器 {sensor_data.name} 报警",
            SensorType.REMOTE: f"遥控器触发！传感器 {sensor_data.name} 报警",
        }
        
        return SensorEvent(
            event_id=str(uuid4()),
            event_type=self._get_event_type_for_alarm(sensor_data.sensor_type),
            level=SensorEventLevel.CRITICAL,
            did=sensor_data.did,
            device_name=sensor_data.name,
            room_name=sensor_data.room_name or "未知区域",
            description=descriptions.get(sensor_data.sensor_type, f"传感器 {sensor_data.name} 报警"),
            raw_data=sensor_data.model_dump(),
            timestamp=sensor_data.timestamp,
            acknowledged=False,
        )
    
    def _create_warning_event(self, sensor_data: SensorData) -> SensorEvent:
        descriptions = {
            SensorType.TEMPERATURE: f"温度异常警告！当前温度: {sensor_data.value}℃",
            SensorType.HUMIDITY: f"湿度异常警告！当前湿度: {sensor_data.value}%",
            SensorType.CO: f"一氧化碳浓度偏高！当前: {sensor_data.value} ppm",
            SensorType.SMOKE: f"烟雾传感器状态异常！传感器 {sensor_data.name}",
            SensorType.WATER: f"水浸传感器状态异常！传感器 {sensor_data.name}",
            SensorType.CONTACT: f"门磁传感器状态异常！传感器 {sensor_data.name}",
            SensorType.MOTION: f"人体传感器状态异常！传感器 {sensor_data.name}",
        }
        
        return SensorEvent(
            event_id=str(uuid4()),
            event_type=self._get_event_type_for_warning(sensor_data.sensor_type),
            level=SensorEventLevel.WARNING,
            did=sensor_data.did,
            device_name=sensor_data.name,
            room_name=sensor_data.room_name or "未知区域",
            description=descriptions.get(sensor_data.sensor_type, f"传感器 {sensor_data.name} 状态异常"),
            raw_data=sensor_data.model_dump(),
            timestamp=sensor_data.timestamp,
            acknowledged=False,
        )
    
    def _create_normal_event(self, sensor_data: SensorData) -> SensorEvent | None:
        if sensor_data.value is None:
            return None
        
        type_descriptions = {
            SensorType.TEMPERATURE: f"温度正常: {sensor_data.value}{sensor_data.unit}",
            SensorType.HUMIDITY: f"湿度正常: {sensor_data.value}{sensor_data.unit}",
            SensorType.CO: f"一氧化碳浓度正常: {sensor_data.value}{sensor_data.unit}",
            SensorType.SMOKE: "烟雾传感器正常",
            SensorType.WATER: "水浸传感器正常",
            SensorType.CONTACT: "门窗关闭正常",
            SensorType.MOTION: "人体传感器正常",
            SensorType.PLUG: f"设备状态正常: {'开启' if sensor_data.value > 0 else '关闭'}",
            SensorType.SIREN: "声光警号正常",
            SensorType.BUTTON: "紧急按钮正常",
            SensorType.REMOTE: "遥控器正常",
            SensorType.GATEWAY: "网关状态正常",
        }
        
        description = type_descriptions.get(
            sensor_data.sensor_type,
            f"传感器正常，值: {sensor_data.value}{sensor_data.unit}"
        )
        
        return SensorEvent(
            event_id=str(uuid4()),
            event_type=SensorEventType.STATUS_REPORT,
            level=SensorEventLevel.INFO,
            did=sensor_data.did,
            device_name=sensor_data.name,
            room_name=sensor_data.room_name or "未知区域",
            description=f"传感器 {sensor_data.name} {description}",
            raw_data=sensor_data.model_dump(),
            timestamp=sensor_data.timestamp,
            acknowledged=False,
        )
    
    def _create_low_battery_event(self, sensor_data: SensorData) -> SensorEvent:
        return SensorEvent(
            event_id=str(uuid4()),
            event_type=SensorEventType.LOW_BATTERY,
            level=SensorEventLevel.WARNING,
            did=sensor_data.did,
            device_name=sensor_data.name,
            room_name=sensor_data.room_name or "未知区域",
            description=f"传感器 {sensor_data.name} 电量低！当前电量: {sensor_data.battery}%",
            raw_data=sensor_data.model_dump(),
            timestamp=sensor_data.timestamp,
            acknowledged=False,
        )
    
    def _get_event_type_for_alarm(self, sensor_type: SensorType) -> SensorEventType:
        mapping = {
            SensorType.SMOKE: SensorEventType.SMOKE_ALARM,
            SensorType.CO: SensorEventType.CO_ALARM,
            SensorType.WATER: SensorEventType.WATER_ALARM,
            SensorType.TEMPERATURE: SensorEventType.TEMP_ALARM,
            SensorType.HUMIDITY: SensorEventType.HUMIDITY_ALARM,
            SensorType.CONTACT: SensorEventType.CONTACT_ALARM,
            SensorType.MOTION: SensorEventType.MOTION_ALARM,
            SensorType.SIREN: SensorEventType.SIREN_ALARM,
            SensorType.BUTTON: SensorEventType.BUTTON_ALARM,
            SensorType.PLUG: SensorEventType.PLUG_ALARM,
            SensorType.REMOTE: SensorEventType.REMOTE_ALARM,
        }
        return mapping.get(sensor_type, SensorEventType.ALARM)
    
    def _get_event_type_for_warning(self, sensor_type: SensorType) -> SensorEventType:
        mapping = {
            SensorType.TEMPERATURE: SensorEventType.TEMP_WARNING,
            SensorType.HUMIDITY: SensorEventType.HUMIDITY_WARNING,
            SensorType.CO: SensorEventType.CO_WARNING,
            SensorType.SMOKE: SensorEventType.SMOKE_WARNING,
            SensorType.WATER: SensorEventType.WATER_WARNING,
            SensorType.CONTACT: SensorEventType.CONTACT_WARNING,
            SensorType.MOTION: SensorEventType.MOTION_WARNING,
        }
        return mapping.get(sensor_type, SensorEventType.WARNING)