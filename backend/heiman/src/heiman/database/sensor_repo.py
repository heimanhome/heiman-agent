import logging
import json
from datetime import datetime, timedelta
from typing import Optional

from heiman.database.connector import transaction, execute_query, execute_update, execute_many
from heiman.schema.sensor import SensorData

logger = logging.getLogger(__name__)

_CACHE_EXPIRY_MINUTES = 5

PROPERTY_MAPPING = {
    "battery": {"property_id": "battery", "property_name": "电池", "unit": "%"},
    "rssi": {"property_id": "rssi", "property_name": "信号强度", "unit": "dBm"},
    "signalLevel": {"property_id": "SignalLevel", "property_name": "信号等级", "unit": ""},
    "contactState": {"property_id": "ContactState", "property_name": "门窗状态", "unit": ""},
    "switchState": {"property_id": "SwitchState", "property_name": "门窗状态", "unit": ""},
    "motionState": {"property_id": "MotionState", "property_name": "移动状态", "unit": ""},
    "gasState": {"property_id": "GasState", "property_name": "燃气状态", "unit": ""},
    "smokeState": {"property_id": "SmokeState", "property_name": "烟雾状态", "unit": ""},
    "waterState": {"property_id": "WaterState", "property_name": "漏水状态", "unit": ""},
    "alarmState": {"property_id": "AlarmState", "property_name": "告警状态", "unit": ""},
    "tamperState": {"property_id": "TamperState", "property_name": "防拆状态", "unit": ""},
    "temperature": {"property_id": "Temperature", "property_name": "温度", "unit": "°C"},
    "humidity": {"property_id": "Humidity", "property_name": "湿度", "unit": "%"},
    "co2": {"property_id": "CO2", "property_name": "二氧化碳", "unit": "ppm"},
    "pm25": {"property_id": "PM25", "property_name": "PM2.5", "unit": "μg/m³"},
    "pm10": {"property_id": "PM10", "property_name": "PM10", "unit": "μg/m³"},
    "hcho": {"property_id": "HCHO", "property_name": "甲醛", "unit": "mg/m³"},
    "sensorLifeStatus": {"property_id": "SensorLifeStatus", "property_name": "传感器寿命状态", "unit": ""},
    "GatewayMac": {"property_id": "GatewayMac", "property_name": "绑定网关的名称", "unit": ""},
    "StateTime": {"property_id": "StateTime", "property_name": "状态改变时间", "unit": ""},
    "BindList": {"property_id": "BindList", "property_name": "设备绑定合集", "unit": ""},
    "OF": {"property_id": "OF", "property_name": "存在状态", "unit": ""},
    "DT": {"property_id": "DT", "property_name": "占位延迟", "unit": "秒"},
    "LVL": {"property_id": "LVL", "property_name": "光照度阈值", "unit": "lux"},
    "MeasuredIlluminance": {"property_id": "MeasuredIlluminance", "property_name": "光照度检测值", "unit": "lux"},
    "Bind": {"property_id": "Bind", "property_name": "绑定设备", "unit": ""},
    "IMEI": {"property_id": "IMEI", "property_name": "IMEI", "unit": ""},
    "IMSI": {"property_id": "IMSI", "property_name": "IMSI", "unit": ""},
    "ICCID": {"property_id": "ICCID", "property_name": "ICCID", "unit": ""},
    "terminal_type": {"property_id": "terminal_type", "property_name": "终端型号", "unit": ""},
    "IOTVersion": {"property_id": "IOTVersion", "property_name": "模组固件版本", "unit": ""},
    "software_version": {"property_id": "software_version", "property_name": "通讯MCU固件版本", "unit": ""},
    "hwVer": {"property_id": "hwVer", "property_name": "硬件版本", "unit": ""},
    "gasFix": {"property_id": "gasFix", "property_name": "传感器数据", "unit": ""},
    "rsrp": {"property_id": "rsrp", "property_name": "参考信号接收功率", "unit": "dBm"},
    "rsrq": {"property_id": "rsrq", "property_name": "信号质量", "unit": "dB"},
    "snr": {"property_id": "snr", "property_name": "信噪比", "unit": "dB"},
    "pci": {"property_id": "pci", "property_name": "小区标识", "unit": ""},
    "CELLID": {"property_id": "CELLID", "property_name": "小区ID", "unit": ""},
    "TimeZone": {"property_id": "TimeZone", "property_name": "设备时区", "unit": ""},
    "DeviceINFO": {"property_id": "DeviceINFO", "property_name": "设备基本信息", "unit": ""},
    "MAC": {"property_id": "MAC", "property_name": "设备MAC", "unit": ""},
    "DBM": {"property_id": "DBM", "property_name": "网络信号强度", "unit": "dBm"},
    "IP": {"property_id": "IP", "property_name": "局域网IP", "unit": ""},
    "SetCMD": {"property_id": "SetCMD", "property_name": "操作设置指令", "unit": ""},
    "ArmStatus": {"property_id": "ArmStatus", "property_name": "布撤防状态", "unit": ""},
    "SensorArm": {"property_id": "SensorArm", "property_name": "传感器布撤防", "unit": ""},
    "DoorState": {"property_id": "DoorState", "property_name": "门状态", "unit": ""},
    "LightState": {"property_id": "LightState", "property_name": "灯光状态", "unit": ""},
    "CurtainState": {"property_id": "CurtainState", "property_name": "窗帘状态", "unit": ""},
    "LockState": {"property_id": "LockState", "property_name": "门锁状态", "unit": ""},
    "Energy": {"property_id": "Energy", "property_name": "电量", "unit": "kWh"},
    "Power": {"property_id": "Power", "property_name": "功率", "unit": "W"},
    "Voltage": {"property_id": "Voltage", "property_name": "电压", "unit": "V"},
    "Current": {"property_id": "Current", "property_name": "电流", "unit": "A"},
    "Frequency": {"property_id": "Frequency", "property_name": "频率", "unit": "Hz"},
    "PowerFactor": {"property_id": "PowerFactor", "property_name": "功率因数", "unit": ""},
    "TestAlarm": {"property_id": "TestAlarm", "property_name": "测试告警", "unit": ""},
    "LowBattery": {"property_id": "LowBattery", "property_name": "低电量", "unit": ""},
    "Fault": {"property_id": "Fault", "property_name": "故障", "unit": ""},
    "Count": {"property_id": "Count", "property_name": "计数", "unit": ""},
    "Duration": {"property_id": "Duration", "property_name": "持续时间", "unit": "秒"},
}


