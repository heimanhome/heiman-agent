import pytest
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from heiman.database.connector import SQLiteConnector


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def connector(temp_db_path):
    with patch("heiman.database.connector.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.logging.log_dir = temp_db_path.parent
        conn = SQLiteConnector()
        conn.db_path = temp_db_path
        conn.initialize_database()
        yield conn


class TestDatabaseInitialization:
    def test_database_created(self, connector, temp_db_path):
        assert temp_db_path.exists()

    def test_tables_created(self, connector):
        with connector.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

        required_tables = {
            "sensor_logs", "events", "rules", "kv",
            "device_lru", "system_logs", "models",
        }
        assert required_tables.issubset(tables)

    def test_indexes_created(self, connector):
        with connector.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row[0] for row in cursor.fetchall()}

        assert len(indexes) > 0


class TestCleanupOldLogs:
    def test_cleanup_removes_old_sensor_logs(self, connector):
        from datetime import datetime, timedelta
        old_time = (datetime.now() - timedelta(days=90)).isoformat()
        new_time = (datetime.now() - timedelta(days=1)).isoformat()

        with connector.get_connection() as conn:
            conn.execute(
                "INSERT INTO sensor_logs (did, sensor_type, value, status, timestamp) VALUES (?, ?, ?, ?, ?)",
                ("dev1", "temperature", 25.0, "normal", old_time),
            )
            conn.execute(
                "INSERT INTO sensor_logs (did, sensor_type, value, status, timestamp) VALUES (?, ?, ?, ?, ?)",
                ("dev2", "temperature", 26.0, "normal", new_time),
            )
            conn.commit()

        deleted = connector.cleanup_old_logs(max_days=30)
        assert deleted > 0

        with connector.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sensor_logs")
            count = cursor.fetchone()[0]
        assert count == 1

    def test_cleanup_removes_old_events(self, connector):
        from datetime import datetime, timedelta
        old_time = (datetime.now() - timedelta(days=90)).isoformat()

        with connector.get_connection() as conn:
            conn.execute(
                "INSERT INTO events (event_id, event_type, level, did, timestamp) VALUES (?, ?, ?, ?, ?)",
                ("evt-old", "alert", "high", "dev1", old_time),
            )
            conn.commit()

        deleted = connector.cleanup_old_logs(max_days=30)
        assert deleted > 0

    def test_cleanup_within_ttl_preserved(self, connector):
        from datetime import datetime, timedelta
        new_time = (datetime.now() - timedelta(days=1)).isoformat()

        with connector.get_connection() as conn:
            conn.execute(
                "INSERT INTO sensor_logs (did, sensor_type, value, status, timestamp) VALUES (?, ?, ?, ?, ?)",
                ("dev1", "temperature", 25.0, "normal", new_time),
            )
            conn.commit()

        deleted = connector.cleanup_old_logs(max_days=30)

        with connector.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sensor_logs")
            count = cursor.fetchone()[0]
        assert count == 1


class TestIncrementalVacuum:
    def test_incremental_vacuum_runs(self, connector):
        try:
            connector.incremental_vacuum(pages=100)
        except Exception as e:
            pytest.fail(f"incremental_vacuum raised {e}")


class TestVacuum:
    def test_vacuum_runs(self, connector):
        try:
            connector.vacuum()
        except Exception as e:
            pytest.fail(f"vacuum raised {e}")


class TestDatabaseInfo:
    def test_get_database_info(self, connector, temp_db_path):
        info = connector.get_database_info()
        assert isinstance(info, dict)
        assert "path" in info
        assert "tables" in info
        assert "version" in info
        assert "page_count" in info
        assert "page_size" in info
        assert info["exists"] is True
        assert len(info["tables"]) > 0


class TestQueryExecution:
    def test_execute_query(self, connector):
        rows = connector.execute_query("SELECT 1 as test")
        assert len(rows) == 1
        assert rows[0]["test"] == 1

    def test_execute_update(self, connector):
        result = connector.execute_update(
            "INSERT INTO kv (key, value, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("test_key", "test_value", int(time.time()), int(time.time())),
        )
        assert result == 1

    def test_execute_many(self, connector):
        params = [
            (f"key_{i}", f"value_{i}", int(time.time()), int(time.time()))
            for i in range(5)
        ]
        result = connector.execute_many(
            "INSERT INTO kv (key, value, created_at, updated_at) VALUES (?, ?, ?, ?)",
            params,
        )
        assert result == 5
