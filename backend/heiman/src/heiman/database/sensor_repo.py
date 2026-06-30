import logging
from datetime import datetime, timedelta
from typing import Optional

from heiman.database.connector import transaction, execute_query, execute_update, execute_many
from heiman.schema.sensor import SensorData

logger = logging.getLogger(__name__)

_CACHE_EXPIRY_MINUTES = 5


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
    
    def insert(self, data: SensorData) -> None:
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sensor_logs (
                        did, sensor_type, value, unit, status, room_name, home_id, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.did,
                    data.sensor_type.value,
                    data.value,
                    data.unit,
                    data.status.value,
                    data.room_name,
                    data.home_id,
                    data.timestamp.isoformat(),
                ))
            
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
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            results = execute_query(query, tuple(params))
            logger.debug("Query returned %d results for did=%s, limit=%d", len(results), did, limit)
            return results
        except Exception as e:
            logger.error("Failed to query sensor logs: %s", e)
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
            logger.debug("Got %d latest sensor logs for home_id=%s", len(results), home_id)
            return results
        except Exception as e:
            logger.error("Failed to get latest sensor logs by home: %s", e)
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