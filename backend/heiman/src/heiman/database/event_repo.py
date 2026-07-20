import json
import logging
from datetime import datetime

from heiman.database.connector import get_db_connector
from heiman.schema.sensor import SensorEvent

logger = logging.getLogger(__name__)


def _serialize_raw_data(raw_data: dict) -> str:
    def default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)
    return json.dumps(raw_data, default=default)


def _enrich_event_row(row_dict: dict) -> dict:
    """Enrich event row with derived fields from raw_data."""
    if row_dict.get("raw_data") and isinstance(row_dict["raw_data"], str):
        try:
            row_dict["raw_data"] = json.loads(row_dict["raw_data"])
        except json.JSONDecodeError:
            pass
    
    raw_data = row_dict.get("raw_data", {}) if isinstance(row_dict.get("raw_data"), dict) else {}
    
    if "message" not in row_dict and "description" in row_dict:
        row_dict["message"] = row_dict["description"]
    
    if not row_dict.get("home_id"):
        row_dict["home_id"] = raw_data.get("home_id", raw_data.get("homeId", ""))
    
    if not row_dict.get("room_name"):
        row_dict["room_name"] = raw_data.get("room_name", raw_data.get("roomName", ""))
    
    if not row_dict.get("device_name") or row_dict["device_name"] == row_dict.get("did"):
        row_dict["device_name"] = raw_data.get(
            "name",
            raw_data.get("device_name", raw_data.get("deviceName", row_dict.get("device_name", ""))),
        )
    
    if "sensor_type" not in row_dict or row_dict.get("sensor_type") == "undefined":
        sensor_type = None
        
        if isinstance(raw_data, dict):
            sensor_type = raw_data.get("sensor_type")
            if not sensor_type:
                sensor_type = raw_data.get("sensorType")
        
        if not sensor_type:
            event_type = str(row_dict.get("event_type", ""))
            if "smoke" in event_type:
                sensor_type = "smoke"
            elif "temperature" in event_type or "temp" in event_type:
                sensor_type = "temperature"
            elif "humidity" in event_type or "humi" in event_type:
                sensor_type = "humidity"
            elif "co" in event_type or "gas" in event_type or "carbon" in event_type:
                sensor_type = "co"
            elif "water" in event_type or "leak" in event_type:
                sensor_type = "water"
            elif "contact" in event_type or "door" in event_type or "window" in event_type:
                sensor_type = "contact"
            elif "motion" in event_type or "pir" in event_type or "move" in event_type:
                sensor_type = "motion"
            elif "plug" in event_type or "switch" in event_type or "outlet" in event_type:
                sensor_type = "plug"
            elif "siren" in event_type or "alarm" in event_type:
                sensor_type = "siren"
            elif "button" in event_type or "sos" in event_type:
                sensor_type = "button"
            elif "gateway" in event_type or "hub" in event_type:
                sensor_type = "gateway"
            elif "remote" in event_type:
                sensor_type = "remote"
            elif "offline" in event_type or "online" in event_type:
                device_name = str(row_dict.get("device_name", "")).lower()
                if "smoke" in device_name:
                    sensor_type = "smoke"
                elif "temperature" in device_name or "thermo" in device_name or "temp" in device_name:
                    sensor_type = "temperature"
                elif "humidity" in device_name or "humi" in device_name:
                    sensor_type = "humidity"
                elif "co" in device_name or "carbon" in device_name or "gas" in device_name:
                    sensor_type = "co"
                elif "water" in device_name or "leak" in device_name:
                    sensor_type = "water"
                elif "contact" in device_name or "door" in device_name or "window" in device_name:
                    sensor_type = "contact"
                elif "motion" in device_name or "pir" in device_name:
                    sensor_type = "motion"
                else:
                    sensor_type = "unknown"
            else:
                sensor_type = "unknown"
        
        row_dict["sensor_type"] = sensor_type
    
    if row_dict.get("sensor_type") == "contact":
        payload = raw_data.get("payload", {})
        if isinstance(payload, dict):
            data = payload.get("data", {})
            if isinstance(data, dict):
                switch_state = data.get("SwitchState", data.get("contactState", data.get("ContactState")))
                if switch_state is not None:
                    try:
                        val_int = int(float(switch_state))
                        if val_int in [0, 2]:
                            row_dict["contact_state_desc"] = "门窗关闭"
                        elif val_int in [1, 3]:
                            row_dict["contact_state_desc"] = "门窗打开"
                        else:
                            row_dict["contact_state_desc"] = str(switch_state)
                    except (ValueError, TypeError):
                        row_dict["contact_state_desc"] = str(switch_state)
    
    if "acknowledged" in row_dict:
        row_dict["acknowledged"] = bool(row_dict["acknowledged"])
        row_dict["acknowledged_desc"] = "已确认" if row_dict["acknowledged"] else "待确认"
    
    return row_dict


