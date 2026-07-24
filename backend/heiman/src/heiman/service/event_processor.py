import asyncio
import json
import logging
import re
import threading
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any, List

from heiman.database.event_repo import get_event_repo
from heiman.schema.sensor import SensorEvent, SensorEventType, SensorEventLevel

logger = logging.getLogger(__name__)

# 所有告警类型都应触发 LLM 深度分析
CRITICAL_EVENT_TYPES = {
    "smoke_alarm",
    "co_alarm",
    "water_leak",
    "switch_alarm",
    "contact_alarm",
    "tamper_alarm",
    "siren_alarm",
    "button_alarm",
    "plug_alarm",
    "remote_alarm",
    "motion_alarm",
    "device_offline",
    "tamper_alarm",
    "switch_alarm",
}

DEVICE_EVENT_TOPIC_PATTERN = re.compile(
    r'^/iot/app/11/[^/]+/([^/]+)/([^/]+)/event/([^/]+)$'
)

CHILD_DEVICE_EVENT_TOPIC_PATTERN = re.compile(
    r'^/iot/app/11/[^/]+/[^/]+/[^/]+/child/([^/]+)/event/([^/]+)$'
)

EVENT_TYPE_MAPPING = {
    "LowElectricityAlarm": ("low_battery", SensorEventLevel.WARNING),
    "TamperAlarm": ("tamper_alarm", SensorEventLevel.CRITICAL),
    "SmokeAlarm": ("smoke_alarm", SensorEventLevel.CRITICAL),
    "CoAlarm": ("co_alarm", SensorEventLevel.CRITICAL),
    "WaterLeak": ("water_leak", SensorEventLevel.CRITICAL),
    "DoorOpen": ("contact_alarm", SensorEventLevel.WARNING),
    "MotionDetected": ("motion_detected", SensorEventLevel.INFO),
    "TemperatureHigh": ("temperature_high", SensorEventLevel.WARNING),
    "TemperatureLow": ("temperature_low", SensorEventLevel.WARNING),
    "HumidityHigh": ("humidity_high", SensorEventLevel.WARNING),
    "HumidityLow": ("humidity_low", SensorEventLevel.WARNING),
    "Offline": ("device_offline", SensorEventLevel.WARNING),
    "Online": ("device_online", SensorEventLevel.INFO),
    "SwitchAlarm": ("switch_alarm", SensorEventLevel.CRITICAL),
}

EVENT_DESCRIPTIONS = {
    "low_battery": "设备电量低告警",
    "tamper_alarm": "设备拆动告警",
    "smoke_alarm": "烟雾告警",
    "co_alarm": "一氧化碳告警",
    "water_leak": "漏水告警",
    "contact_alarm": "门窗打开",
    "motion_detected": "移动侦测",
    "temperature_high": "温度过高告警",
    "temperature_low": "温度过低告警",
    "humidity_high": "湿度高告警",
    "humidity_low": "湿度低告警",
    "device_offline": "设备离线",
    "device_online": "设备上线",
    "switch_alarm": "开关告警",
}


class ParsedEvent:
    product_id: str
    device_id: str
    child_device_id: Optional[str]
    event_id: str
    payload: dict
    timestamp: datetime
    is_child_device: bool
    device_name: Optional[str]
    sensor_type: Optional[str]
    gw_product_id: Optional[str]
    gw_device_id: Optional[str]

    def __init__(self, product_id: str, device_id: str, event_id: str,
                 payload: dict, timestamp: datetime,
                 child_device_id: Optional[str] = None,
                 gw_product_id: Optional[str] = None,
                 gw_device_id: Optional[str] = None):
        self.product_id = product_id
        self.device_id = device_id
        self.child_device_id = child_device_id
        self.event_id = event_id
        self.payload = payload
        self.timestamp = timestamp
        self.is_child_device = child_device_id is not None
        self.device_name = None
        self.sensor_type = None
        self.gw_product_id = gw_product_id
        self.gw_device_id = gw_device_id


