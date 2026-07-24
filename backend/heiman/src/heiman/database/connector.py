import sqlite3
import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional, List, Dict, Tuple

from heiman.config import get_settings

logger = logging.getLogger(__name__)

_DB_SCHEMA_VERSION = 18


class SQLiteConnector:
    def __init__(self):
        settings = get_settings()
        self.db_path = settings.logging.log_dir / "heiman.db"
        self.timeout = 30
        self.check_same_thread = False
        self.isolation_level = None
        self._connection: Optional[sqlite3.Connection] = None

    def initialize_database(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            if self.db_path.exists():
                logger.info("[DB] Database file already exists: %s", self.db_path)
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    existing_tables = {row[0] for row in cursor.fetchall()}
                    logger.info(
                        "[DB] Found %d tables in existing database: %s",
                        len(existing_tables),
                        existing_tables,
                    )

                    if not existing_tables:
                        logger.info("[DB] Empty pre-created db file, running fresh init")
                        self._create_tables(conn)
                        logger.info("[DB] Database initialized successfully: %s", self.db_path)
                        return

                    tables_created = []

                    if "sensor_logs" not in existing_tables:
                        logger.info("[DB] sensor_logs table not found, creating...")
                        self._create_sensor_logs_table(conn)
                        tables_created.append("sensor_logs")

                    if "events" not in existing_tables:
                        logger.info("[DB] events table not found, creating...")
                        self._create_events_table(conn)
                        tables_created.append("events")

                    if "rules" not in existing_tables:
                        logger.info("[DB] rules table not found, creating...")
                        self._create_rules_table(conn)
                        tables_created.append("rules")

                    if "kv" not in existing_tables:
                        logger.info("[DB] kv table not found, creating...")
                        self._create_kv_table(conn)
                        tables_created.append("kv")

                    if "device_lru" not in existing_tables:
                        logger.info("[DB] device_lru table not found, creating...")
                        self._create_device_lru_table(conn)
                        tables_created.append("device_lru")

                    current_version = cursor.execute("PRAGMA user_version").fetchone()[0]
                    logger.info("[DB] Current schema version: %d, target: %d", current_version, _DB_SCHEMA_VERSION)

                    if current_version < _DB_SCHEMA_VERSION:
                        logger.info("[DB] Upgrading database schema from version %d to %d", current_version, _DB_SCHEMA_VERSION)
                        if "system_logs" not in existing_tables:
                            self._create_system_logs_table(conn)
                            tables_created.append("system_logs")
                        if "models" not in existing_tables:
                            self._create_models_table(conn)
                            tables_created.append("models")
                        if "person" not in existing_tables:
                            self._create_person_table(conn)
                            tables_created.append("person")
                        if "task" not in existing_tables:
                            self._create_task_tables(conn)
                            tables_created.extend(["task", "task_link", "task_record_progress", "task_record_duration", "task_record_event", "task_duration_session", "task_event_entry"])

                        if current_version < 4:
                            logger.info("[DB] Migrating to v4: adding recurring_pattern and archived_at columns")
                            cursor = conn.cursor()
                            cursor.execute("ALTER TABLE task_record_progress ADD COLUMN recurring_pattern TEXT")
                            cursor.execute("ALTER TABLE task_record_progress ADD COLUMN archived_at TEXT")
                            cursor.execute("ALTER TABLE task_record_duration ADD COLUMN recurring_pattern TEXT")
                            cursor.execute("ALTER TABLE task_record_duration ADD COLUMN archived_at TEXT")
                            cursor.execute("ALTER TABLE task_record_event ADD COLUMN recurring_pattern TEXT")
                            cursor.execute("ALTER TABLE task_record_event ADD COLUMN archived_at TEXT")
                            cursor.execute("DROP INDEX IF EXISTS idx_task_progress_task")
                            cursor.execute("DROP INDEX IF EXISTS idx_task_duration_task")
                            cursor.execute("DROP INDEX IF EXISTS idx_task_event_task")

                        if current_version < 5:
                            logger.info("[DB] Migrating to v5: adding home_id column to sensor_logs")
                            cursor = conn.cursor()
                            cursor.execute("ALTER TABLE sensor_logs ADD COLUMN home_id TEXT")
                            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensor_logs_home ON sensor_logs(home_id)")

                        if current_version < 6:
                            logger.info("[DB] Migrating to v6: adding product tables")
                            self._create_product_tables(conn)

                        if current_version < 7:
                            logger.info("[DB] Migrating to v7: adding product_id and child_device_id columns to events")
                            cursor = conn.cursor()
                            cursor.execute("ALTER TABLE events ADD COLUMN product_id TEXT")
                            cursor.execute("ALTER TABLE events ADD COLUMN child_device_id TEXT")
                            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_product_id ON events(product_id)")
                            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_child_device_id ON events(child_device_id)")

                        if current_version < 8:
                            logger.info("[DB] Migrating to v8: adding home_id column to events")
                            cursor = conn.cursor()
                            cursor.execute("ALTER TABLE events ADD COLUMN home_id TEXT")
                            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_home ON events(home_id)")

                        if current_version < 9:
                            logger.info("[DB] Migrating to v9: adding home_id column to rules")
                            cursor = conn.cursor()
                            # Check if rules table exists and if home_id column is missing
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rules'")
                            if cursor.fetchone():
                                cursor.execute("PRAGMA table_info(rules)")
                                columns = [col[1] for col in cursor.fetchall()]
                                if 'home_id' not in columns:
                                    cursor.execute("ALTER TABLE rules ADD COLUMN home_id TEXT")
                                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_home ON rules(home_id)")

                        if current_version < 10:
                            logger.info("[DB] Migrating to v10: adding missing columns to person table")
                            cursor = conn.cursor()
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='person'")
                            if cursor.fetchone():
                                cursor.execute("PRAGMA table_info(person)")
                                existing_cols = {col[1] for col in cursor.fetchall()}
                                person_new_cols = [
                                    ("user_id", "TEXT"),
                                    ("home_id", "TEXT"),
                                    ("home_name", "TEXT"),
                                    ("user_account", "TEXT"),
                                    ("alias_name", "TEXT"),
                                    ("head_img_url", "TEXT"),
                                    ("is_home_root", "INTEGER DEFAULT 0"),
                                    ("role_type", "INTEGER DEFAULT 2"),
                                    ("status", "INTEGER DEFAULT 1"),
                                    ("remark", "TEXT"),
                                ]
                                for col_name, col_type in person_new_cols:
                                    if col_name not in existing_cols:
                                        cursor.execute(f"ALTER TABLE person ADD COLUMN {col_name} {col_type}")
                                        logger.info("[DB] Added column %s to person table", col_name)
                                cursor.execute("CREATE INDEX IF NOT EXISTS idx_person_user_id ON person(user_id)")
                                cursor.execute("CREATE INDEX IF NOT EXISTS idx_person_home_id ON person(home_id)")

                        if current_version < 11:
                            logger.info("[DB] Migrating to v11: adding extended properties to sensor_logs")
                            cursor = conn.cursor()
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_logs'")
                            if cursor.fetchone():
                                cursor.execute("PRAGMA table_info(sensor_logs)")
                                existing_cols = {col[1] for col in cursor.fetchall()}
                                sensor_logs_new_cols = [
                                    ("battery", "INTEGER"),
                                    ("rssi", "INTEGER"),
                                    ("signal_level", "INTEGER"),
                                    ("switch_state", "INTEGER"),
                                    ("contact_state", "INTEGER"),
                                    ("motion_state", "INTEGER"),
                                    ("gas_state", "INTEGER"),
                                    ("smoke_state", "INTEGER"),
                                    ("water_state", "INTEGER"),
                                    ("alarm_state", "INTEGER"),
                                    ("tamper_state", "INTEGER"),
                                    ("temperature", "REAL"),
                                    ("humidity", "REAL"),
                                    ("co2", "REAL"),
                                    ("pm25", "REAL"),
                                    ("pm10", "REAL"),
                                    ("hcho", "REAL"),
                                    ("sensor_life_status", "INTEGER"),
                                    ("raw_properties", "TEXT"),
                                ]
                                for col_name, col_type in sensor_logs_new_cols:
                                    if col_name not in existing_cols:
                                        cursor.execute(f"ALTER TABLE sensor_logs ADD COLUMN {col_name} {col_type}")
                                        logger.info("[DB] Added column %s to sensor_logs table", col_name)

                        if current_version < 12:
                            logger.info("[DB] Migrating to v12: creating sensor_log_properties table for dynamic attributes")
                            self._create_sensor_log_properties_table(conn)

                        if current_version < 13:
                            logger.info("[DB] Migrating to v13: adding unit column to sensor_log_properties")
                            cursor = conn.cursor()
                            cursor.execute("PRAGMA table_info(sensor_log_properties)")
                            existing_cols = {col[1] for col in cursor.fetchall()}
                            if "unit" not in existing_cols:
                                cursor.execute("ALTER TABLE sensor_log_properties ADD COLUMN unit TEXT")
                                logger.info("[DB] Added column unit to sensor_log_properties table")

                        if current_version < 14:
                            logger.info("[DB] Migrating to v14: creating_analysis_results table")
                            self._create_ai_analysis_results_table(conn)

                        if current_version < 15:
                            logger.info("[DB] Migrating to v15: creating rule_executions table")
                            self._create_rule_executions_table(conn)

                        if current_version < 16:
                            logger.info("[DB] Migrating to v16: creating rule_suggestions table")
                            self._create_rule_suggestions_table(conn)

                        if current_version < 17:
                            logger.info("[DB] Migrating to v17: creating self-learning tables")
                            self._create_self_learning_tables(conn)

                        if current_version < 18:
                            logger.info("[DB] Migrating to v18: creating alert_analyses table")
                            self._create_alert_analyses_table(conn)

                        conn.execute(f"PRAGMA user_version = {_DB_SCHEMA_VERSION}")
                        conn.commit()
                        logger.info("[DB] Schema migration committed, version=%d", _DB_SCHEMA_VERSION)

                    if current_version >= _DB_SCHEMA_VERSION:
                        for table, creator in [
                            ("system_logs", self._create_system_logs_table),
                            ("models", self._create_models_table),
                            ("person", self._create_person_table),
                        ]:
                            if table not in existing_tables:
                                logger.info("[DB] Missing table %s in v%d db, creating...", table, current_version)
                                creator(conn)
                                tables_created.append(table)

                        if "task" not in existing_tables:
                            logger.info("[DB] Missing task tables in v%d db, creating...", current_version)
                            self._create_task_tables(conn)
                            tables_created.extend(["task", "task_link", "task_record_progress", "task_record_duration", "task_record_event", "task_duration_session", "task_event_entry"])

                        if "dev_product" not in existing_tables:
                            logger.info("[DB] Missing product tables in v%d db, creating...", current_version)
                            self._create_product_tables(conn)
                            tables_created.extend(["dev_product", "product_property"])

                    if tables_created:
                        conn.commit()
                        logger.info("[DB] Created missing tables: %s", tables_created)
                    else:
                        conn.commit()
                        logger.info("[DB] All required tables already exist")

                    logger.info("[DB] Database loaded successfully: %s", self.db_path)
            else:
                logger.info("[DB] Database file does not exist, creating new database: %s", self.db_path)
                with self.get_connection() as conn:
                    self._create_tables(conn)
                    logger.info("[DB] Database initialized successfully: %s", self.db_path)

        except Exception as e:
            logger.error("[DB] Database initialization failed: %s", e)
            raise

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
        conn.execute("PRAGMA journal_mode=WAL")
        self._create_sensor_logs_table(conn)
        self._create_sensor_log_properties_table(conn)
        self._create_events_table(conn)
        self._create_rules_table(conn)
        self._create_kv_table(conn)
        self._create_device_lru_table(conn)
        self._create_system_logs_table(conn)
        self._create_models_table(conn)
        self._create_person_table(conn)
        self._create_task_tables(conn)
        self._create_product_tables(conn)
        self._create_ai_analysis_results_table(conn)
        self._create_alert_analyses_table(conn)
        conn.execute(f"PRAGMA user_version = {_DB_SCHEMA_VERSION}")
        conn.commit()
        logger.info("[DB] Database table structure created successfully")

    def _create_sensor_logs_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                did TEXT NOT NULL,
                product_id TEXT,
                sensor_type TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT,
                status TEXT NOT NULL,
                room_name TEXT,
                home_id TEXT,
                timestamp TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                battery INTEGER,
                rssi INTEGER,
                signal_level INTEGER,
                switch_state INTEGER,
                contact_state INTEGER,
                motion_state INTEGER,
                gas_state INTEGER,
                smoke_state INTEGER,
                water_state INTEGER,
                alarm_state INTEGER,
                tamper_state INTEGER,
                temperature REAL,
                humidity REAL,
                co2 REAL,
                pm25 REAL,
                pm10 REAL,
                hcho REAL,
                sensor_life_status INTEGER,
                raw_properties TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensor_logs_did ON sensor_logs(did)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensor_logs_timestamp ON sensor_logs(timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensor_logs_did_ts ON sensor_logs(did, timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensor_logs_home ON sensor_logs(home_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensor_logs_product ON sensor_logs(product_id)")
        logger.info("[DB] sensor_logs table created successfully")

    def _create_sensor_log_properties_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_log_properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_id INTEGER NOT NULL,
                property_id TEXT NOT NULL,
                property_name TEXT,
                value TEXT NOT NULL,
                value_type TEXT,
                unit TEXT,
                FOREIGN KEY (log_id) REFERENCES sensor_logs(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensor_log_prop_log_id ON sensor_log_properties(log_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensor_log_prop_property ON sensor_log_properties(property_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensor_log_prop_log_prop ON sensor_log_properties(log_id, property_id)")
        logger.info("[DB] sensor_log_properties table created successfully")

    def _create_events_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                level TEXT NOT NULL,
                did TEXT NOT NULL,
                device_name TEXT,
                room_name TEXT,
                home_id TEXT,
                product_id TEXT,
                child_device_id TEXT,
                description TEXT,
                raw_data TEXT,
                timestamp TEXT NOT NULL,
                acknowledged INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_event_id ON events(event_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_did ON events(did)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_level ON events(level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_home ON events(home_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_ack ON events(acknowledged)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_product_id ON events(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_child_device_id ON events(child_device_id)")
        logger.info("[DB] events table created successfully")

    def _create_rules_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                enabled INTEGER DEFAULT 1,
                conditions TEXT NOT NULL,
                actions TEXT NOT NULL,
                cooldown_minutes INTEGER DEFAULT 5,
                home_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_rule_id ON rules(rule_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_name ON rules(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_enabled ON rules(enabled)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_home ON rules(home_id)")
        logger.info("[DB] rules table created successfully")

    def _create_kv_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kv (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kv_key ON kv(key)")
        logger.info("[DB] kv table created successfully")

    def _create_device_lru_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_lru (
                did TEXT NOT NULL,
                key TEXT NOT NULL,
                touched_at INTEGER NOT NULL,
                PRIMARY KEY (did, key)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_device_lru_did_touched ON device_lru(did, touched_at DESC)")
        logger.info("[DB] device_lru table created successfully")

    def _create_system_logs_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                level TEXT NOT NULL,
                action TEXT NOT NULL,
                user TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_logs_time ON system_logs(time DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_logs_action ON system_logs(action)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_logs_user ON system_logs(user)")
        logger.info("[DB] system_logs table created successfully")

    def _create_models_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS models (
                id TEXT NOT NULL PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                description TEXT,
                accuracy REAL DEFAULT 0,
                model_path TEXT,
                last_deployed TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_models_type ON models(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_models_status ON models(status)")
        logger.info("[DB] models table created successfully")

    def _create_person_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS person (
                id TEXT NOT NULL PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT,
                user_id TEXT UNIQUE,
                home_id TEXT,
                home_name TEXT,
                user_account TEXT,
                alias_name TEXT,
                head_img_url TEXT,
                is_home_root INTEGER DEFAULT 0,
                role_type INTEGER DEFAULT 2,
                status INTEGER DEFAULT 1,
                remark TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_person_name ON person(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_person_user_id ON person(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_person_home_id ON person(home_id)")
        logger.info("[DB] person table created successfully")

    def _create_product_tables(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dev_product (
                id TEXT NOT NULL PRIMARY KEY,
                name TEXT,
                project_id TEXT,
                photo_url TEXT,
                project_name TEXT,
                describe TEXT,
                classified_id TEXT,
                classified_name TEXT,
                message_protocol TEXT,
                protocol_name TEXT,
                metadata TEXT,
                transport_protocol TEXT,
                network_way TEXT,
                device_type TEXT,
                configuration TEXT,
                state INTEGER DEFAULT 1,
                creator_id TEXT,
                create_time INTEGER,
                org_id TEXT,
                access_id TEXT,
                access_provider TEXT,
                access_name TEXT,
                store_policy TEXT,
                store_policy_configuration TEXT,
                modifier_id TEXT,
                modify_time INTEGER,
                bind_type INTEGER DEFAULT 0,
                network_type INTEGER DEFAULT 1,
                target_id TEXT,
                dueros_product TEXT,
                keep_online_second INTEGER,
                ifttt TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prod_name ON dev_product(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prod_classified ON dev_product(classified_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prod_classified_name ON dev_product(classified_name)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_property (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                property_name TEXT,
                property_type TEXT,
                value_type TEXT,
                expands TEXT,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES dev_product(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prod_prop_product ON product_property(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prod_prop_id ON product_property(property_id)")
        logger.info("[DB] product tables created successfully")

    def _create_task_tables(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task (
                task_id TEXT NOT NULL PRIMARY KEY,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                paused_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON task(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_created ON task(created_at DESC)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_link (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                link_kind TEXT NOT NULL,
                link_ref TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES task(task_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_task_link_ref_unique ON task_link(link_kind, link_ref)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_link_task ON task_link(task_id)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_record_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                target INTEGER NOT NULL,
                current INTEGER NOT NULL DEFAULT 0,
                unit TEXT NOT NULL,
                window TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                recurring_pattern TEXT,
                archived_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES task(task_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_progress_status ON task_record_progress(status)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_record_duration (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                target_minutes INTEGER,
                active_session_start_at TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                recurring_pattern TEXT,
                archived_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES task(task_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_duration_status ON task_record_duration(status)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_duration_session (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                start_at TEXT NOT NULL,
                end_at TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL,
                FOREIGN KEY (task_id) REFERENCES task(task_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_duration_session_task ON task_duration_session(task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_duration_session_start ON task_duration_session(start_at DESC)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_record_event (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                recurring_pattern TEXT,
                archived_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES task(task_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_event_status ON task_record_event(status)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_event_entry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                description TEXT NOT NULL,
                at TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES task(task_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_event_entry_task ON task_event_entry(task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_event_entry_at ON task_event_entry(at DESC)")

        logger.info("[DB] task tables created successfully")

    def _create_ai_analysis_results_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL UNIQUE,
                analysis_type TEXT NOT NULL,
                result_data TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                anomaly_count INTEGER DEFAULT 0,
                comfort_score REAL DEFAULT 0,
                activity_type TEXT,
                home_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_analysis_id ON ai_analysis_results(analysis_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_analysis_timestamp ON ai_analysis_results(timestamp_ms DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_analysis_type ON ai_analysis_results(analysis_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_analysis_home ON ai_analysis_results(home_id)")
        logger.info("[DB] ai_analysis_results table created successfully")

    def _create_alert_analyses_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL UNIQUE,
                event_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                root_cause TEXT NOT NULL DEFAULT '{}',
                impact TEXT NOT NULL DEFAULT '{}',
                remediation TEXT NOT NULL DEFAULT '[]',
                urgency_level TEXT DEFAULT 'medium',
                recommended_actions TEXT DEFAULT '[]',
                raw_response TEXT DEFAULT '',
                model_used TEXT DEFAULT '',
                success INTEGER DEFAULT 1,
                created_at_ms INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_analyses_id ON alert_analyses(analysis_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_analyses_event ON alert_analyses(event_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_analyses_type ON alert_analyses(alert_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_analyses_urgency ON alert_analyses(urgency_level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_analyses_time ON alert_analyses(created_at_ms DESC)")
        logger.info("[DB] alert_analyses table created successfully")

    def _create_rule_executions_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rule_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id TEXT NOT NULL,
                rule_name TEXT NOT NULL,
                action_type TEXT NOT NULL,
                executed_at TEXT NOT NULL,
                success INTEGER DEFAULT 1,
                error_message TEXT,
                home_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rule_executions_rule_id ON rule_executions(rule_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rule_executions_executed ON rule_executions(executed_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rule_executions_home ON rule_executions(home_id)")
        logger.info("[DB] rule_executions table created successfully")

    def _create_rule_suggestions_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rule_suggestions (
                suggestion_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                home_id TEXT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                confidence REAL NOT NULL,
                pattern_type TEXT NOT NULL,
                trigger_device_id TEXT,
                trigger_device_name TEXT,
                action_device_id TEXT,
                action_device_name TEXT,
                rule_data TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                approved_at TEXT,
                rejected_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rule_suggestions_user ON rule_suggestions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rule_suggestions_status ON rule_suggestions(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rule_suggestions_home ON rule_suggestions(home_id)")
        logger.info("[DB] rule_suggestions table created successfully")

    def _create_self_learning_tables(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_feedback (
                feedback_id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                prediction_id TEXT,
                input_features TEXT NOT NULL,
                predicted_output TEXT NOT NULL,
                actual_output TEXT,
                feedback_type TEXT NOT NULL,
                confidence REAL,
                user_id TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_model ON model_feedback(model_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_time ON model_feedback(timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_type ON model_feedback(feedback_type)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_cycles (
                cycle_id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                start_time TEXT NOT NULL,
                end_time TEXT,
                samples_analyzed INTEGER DEFAULT 0,
                improvements_made INTEGER DEFAULT 0,
                performance_before REAL,
                performance_after REAL,
                error_message TEXT,
                metadata TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cycle_model ON learning_cycles(model_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cycle_status ON learning_cycles(status)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                metric_id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL NOT NULL,
                window_start TEXT NOT NULL,
                window_end TEXT NOT NULL,
                sample_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_model ON performance_metrics(model_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_type ON performance_metrics(metric_type)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_rules (
                rule_id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                rule_type TEXT NOT NULL,
                condition TEXT NOT NULL,
                action TEXT NOT NULL,
                confidence_threshold REAL DEFAULT 0.6,
                enabled INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_rules_model ON learning_rules(model_name)")

        logger.info("[DB] Self-learning tables created successfully")

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=self.timeout,
                check_same_thread=self.check_same_thread,
                isolation_level=self.isolation_level,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error("[DB] Database connection error: %s", e)
            raise
        finally:
            if conn:
                conn.close()

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error("[DB] Query execution failed: %s, SQL: %s", e, query)
            raise

    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error("[DB] Update execution failed: %s, SQL: %s", e, query)
            raise

    def execute_many(self, query: str, params_list: list[tuple]) -> int:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error("[DB] Batch execution failed: %s, SQL: %s", e, query)
            raise

    def get_database_info(self) -> dict[str, Any]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]

                cursor.execute("PRAGMA user_version")
                version = cursor.fetchone()[0]

                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]

                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]

                return {
                    "path": str(self.db_path),
                    "size": db_size,
                    "tables": tables,
                    "version": version,
                    "page_count": page_count,
                    "page_size": page_size,
                    "exists": self.db_path.exists(),
                }
        except Exception as e:
            logger.error("[DB] Failed to get database info: %s", e)
            return {}

    def cleanup_old_logs(self, max_days: int = 30) -> int:
        try:
            from datetime import datetime, timedelta

            cutoff_time = (datetime.now() - timedelta(days=max_days)).isoformat()
            cutoff_epoch = int(time.time()) - (max_days * 24 * 60 * 60)

            with self.get_connection() as conn:
                cursor = conn.cursor()
                total_deleted = 0

                cursor.execute(
                    "DELETE FROM sensor_logs WHERE timestamp < ?",
                    (cutoff_time,),
                )
                total_deleted += cursor.rowcount
                sensor_deleted = cursor.rowcount

                cursor.execute(
                    "DELETE FROM events WHERE timestamp < ?",
                    (cutoff_time,),
                )
                total_deleted += cursor.rowcount
                events_deleted = cursor.rowcount

                cursor.execute(
                    "DELETE FROM system_logs WHERE created_at < ?",
                    (cutoff_time,),
                )
                total_deleted += cursor.rowcount
                syslog_deleted = cursor.rowcount

                cursor.execute(
                    "DELETE FROM device_lru WHERE touched_at < ?",
                    (cutoff_epoch,),
                )
                total_deleted += cursor.rowcount

                conn.commit()

            logger.info(
                "[DB] Cleanup completed: %d total records deleted (sensor=%d, events=%d, syslogs=%d), older than %d days",
                total_deleted,
                sensor_deleted,
                events_deleted,
                syslog_deleted,
                max_days,
            )
            return total_deleted
        except Exception as e:
            logger.error("[DB] Cleanup failed: %s", e)
            raise

    def incremental_vacuum(self, pages: int = 1000) -> None:
        try:
            with self.get_connection() as conn:
                conn.execute(f"PRAGMA incremental_vacuum({pages})")
                conn.commit()
            logger.debug("[DB] Incremental vacuum completed: %d pages", pages)
        except Exception as e:
            logger.warning("[DB] Incremental vacuum failed: %s", e)

    def vacuum(self) -> None:
        try:
            with self.get_connection() as conn:
                conn.execute("VACUUM")
                conn.commit()
            logger.info("[DB] Database vacuum completed")
        except Exception as e:
            logger.error("[DB] Vacuum failed: %s", e)
            raise


db_connector = None


def init_database() -> None:
    get_db_connector().initialize_database()


def get_db_connector() -> SQLiteConnector:
    global db_connector
    if db_connector is None:
        db_connector = SQLiteConnector()
    return db_connector


@contextmanager
def transaction():
    conn = None
    try:
        conn = sqlite3.connect(
            str(get_db_connector().db_path),
            timeout=30,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
        conn.commit()
        logger.debug("[DB] Transaction committed successfully")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("[DB] Transaction rolled back due to error: %s", e)
        raise
    finally:
        if conn:
            conn.close()


def execute_query(query: str, params: Optional[Tuple] = None) -> list[dict[str, Any]]:
    return get_db_connector().execute_query(query, params)


def execute_update(query: str, params: Optional[Tuple] = None) -> int:
    return get_db_connector().execute_update(query, params)


def execute_many(query: str, params_list: list[tuple]) -> int:
    return get_db_connector().execute_many(query, params_list)


def get_database_info() -> dict[str, Any]:
    return get_db_connector().get_database_info()