class EventRepo:
    def __init__(self):
        self.db_connector = get_db_connector()

    def insert(self, event: SensorEvent) -> None:
        try:
            self.db_connector.execute_update("""
                INSERT OR IGNORE INTO events (
                    event_id, event_type, level, did, device_name, room_name,
                    home_id, product_id, child_device_id, description, raw_data, 
                    timestamp, acknowledged
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.event_type.value,
                event.level.value,
                event.did,
                event.device_name,
                event.room_name,
                event.home_id,
                event.product_id,
                event.child_device_id,
                event.description,
                _serialize_raw_data(event.raw_data),
                event.timestamp.isoformat(),
                1 if event.acknowledged else 0,
            ))
            logger.info("[DB] Event inserted: event_id=%s, type=%s, level=%s, product_id=%s, child_device_id=%s", 
                       event.event_id, event.event_type.value, event.level.value, event.product_id, event.child_device_id)
        except Exception as e:
            logger.error("[DB] Failed to insert event: event_id=%s, error=%s", event.event_id, e)
            raise

    def batch_insert(self, events: list[SensorEvent]) -> int:
        if not events:
            return 0
        
        try:
            params_list = [
                (
                    event.event_id,
                    event.event_type.value,
                    event.level.value,
                    event.did,
                    event.device_name,
                    event.room_name,
                    event.home_id,
                    event.product_id,
                    event.child_device_id,
                    event.description,
                    _serialize_raw_data(event.raw_data),
                    event.timestamp.isoformat(),
                    1 if event.acknowledged else 0,
                )
                for event in events
            ]
            
            count = self.db_connector.execute_many("""
                INSERT OR IGNORE INTO events (
                    event_id, event_type, level, did, device_name, room_name,
                    home_id, product_id, child_device_id, description, raw_data, 
                    timestamp, acknowledged
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, params_list)
            
            logger.info("[DB] Batch inserted %d events", count)
            return count
        except Exception as e:
            logger.error("[DB] Failed to batch insert events: error=%s", e)
            raise

    def query(
        self,
        event_type: str | None = None,
        level: str | None = None,
        did: str | None = None,
        home_id: str | None = None,
        acknowledged: bool | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        try:
            query = "SELECT * FROM events WHERE 1=1"
            params: list = []
            
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)
            
            if level:
                query += " AND level = ?"
                params.append(level)
            
            if did:
                query += " AND did = ?"
                params.append(did)
            
            if home_id:
                query += " AND home_id = ?"
                params.append(home_id)
            
            if acknowledged is not None:
                query += " AND acknowledged = ?"
                params.append(1 if acknowledged else 0)
            
            if after:
                query += " AND timestamp >= ?"
                params.append(after)
            
            if before:
                query += " AND timestamp <= ?"
                params.append(before)
            
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.append(limit)
            params.append(offset)
            
            results = self.db_connector.execute_query(query, tuple(params))
            
            result = []
            for row in results:
                row_dict = dict(row)
                row_dict = _enrich_event_row(row_dict)
                result.append(row_dict)
            
            logger.debug("[DB] Query returned %d events", len(result))
            return result
        except Exception as e:
            logger.error("[DB] Failed to query events: error=%s", e)
            raise

    def count(
        self,
        event_type: str | None = None,
        level: str | None = None,
        did: str | None = None,
        home_id: str | None = None,
        acknowledged: bool | None = None,
        after: str | None = None,
        before: str | None = None,
    ) -> int:
        try:
            query = "SELECT COUNT(*) as count FROM events WHERE 1=1"
            params: list = []
            
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)
            
            if level:
                query += " AND level = ?"
                params.append(level)
            
            if did:
                query += " AND did = ?"
                params.append(did)
            
            if home_id:
                query += " AND home_id = ?"
                params.append(home_id)
            
            if acknowledged is not None:
                query += " AND acknowledged = ?"
                params.append(1 if acknowledged else 0)
            
            if after:
                query += " AND timestamp >= ?"
                params.append(after)
            
            if before:
                query += " AND timestamp <= ?"
                params.append(before)
            
            results = self.db_connector.execute_query(query, tuple(params))
            return results[0]["count"] if results else 0
        except Exception as e:
            logger.error("[DB] Failed to count events: error=%s", e)
            raise

    def get_by_id(self, event_id: str) -> dict | None:
        try:
            results = self.db_connector.execute_query("""
                SELECT * FROM events WHERE event_id = ?
            """, (event_id,))
            
            if results:
                row_dict = dict(results[0])
                row_dict = _enrich_event_row(row_dict)
                return row_dict
            return None
        except Exception as e:
            logger.error("[DB] Failed to get event: event_id=%s, error=%s", event_id, e)
            raise

    def acknowledge(self, event_id: str) -> bool:
        try:
            count = self.db_connector.execute_update("""
                UPDATE events SET acknowledged = 1 WHERE event_id = ?
            """, (event_id,))

            success = count > 0
            if success:
                logger.info("[DB] Event acknowledged: event_id=%s", event_id)
            return success
        except Exception as e:
            logger.error("[DB] Failed to acknowledge event: event_id=%s, error=%s", event_id, e)
            raise

    def acknowledge_many(self, event_ids: list[str]) -> int:
        if not event_ids:
            return 0
        try:
            placeholders = ",".join("?" * len(event_ids))
            count = self.db_connector.execute_update(
                f"UPDATE events SET acknowledged = 1 WHERE event_id IN ({placeholders})",
                tuple(event_ids),
            )
            logger.info("[DB] Batch acknowledged %d events", count)
            return count
        except Exception as e:
            logger.error("[DB] Failed to batch acknowledge events: error=%s", e)
            raise

    def delete_old_events(self, days: int = 30) -> int:
        try:
            from datetime import datetime, timedelta
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            count = self.db_connector.execute_update(
                "DELETE FROM events WHERE timestamp < ?",
                (cutoff_date,),
            )
            logger.info("[DB] Deleted %d events older than %d days", count, days)
            return count
        except Exception as e:
            logger.error("[DB] Failed to delete old events: error=%s", e)
            raise


_event_repo_instance = None


def get_event_repo() -> EventRepo:
    global _event_repo_instance
    if _event_repo_instance is None:
        _event_repo_instance = EventRepo()
    return _event_repo_instance