class EventProcessor:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._event_repo = get_event_repo()
        self._processing_lock = threading.Lock()
        self._processed_count = 0
        self._error_count = 0
        self._initialized = True
        logger.info("[EventProcessor] EventProcessor initialized")

    def parse_topic(self, topic: str) -> Optional[ParsedEvent]:
        child_match = CHILD_DEVICE_EVENT_TOPIC_PATTERN.match(topic)
        if child_match:
            device_id = child_match.group(1)
            event_id = child_match.group(2)
            
            parts = topic.strip('/').split('/')
            gw_product_id = None
            gw_device_id = None
            if len(parts) >= 6:
                gw_product_id = parts[4]
                gw_device_id = parts[5]
            
            return ParsedEvent(
                product_id="",
                device_id=device_id,
                child_device_id=device_id,
                event_id=event_id,
                payload={},
                timestamp=datetime.now(),
                gw_product_id=gw_product_id,
                gw_device_id=gw_device_id,
            )

        device_match = DEVICE_EVENT_TOPIC_PATTERN.match(topic)
        if device_match:
            product_id = device_match.group(1)
            device_id = device_match.group(2)
            event_id = device_match.group(3)
            return ParsedEvent(
                product_id=product_id,
                device_id=device_id,
                event_id=event_id,
                payload={},
                timestamp=datetime.now(),
            )

        return None

    def validate_payload(self, payload: dict) -> Tuple[bool, str]:
        if not isinstance(payload, dict):
            return False, "Payload must be a dictionary"

        if "timestamp" not in payload:
            logger.debug("[EventProcessor] Payload missing timestamp, using current time")

        if "messageId" not in payload:
            logger.debug("[EventProcessor] Payload missing messageId")

        if "data" not in payload:
            logger.debug("[EventProcessor] Payload missing data field")

        return True, ""

    def extract_timestamp(self, payload: dict) -> datetime:
        timestamp = payload.get("timestamp")
        if isinstance(timestamp, int):
            if timestamp > 1e12:
                timestamp = timestamp / 1000.0
            return datetime.fromtimestamp(timestamp)
        return datetime.now()

    def map_event_type(self, event_id: str) -> Tuple[str, SensorEventLevel]:
        mapped = EVENT_TYPE_MAPPING.get(event_id)
        if mapped:
            return mapped
        return (event_id.lower(), SensorEventLevel.INFO)

    def _determine_switch_alarm_level(self, event_id: str, payload: dict) -> SensorEventLevel:
        if event_id != "SwitchAlarm":
            return EVENT_TYPE_MAPPING.get(event_id, (event_id.lower(), SensorEventLevel.INFO))[1]

        data = payload.get("data", {})
        switch_state = data.get("SwitchState", data.get("switchState", 0))

        if switch_state == 3 or switch_state == 1:
            return SensorEventLevel.CRITICAL
        elif switch_state == 2 or switch_state == 0:
            return SensorEventLevel.INFO
        else:
            return SensorEventLevel.WARNING

    def _resolve_device_info(self, parsed: ParsedEvent) -> None:
        payload = parsed.payload or {}
        logger.info("[EventProcessor] _resolve_device_info - product_id before: %s", parsed.product_id)
        
        if isinstance(payload, dict):
            if not parsed.product_id or parsed.product_id == "heiman":
                if "productId" in payload:
                    parsed.product_id = payload["productId"]
                    logger.info("[EventProcessor] _resolve_device_info - product_id overwritten from payload: %s", parsed.product_id)
                elif "data" in payload and isinstance(payload["data"], dict):
                    data = payload["data"]
                    if "productId" in data:
                        parsed.product_id = data["productId"]
                    elif isinstance(data.get("device"), dict) and "productId" in data["device"]:
                        parsed.product_id = data["device"]["productId"]
                elif isinstance(payload.get("device"), dict) and "productId" in payload["device"]:
                    parsed.product_id = payload["device"]["productId"]

        if not parsed.product_id:
            parsed.product_id = "heiman"

        try:
            from heiman.manager import get_manager
            mgr = get_manager()
            devices = mgr.adapter.get_connected_devices()
            
            target_did = parsed.child_device_id if parsed.is_child_device else parsed.device_id
            if target_did in devices:
                device = devices[target_did]
                parsed.device_name = device.name
                parsed.sensor_type = device.device_type
            else:
                try:
                    from heiman.dependencies import get_collector
                    collector = get_collector()
                    device_data = collector.collect(target_did, drain=False)
                    if device_data and device_data.meta:
                        parsed.device_name = device_data.meta.name
                        parsed.sensor_type = device_data.meta.device_type
                except Exception as e:
                    logger.debug("[EventProcessor] Failed to get device from collector: %s", e)
            
            if not parsed.device_name or parsed.device_name == target_did or parsed.device_name.startswith("Device "):
                try:
                    from heiman.database.connector import get_db_connector
                    from heiman.database.product_repo import ProductRepo
                    db = get_db_connector()
                    repo = ProductRepo(db)
                    
                    cursor = db.get_connection().cursor()
                    cursor.execute(
                        "SELECT sensor_type, raw_properties FROM sensor_logs WHERE did = ? AND (sensor_type IS NOT NULL OR raw_properties IS NOT NULL) ORDER BY id DESC LIMIT 1",
                        (target_did,)
                    )
                    row = cursor.fetchone()
                    if row:
                        db_sensor_type = row[0] if row[0] else None
                        raw_props_str = row[1] if row[1] else None
                        
                        if db_sensor_type and db_sensor_type != "" and not parsed.sensor_type:
                            parsed.sensor_type = db_sensor_type
                            logger.info("[EventProcessor] _resolve_device_info - sensor_type from sensor_logs: %s", db_sensor_type)
                        
                        if raw_props_str:
                            try:
                                import json
                                raw_props = json.loads(raw_props_str)
                                if isinstance(raw_props, dict):
                                    if not parsed.sensor_type:
                                        sensor_type_val = raw_props.get("sensor_type", raw_props.get("sensorType", ""))
                                        if sensor_type_val:
                                            parsed.sensor_type = str(sensor_type_val)
                                            logger.info("[EventProcessor] _resolve_device_info - sensor_type from raw_properties: %s", parsed.sensor_type)
                                    props_name = raw_props.get("name", raw_props.get("deviceName", ""))
                                    if props_name and props_name != target_did and not props_name.startswith("Device "):
                                        parsed.device_name = props_name
                            except (json.JSONDecodeError, TypeError):
                                pass
                    
                    if not parsed.device_name or parsed.device_name == target_did or parsed.device_name.startswith("Device "):
                        if parsed.product_id and parsed.product_id != "heiman":
                            product_info = repo.get_product(parsed.product_id)
                            if product_info:
                                parsed.device_name = product_info.get("name", target_did)
                        elif parsed.sensor_type:
                            sensor_type_names = {
                                "plug": "智能插座",
                                "contact": "门磁探测器",
                                "motion": "移动探测器",
                                "smoke": "烟雾探测器",
                                "co": "一氧化碳探测器",
                                "water": "水浸探测器",
                                "temperature": "温度传感器",
                                "humidity": "湿度传感器",
                                "siren": "声光报警器",
                            }
                            parsed.device_name = sensor_type_names.get(parsed.sensor_type, f"Device {target_did[:8]}")
                except Exception as e:
                    logger.debug("[EventProcessor] Failed to get device name from database: %s", e)
            logger.info("[EventProcessor] _resolve_device_info - product_id after: %s", parsed.product_id)
        except Exception as e:
            logger.debug("[EventProcessor] Failed to resolve device info: %s", e)

    def build_sensor_event(self, parsed: ParsedEvent) -> SensorEvent:
        event_type_str, base_level = self.map_event_type(parsed.event_id)
        
        if event_type_str == "switch_alarm":
            level = self._determine_switch_alarm_level(parsed.event_id, parsed.payload)
            
            sensor_type = parsed.sensor_type or ""
            data = parsed.payload.get("data", {})
            switch_state = data.get("SwitchState", data.get("switchState", 0))
            
            device_name = parsed.device_name or ""
            device_name_lower = device_name.lower()
            
            is_contact = False
            is_plug = False
            
            if "contact" in sensor_type.lower():
                is_contact = True
            elif "plug" in sensor_type.lower():
                is_plug = True
            elif "门磁" in device_name or "门窗" in device_name:
                is_contact = True
            elif "插座" in device_name:
                is_plug = True
            elif parsed.product_id:
                try:
                    from heiman.database.connector import get_db_connector
                    from heiman.database.product_repo import ProductRepo
                    db = get_db_connector()
                    repo = ProductRepo(db)
                    product_info = repo.get_product(parsed.product_id)
                    if product_info:
                        db_product_name = product_info.get("name", "")
                        if "门磁" in db_product_name or "门窗" in db_product_name or "contact" in db_product_name.lower():
                            is_contact = True
                        elif "插座" in db_product_name or "plug" in db_product_name.lower():
                            is_plug = True
                except Exception as e:
                    logger.debug("[EventProcessor] Failed to get product info: %s", e)
            
            if is_contact:
                if switch_state == 3 or switch_state == 1:
                    description = "门窗打开"
                elif switch_state == 2 or switch_state == 0:
                    description = "门窗关闭"
                else:
                    description = "门窗状态变更"
            elif is_plug:
                if switch_state == 3 or switch_state == 1:
                    description = "插座开启"
                elif switch_state == 2 or switch_state == 0:
                    description = "插座关闭"
                else:
                    description = "插座状态变更"
            elif sensor_type == "motion" or sensor_type == "pir":
                if switch_state == 2:
                    description = "检测到移动"
                elif switch_state == 3:
                    description = "移动结束"
                else:
                    description = "移动状态变更"
            else:
                description = EVENT_DESCRIPTIONS.get(event_type_str, f"事件: {parsed.event_id}")
        else:
            level = base_level
            description = EVENT_DESCRIPTIONS.get(event_type_str, f"事件: {parsed.event_id}")

        try:
            event_type_enum = SensorEventType(event_type_str)
        except ValueError:
            try:
                enum_name = event_type_str.upper()
                event_type_enum = SensorEventType[enum_name]
            except (KeyError, AttributeError):
                event_type_enum = SensorEventType.ALARM

        target_device_id = parsed.child_device_id if parsed.is_child_device else parsed.device_id
        
        device_name = parsed.device_name if parsed.device_name else target_device_id

        return SensorEvent(
            event_id=f"{target_device_id}_{parsed.event_id}_{int(parsed.timestamp.timestamp() * 1000)}",
            event_type=event_type_enum,
            level=level,
            did=target_device_id,
            device_name=device_name,
            room_name=None,
            home_id=None,
            product_id=parsed.product_id,
            child_device_id=parsed.child_device_id,
            description=description,
            raw_data={
                "productId": parsed.product_id,
                "deviceId": parsed.device_id,
                "childDeviceId": parsed.child_device_id,
                "eventId": parsed.event_id,
                "payload": parsed.payload,
                "sensorType": parsed.sensor_type,
                "deviceName": device_name,
            },
            timestamp=parsed.timestamp,
            acknowledged=False,
        )

    async def process_event(self, topic: str, payload: dict) -> bool:
        with self._processing_lock:
            try:
                logger.info("[EventProcessor] Processing event from topic: %s", topic)

                parsed = self.parse_topic(topic)
                if not parsed:
                    logger.error("[EventProcessor] Failed to parse topic: %s", topic)
                    self._error_count += 1
                    return False

                valid, error_msg = self.validate_payload(payload)
                if not valid:
                    logger.error("[EventProcessor] Invalid payload: %s", error_msg)
                    self._error_count += 1
                    return False

                parsed.payload = payload
                parsed.timestamp = self.extract_timestamp(payload)

                product_id = parsed.product_id
                logger.info("[EventProcessor] product_id from topic: %s", product_id)
                
                if not product_id or product_id == "heiman":
                    payload_product_id = payload.get("productId", "")
                    if payload_product_id and payload_product_id != "heiman":
                        product_id = payload_product_id
                        logger.info("[EventProcessor] product_id from payload: %s", product_id)
                    else:
                        try:
                            from heiman.database.connector import get_db_connector
                            from heiman.database.product_repo import ProductRepo
                            db = get_db_connector()
                            repo = ProductRepo(db)
                            
                            valid_product_id = None
                            fallback_product_id = None
                            
                            with db.get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "SELECT DISTINCT product_id FROM sensor_logs WHERE did = ? AND product_id IS NOT NULL AND product_id != '' ORDER BY id DESC",
                                    (parsed.device_id,)
                                )
                                rows = cursor.fetchall()
                                
                                for row in rows:
                                    pid = str(row[0])
                                    if pid:
                                        if fallback_product_id is None:
                                            fallback_product_id = pid
                                        product_info = repo.get_product(pid)
                                        if product_info:
                                            classified_name = product_info.get("classified_name", "")
                                            product_name = product_info.get("name", "")
                                            if "网关" not in classified_name and "网关" not in product_name:
                                                valid_product_id = pid
                                                logger.info("[EventProcessor] Resolved product_id from sensor_logs (non-gateway): %s", valid_product_id)
                                                break
                            
                            if valid_product_id:
                                product_id = valid_product_id
                            elif fallback_product_id:
                                product_info = repo.get_product(fallback_product_id)
                                if product_info:
                                    product_id = fallback_product_id
                                    logger.info("[EventProcessor] Resolved product_id from sensor_logs (fallback): %s", product_id)
                                else:
                                    logger.info("[EventProcessor] product_id %s not found in dev_product, will use sensor_type for device classification", fallback_product_id)
                        except Exception as e:
                            logger.error("[EventProcessor] Failed to resolve product_id from sensor_logs: %s", e)
                parsed.product_id = product_id
                logger.info("[EventProcessor] Final product_id: %s", parsed.product_id)

                self._resolve_device_info(parsed)

                sensor_event = self.build_sensor_event(parsed)

                self._event_repo.insert(sensor_event)

                await self.publish_to_event_bus(sensor_event)

                self._processed_count += 1
                logger.info(
                    "[EventProcessor] Event processed successfully - event_id=%s, type=%s, level=%s, is_child=%s",
                    sensor_event.event_id,
                    sensor_event.event_type.value,
                    sensor_event.level.value,
                    parsed.is_child_device,
                )

                self._trigger_ai_analysis(sensor_event, parsed.device_id)

                return True

            except Exception as e:
                logger.error(
                    "[EventProcessor] Error processing event from topic %s: %s",
                    topic,
                    str(e),
                    exc_info=True,
                )
                self._error_count += 1
                return False

    async def publish_to_event_bus(self, event: SensorEvent):
        try:
            from heiman.service.event_bus import get_event_bus

            bus = get_event_bus()
            await bus.publish({
                "event": "device_event",
                "id": event.event_id,
                "data": {
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "level": event.level.value,
                    "did": event.did,
                    "device_name": event.device_name,
                    "description": event.description,
                    "timestamp": event.timestamp.isoformat(),
                    "acknowledged": event.acknowledged,
                    "raw_data": event.raw_data,
                },
            })
            logger.debug("[EventProcessor] Event published to event bus: %s", event.event_id)
        except Exception as e:
            logger.warning("[EventProcessor] Failed to publish to event bus: %s", e)

    def _trigger_ai_analysis(self, sensor_event: SensorEvent, device_id: str) -> None:
        event_type = sensor_event.event_type.value

        if event_type in CRITICAL_EVENT_TYPES or sensor_event.level == SensorEventLevel.CRITICAL:
            logger.info(
                "[EventProcessor] Critical event detected - triggering AI analysis: %s",
                event_type,
            )
            asyncio.create_task(self._execute_ai_analysis(sensor_event, device_id))

        asyncio.create_task(self._process_behavior_learning(sensor_event))

    async def _process_behavior_learning(self, sensor_event: SensorEvent) -> None:
        try:
            from heiman.ai.smart_rule_generator import SmartRuleGenerator

            generator = SmartRuleGenerator()

            event_for_learning = {
                "user_id": "default",
                "type": sensor_event.event_type.value,
                "timestamp": sensor_event.timestamp.timestamp(),
                "did": sensor_event.did,
                "device_name": sensor_event.device_name,
                "level": sensor_event.level.value,
                "description": sensor_event.description,
            }

            await generator.process_event_for_learning(event_for_learning)
            logger.debug("[EventProcessor] Behavior learning processed for event: %s", sensor_event.event_type.value)

        except Exception as e:
            logger.warning("[EventProcessor] Failed to process behavior learning: %s", e)

    async def _execute_ai_analysis(self, sensor_event: SensorEvent, device_id: str) -> None:
        try:
            from heiman.ai.anomaly_detector_v2 import get_anomaly_detector_v2
            from heiman.ai.decision_engine_v2 import get_decision_engine_v2
            from heiman.ai.comfort_evaluator_v2 import get_comfort_evaluator_v2
            from heiman.ai.behavior_recognizer_v2 import get_behavior_recognizer_v2
            from heiman.database.connector import get_db_connector

            logger.info("[EventProcessor] Executing V2 AI analysis for device: %s", device_id)

            anomaly_detector = get_anomaly_detector_v2()
            decision_engine = get_decision_engine_v2()
            comfort_evaluator = get_comfort_evaluator_v2()
            behavior_recognizer = get_behavior_recognizer_v2()

            all_devices = await self._get_all_devices_for_analysis()
            if not all_devices:
                logger.warning("[EventProcessor] No devices available for AI analysis")
                return

            anomalies = anomaly_detector.detect_batch(all_devices)

            analysis_result = await decision_engine.analyze_home_fused()
            if analysis_result is None:
                analysis_result = {"decision": "no_action", "confidence": 0, "reasoning": "no_ml_model_loaded"}
            await self._store_ai_analysis_result(analysis_result)

            if anomalies:
                logger.info("[EventProcessor] AI analysis detected %d anomalies", len(anomalies))
                for anomaly in anomalies:
                    logger.info(
                        "[EventProcessor] Anomaly detected: type=%s, severity=%s, message=%s",
                        anomaly.anomaly_type.value,
                        anomaly.severity,
                        anomaly.message,
                    )

            # --- 告警事件规则引擎分析（ML 分析之后） ---
            if sensor_event.event_type.value in CRITICAL_EVENT_TYPES:
                await self._execute_alert_analysis(
                    sensor_event=sensor_event,
                    analysis_result=analysis_result,
                    anomalies=anomalies,
                    all_devices=all_devices,
                )

            logger.info("[EventProcessor] AI analysis completed successfully")

        except Exception as e:
            logger.error(
                "[EventProcessor] Error executing AI analysis: %s",
                e,
                exc_info=True,
            )

    async def _execute_alert_analysis(
        self,
        sensor_event: SensorEvent,
        analysis_result: Dict[str, Any],
        anomalies: List[Any],
        all_devices: List[Dict[str, Any]],
    ) -> None:
        """在 ML 分析之后，对关键告警执行规则引擎深度分析。"""
        try:
            from heiman.ai.alert_analyzer import AlertContext, get_alert_analyzer, init_alert_analyzer
            from heiman.database.connector import get_db_connector
            from heiman.manager import get_manager

            # 确保 AlertAnalyzer 已初始化
            try:
                analyzer = get_alert_analyzer()
            except RuntimeError:
                db = get_db_connector()
                mgr = get_manager()
                analyzer = init_alert_analyzer(db=db)

            # 获取设备详细信息
            mgr = get_manager()
            device = mgr.adapter.get_connected_devices().get(sensor_event.did)

            # 构建历史事件上下文
            event_repo = self._event_repo
            twenty_four_hours_ago = (datetime.now() - timedelta(hours=24)).isoformat()

            # 查询同设备的历史事件
            recent_events = event_repo.query(
                did=sensor_event.did,
                after=twenty_four_hours_ago,
                limit=20,
            )

            # 查询系统日志（最近 20 条）
            system_logs: List[Dict[str, Any]] = []
            try:
                db = get_db_connector()
                with db.get_connection() as conn:
                    # 确保行以 dict 方式返回
                    conn.row_factory = type(conn).row_factory
                    log_rows = conn.execute(
                        "SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT 20"
                    ).fetchall()
                    system_logs = [dict(r) for r in log_rows]
            except Exception:
                pass  # 系统日志表可能不存在

            # 查询最近传感器读数
            recent_readings: List[Dict[str, Any]] = []
            try:
                db = get_db_connector()
                with db.get_connection() as conn:
                    reading_rows = conn.execute(
                        "SELECT * FROM sensor_logs WHERE did = ? ORDER BY timestamp DESC LIMIT 10",
                        (sensor_event.did,),
                    ).fetchall()
                    recent_readings = [dict(r) for r in reading_rows]
            except Exception:
                pass

            # 收集当前传感器指标
            current_values: Dict[str, Any] = {}
            if device:
                current_values = {
                    "temperature": getattr(device, "temperature", None),
                    "humidity": getattr(device, "humidity", None),
                    "smoke_ppm": getattr(device, "smoke_ppm", None),
                    "co_ppm": getattr(device, "co_ppm", None),
                    "battery": getattr(device, "battery", None),
                    "signal_strength": getattr(device, "signal_strength", None),
                }
                current_values = {k: v for k, v in current_values.items() if v is not None}

            # 设备配置
            device_config: Dict[str, Any] = {}
            if device:
                device_config = {
                    "model": getattr(device, "model", ""),
                    "firmware": getattr(device, "firmware", ""),
                    "sensor_type": getattr(device, "device_type", ""),
                    "thresholds": getattr(device, "thresholds", {}),
                    "capabilities": getattr(device, "capabilities", []),
                }

            # 关联设备（同房间）
            room = getattr(device, "room", "") if device else sensor_event.room_name
            related_devices = [
                {
                    "id": d.get("id", ""),
                    "name": d.get("name", ""),
                    "type": d.get("type", ""),
                    "status": d.get("status", ""),
                }
                for d in all_devices
                if d.get("room") == room and d.get("id") != sensor_event.did
            ]

            # 提取 ML 分析结果
            anomalies_data = []
            for a in anomalies:
                anomalies_data.append({
                    "type": getattr(a, "anomaly_type", ""),
                    "severity": getattr(a, "severity", ""),
                    "message": getattr(a, "message", ""),
                    "score": getattr(a, "score", 0),
                } if hasattr(a, "anomaly_type") else str(a))

            comfort = analysis_result.get("comfort", {})
            comfort_score = comfort.get("score", 0) if isinstance(comfort, dict) else 0
            behavior = analysis_result.get("behavior", {})
            behavior_data = {
                "activity": behavior.get("activity", "") if isinstance(behavior, dict) else "",
                "confidence": behavior.get("confidence", 0) if isinstance(behavior, dict) else 0,
            } if isinstance(behavior, dict) else {}

            # 构建上下文
            context = AlertContext(
                event_id=sensor_event.event_id,
                event_type=sensor_event.event_type.value,
                device_id=sensor_event.did,
                device_name=sensor_event.device_name or f"Device_{sensor_event.did[:8]}",
                device_type=getattr(device, "device_type", "") if device else "",
                room_name=sensor_event.room_name or room or "",
                home_id=sensor_event.home_id or "",
                current_values=current_values,
                historical_events_count=len(recent_events),
                recent_events=[dict(r) for r in recent_events[:10]],
                recent_readings=recent_readings[:10],
                device_config=device_config,
                related_devices=related_devices,
                anomaly_score=analysis_result.get("anomaly_score", 0.0),
                anomalies=anomalies_data,
                comfort_score=comfort_score,
                behavior_analysis=behavior_data,
                system_logs=system_logs[:5],
                timestamp_ms=int(sensor_event.timestamp.timestamp() * 1000) if sensor_event.timestamp else 0,
                timestamp_iso=sensor_event.timestamp.isoformat() if sensor_event.timestamp else datetime.now().isoformat(),
            )

            logger.info(
                "[EventProcessor] Triggering rule-engine alert analysis | event=%s type=%s device=%s",
                context.event_id, context.event_type, context.device_name,
            )

            # 执行规则引擎分析（纯本地计算，不调用 LLM）
            result = await analyzer.analyze(context, store=True)

            if result.success:
                logger.info(
                    "[EventProcessor] Alert analysis complete | event=%s urgency=%s remediation_steps=%d",
                    context.event_id, result.urgency_level, len(result.remediation_steps),
                )
            else:
                logger.error(
                    "[EventProcessor] Alert analysis failed | event=%s error=%s",
                    context.event_id, result.error_message,
                )

        except Exception as e:
            logger.error(
                "[EventProcessor] Alert analysis error | event=%s error=%s",
                getattr(sensor_event, "event_id", "unknown"), e, exc_info=True,
            )

    async def _get_all_devices_for_analysis(self) -> list:
        try:
            from heiman.manager import get_manager

            mgr = get_manager()
            perception_devices = mgr.adapter.get_connected_devices()

            result = []
            for did, device in perception_devices.items():
                device_data = {
                    "id": did,
                    "name": device.name,
                    "type": device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type),
                    "status": "online" if device.online else "offline",
                    "battery": None,
                    "room": device.room_name or "",
                    "lastUpdate": datetime.now().isoformat(),
                }
                # 从 sensor_data_cache 获取传感器实时读数
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
                        if dev_data.timestamp:
                            device_data["lastUpdate"] = dev_data.timestamp.isoformat()
                except Exception:
                    pass
                result.append(device_data)

            return result
        except Exception as e:
            logger.error("[EventProcessor] Error getting devices for analysis: %s", e)
            return []

    async def _store_ai_analysis_result(self, analysis_result: dict) -> None:
        try:
            from heiman.database.connector import get_db_connector

            db = get_db_connector()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                anomalies = analysis_result.get("anomalies", [])
                anomaly_count = len(anomalies) if isinstance(anomalies, list) else 0
                
                comfort = analysis_result.get("comfort", {})
                comfort_score = comfort.get("score", 0) if isinstance(comfort, dict) else 0
                
                activity = analysis_result.get("activity", {})
                activity_type = activity.get("activity", "") if isinstance(activity, dict) else ""
                
                cursor.execute(
                    """
                    INSERT INTO ai_analysis_results (
                        analysis_id, analysis_type, result_data, timestamp_ms,
                        anomaly_count, comfort_score, activity_type, home_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        analysis_result.get("type", "comprehensive"),
                        json.dumps(analysis_result),
                        int(datetime.now().timestamp() * 1000),
                        anomaly_count,
                        comfort_score,
                        activity_type,
                        analysis_result.get("home_id", ""),
                    ),
                )
                conn.commit()
            logger.info("[EventProcessor] AI analysis result stored")
        except Exception as e:
            logger.warning("[EventProcessor] Failed to store AI analysis result: %s", e)

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "processed_count": self._processed_count,
            "error_count": self._error_count,
        }


def get_event_processor() -> EventProcessor:
    return EventProcessor()