class SensorLogRepo:
    def __init__(self):
        self._cache: dict[str, dict] = {}
        self._cache_timestamps: dict[str, datetime] = {}
    
    def _is_cache_valid(self, key: str) -> bool:
        timestamp = self._cache_timestamps.get(key)
        if not timestamp:
            return False
        return (datetime.now() - timestamp) < timedelta(minutes=_CACHE_EXPIRY_MINUTES)
    
    def _update_cache(self, key: str, data: dict) -> None:
        self._cache[key] = data
        self._cache_timestamps[key] = datetime.now()
    
    def _clear_cache(self) -> None:
        self._cache.clear()
        self._cache_timestamps.clear()

    def _extract_dynamic_properties(self, data: SensorData) -> list[tuple]:
        properties = []
        for attr_name, mapping in PROPERTY_MAPPING.items():
            value = getattr(data, attr_name, None)
            if value is not None:
                value_str = str(value)
                value_type = type(value).__name__
                unit = mapping.get("unit", "")
                properties.append((
                    mapping["property_id"],
                    mapping["property_name"],
                    value_str,
                    value_type,
                    unit,
                ))
        return properties
    
    def insert(self, data: SensorData) -> None:
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sensor_logs (
                        did, product_id, sensor_type, value, unit, status, room_name, home_id, timestamp,
                        battery, rssi, signal_level, switch_state, contact_state, motion_state,
                        gas_state, smoke_state, water_state, alarm_state, tamper_state,
                        temperature, humidity, co2, pm25, pm10, hcho, sensor_life_status, raw_properties
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.did,
                    data.product_id,
                    data.sensor_type.value,
                    data.value,
                    data.unit,
                    data.status.value,
                    data.room_name,
                    data.home_id,
                    data.timestamp.isoformat(),
                    data.battery,
                    data.rssi,
                    data.signalLevel,
                    data.switchState,
                    data.contactState,
                    data.motionState,
                    data.gasState,
                    data.smokeState,
                    data.waterState,
                    data.alarmState,
                    data.tamperState,
                    data.temperature,
                    data.humidity,
                    data.co2,
                    data.pm25,
                    data.pm10,
                    data.hcho,
                    data.sensorLifeStatus,
                    json.dumps(
                        {k: v.isoformat() if isinstance(v, datetime) else v 
                         for k, v in data.__dict__.items() if v is not None}, 
                        ensure_ascii=False
                    ),
                ))
                
                log_id = cursor.lastrowid
                
                dynamic_properties = self._extract_dynamic_properties(data)
                if dynamic_properties:
                    cursor.executemany("""
                        INSERT INTO sensor_log_properties (
                            log_id, property_id, property_name, value, value_type, unit
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, [(log_id, prop_id, prop_name, value, value_type, unit) 
                          for prop_id, prop_name, value, value_type, unit in dynamic_properties])
            
            cache_key = f"latest_{data.did}"
            self._update_cache(cache_key, {
                "did": data.did,
                "sensor_type": data.sensor_type.value,
                "value": data.value,
                "unit": data.unit,
                "status": data.status.value,
                "room_name": data.room_name,
                "home_id": data.home_id,
                "timestamp": data.timestamp.isoformat(),
                "battery": data.battery,
                "rssi": data.rssi,
                "signal_level": data.signalLevel,
                "switch_state": data.switchState,
                "contact_state": data.contactState,
                "motion_state": data.motionState,
                "gas_state": data.gasState,
                "smoke_state": data.smokeState,
                "water_state": data.waterState,
                "alarm_state": data.alarmState,
                "tamper_state": data.tamperState,
                "temperature": data.temperature,
                "humidity": data.humidity,
            })
            
            logger.debug("Sensor log inserted for did=%s, value=%s", data.did, data.value)
        except Exception as e:
            logger.error("Failed to insert sensor log for did=%s: %s", data.did, e)
            raise
    
    def batch_insert(self, data_list: list[SensorData]) -> int:
        if not data_list:
            return 0
        
        try:
            params_list = [
                (
                    data.did,
                    data.sensor_type.value,
                    data.value,
                    data.unit,
                    data.status.value,
                    data.room_name,
                    data.home_id,
                    data.timestamp.isoformat(),
                )
                for data in data_list
            ]
            
            count = execute_many("""
                INSERT INTO sensor_logs (
                    did, sensor_type, value, unit, status, room_name, home_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, params_list)
            
            for data in data_list:
                cache_key = f"latest_{data.did}"
                self._update_cache(cache_key, {
                    "did": data.did,
                    "sensor_type": data.sensor_type.value,
                    "value": data.value,
                    "unit": data.unit,
                    "status": data.status.value,
                    "room_name": data.room_name,
                    "home_id": data.home_id,
                    "timestamp": data.timestamp.isoformat(),
                })
            
            logger.info("Batch inserted %d sensor logs", count)
            return count
        except Exception as e:
            logger.error("Failed to batch insert sensor logs: %s", e)
            raise
    
    def query(
        self,
        did: str | None = None,
        sensor_type: str | None = None,
        home_id: str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        try:
            query = "SELECT * FROM sensor_logs WHERE 1=1"
            params: list = []
            
            if did:
                query += " AND did = ?"
                params.append(did)
            
            if sensor_type:
                query += " AND sensor_type = ?"
                params.append(sensor_type)
            
            if home_id:
                query += " AND home_id = ?"
                params.append(home_id)
            
            if after:
                query += " AND timestamp >= ?"
                params.append(after)
            
            if before:
                query += " AND timestamp <= ?"
                params.append(before)
            
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.append(limit)
            params.append(offset)
            
            results = execute_query(query, tuple(params))
            
            log_ids = [str(r["id"]) for r in results]
            if log_ids:
                properties_query = """
                    SELECT log_id, property_id, property_name, value, value_type, unit
                    FROM sensor_log_properties
                    WHERE log_id IN ({})
                """.format(",".join("?" * len(log_ids)))
                properties = execute_query(properties_query, tuple(log_ids))
                
                prop_map = {}
                for p in properties:
                    log_id = str(p["log_id"])
                    if log_id not in prop_map:
                        prop_map[log_id] = []
                    
                    db_unit = p.get("unit", "")
                    if not db_unit:
                        for attr_name, mapping in PROPERTY_MAPPING.items():
                            if mapping["property_id"].lower() == p["property_id"].lower():
                                p["unit"] = mapping.get("unit", "")
                                break
                    prop_map[log_id].append(p)
                
                for r in results:
                    log_id = str(r["id"])
                    r["properties"] = prop_map.get(log_id, [])
            
            for r in results:
                sensor_type = r.get("sensor_type", "")
                unit = r.get("unit", "")
                
                attribute_map = {
                    "temperature": "温度",
                    "humidity": "湿度",
                    "co": "一氧化碳",
                    "water": "水浸状态",
                    "smoke": "烟雾状态",
                    "contact": "门窗状态",
                    "motion": "移动状态",
                    "plug": "开关状态",
                    "siren": "警笛状态",
                    "button": "按钮状态",
                    "gateway": "网关状态",
                    "remote": "遥控器状态",
                }
                
                r["property_name"] = attribute_map.get(sensor_type, sensor_type)
                r["attribute"] = attribute_map.get(sensor_type, "value")
                
                if sensor_type == "contact":
                    value = r.get("value", 0)
                    try:
                        val_int = int(float(value))
                        if val_int in [0, 2]:
                            r["value_label"] = "门窗关闭"
                        elif val_int in [1, 3]:
                            r["value_label"] = "门窗打开"
                        else:
                            r["value_label"] = str(value)
                    except (ValueError, TypeError):
                        r["value_label"] = str(value)
            
            logger.debug("Query returned %d results for did=%s, limit=%d", len(results), did, limit)
            return results
        except Exception as e:
            logger.error("Failed to query sensor logs: %s", e)
            raise
    
    def count(
        self,
        did: str | None = None,
        sensor_type: str | None = None,
        home_id: str | None = None,
        after: str | None = None,
        before: str | None = None,
    ) -> int:
        try:
            query = "SELECT COUNT(*) as count FROM sensor_logs WHERE 1=1"
            params: list = []
            
            if did:
                query += " AND did = ?"
                params.append(did)
            
            if sensor_type:
                query += " AND sensor_type = ?"
                params.append(sensor_type)
            
            if home_id:
                query += " AND home_id = ?"
                params.append(home_id)
            
            if after:
                query += " AND timestamp >= ?"
                params.append(after)
            
            if before:
                query += " AND timestamp <= ?"
                params.append(before)
            
            results = execute_query(query, tuple(params))
            return results[0]["count"] if results else 0
        except Exception as e:
            logger.error("Failed to count sensor logs: %s", e)
            raise
    
    def get_latest(self, did: str) -> dict | None:
        cache_key = f"latest_{did}"
        if self._is_cache_valid(cache_key):
            return self._cache.get(cache_key)
        
        try:
            results = execute_query(
                "SELECT * FROM sensor_logs WHERE did = ? ORDER BY timestamp DESC LIMIT 1",
                (did,),
            )
            
            if results:
                latest = results[0]
                
                log_id = str(latest["id"])
                properties = execute_query(
                    "SELECT property_id, property_name, value, value_type FROM sensor_log_properties WHERE log_id = ?",
                    (log_id,),
                )
                latest["properties"] = properties
                
                self._update_cache(cache_key, latest)
                return latest
            
            return None
        except Exception as e:
            logger.error("Failed to get latest sensor log for did=%s: %s", did, e)
            return None
    
    def get_latest_by_home(self, home_id: str) -> list[dict]:
        try:
            results = execute_query(
                """
                SELECT s.* FROM sensor_logs s
                INNER JOIN (
                    SELECT did, MAX(timestamp) as max_ts 
                    FROM sensor_logs 
                    WHERE home_id = ? 
                    GROUP BY did
                ) latest ON s.did = latest.did AND s.timestamp = latest.max_ts
                ORDER BY s.timestamp DESC
                """,
                (home_id,),
            )
            
            log_ids = [str(r["id"]) for r in results]
            if log_ids:
                properties_query = """
                    SELECT log_id, property_id, property_name, value, value_type, unit
                    FROM sensor_log_properties
                    WHERE log_id IN ({})
                """.format(",".join("?" * len(log_ids)))
                properties = execute_query(properties_query, tuple(log_ids))
                
                prop_map = {}
                for p in properties:
                    log_id = str(p["log_id"])
                    if log_id not in prop_map:
                        prop_map[log_id] = []
                    
                    db_unit = p.get("unit", "")
                    if not db_unit:
                        for attr_name, mapping in PROPERTY_MAPPING.items():
                            if mapping["property_id"].lower() == p["property_id"].lower():
                                p["unit"] = mapping.get("unit", "")
                                break
                    prop_map[log_id].append(p)
                
                for r in results:
                    log_id = str(r["id"])
                    r["properties"] = prop_map.get(log_id, [])
            
            logger.debug("Got %d latest sensor logs for home_id=%s", len(results), home_id)
            return results
        except Exception as e:
            logger.error("Failed to get latest sensor logs by home: %s", e)
            raise
    
    def get_all(self) -> list[dict]:
        """获取所有设备的最新传感器日志（每个设备一条）"""
        try:
            results = execute_query(
                """
                SELECT s.* FROM sensor_logs s
                INNER JOIN (
                    SELECT did, MAX(timestamp) as max_ts 
                    FROM sensor_logs 
                    GROUP BY did
                ) latest ON s.did = latest.did AND s.timestamp = latest.max_ts
                ORDER BY s.timestamp DESC
                """
            )
            
            log_ids = [str(r["id"]) for r in results]
            if log_ids:
                properties_query = """
                    SELECT log_id, property_id, property_name, value, value_type, unit
                    FROM sensor_log_properties
                    WHERE log_id IN ({})
                """.format(",".join("?" * len(log_ids)))
                properties = execute_query(properties_query, tuple(log_ids))
                
                prop_map = {}
                for p in properties:
                    log_id = str(p["log_id"])
                    if log_id not in prop_map:
                        prop_map[log_id] = []
                    
                    db_unit = p.get("unit", "")
                    if not db_unit:
                        for attr_name, mapping in PROPERTY_MAPPING.items():
                            if mapping["property_id"].lower() == p["property_id"].lower():
                                p["unit"] = mapping.get("unit", "")
                                break
                    prop_map[log_id].append(p)
                
                for r in results:
                    log_id = str(r["id"])
                    r["properties"] = prop_map.get(log_id, [])
            
            return results
        except Exception as e:
            logger.error("Failed to get all sensor logs: %s", e)
            raise

    def delete_old_logs(self, days: int = 30) -> int:
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            count = execute_update(
                "DELETE FROM sensor_logs WHERE timestamp < ?",
                (cutoff_date,),
            )
            self._clear_cache()
            logger.info("Deleted %d sensor logs older than %d days", count, days)
            return count
        except Exception as e:
            logger.error("Failed to delete old sensor logs: %s", e)
            raise

    def check_exists(self, did: str, timestamp: str) -> bool:
        try:
            results = execute_query(
                "SELECT id FROM sensor_logs WHERE did = ? AND timestamp = ? LIMIT 1",
                (did, timestamp),
            )
            return len(results) > 0
        except Exception as e:
            logger.error("Failed to check sensor log existence: %s", e)
            return False