import os
import logging
from pathlib import Path
from typing import Optional

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class HeimanSettings(BaseSettings):
    api_url: str = "https://spapi.heiman.cn"
    authorize_url: str = "https://spfile.heiman.cn/applogin/sso.html"
    client_id: str = "Wn1Y0y14x232MQdJ"
    client_secret: str = "0i0JzQmKdCNGEnmW1Ga8Gk3WtBrTCWAw"
    redirect_uri: str = "http://127.0.0.1:1912/api/auth/heiman_redirect"
    app_id: str = "11"
    email: str = ""
    password: str = ""
    tenant_id: str = "1"
    language: str = "zh-CN"

    mqtt_broker: str = "mqtt.heiman.cn"
    mqtt_port: int = 1884
    mqtt_ssl_enabled: bool = True
    secure_id: str = os.getenv("HEIMAN_SECURE_ID", "")
    secure_key: str = os.getenv("HEIMAN_SECURE_KEY", "")

    model_config = SettingsConfigDict(env_prefix="heiman_")


class SensorSettings(BaseSettings):
    sync_interval_seconds: int = 30
    mqtt_enabled: bool = False
    mqtt_server: str = "mqtt.heiman.cn"
    mqtt_port: int = 1883
    mqtt_secure_id: str = ""
    mqtt_secure_key: str = ""

    model_config = SettingsConfigDict(env_prefix="sensor_")


class RuleSettings(BaseSettings):
    default_cooldown_minutes: int = 5

    model_config = SettingsConfigDict(env_prefix="rule_")


class PerfSettings(BaseSettings):
    enabled: bool = True
    cache_ttl_seconds: int = 300
    max_cache_size: int = 1000
    request_timeout: float = 10.0
    connection_pool_size: int = 10

    model_config = SettingsConfigDict(env_prefix="perf_")


class LoggingSettings(BaseSettings):
    level: str = "INFO"
    log_ttl_days: int = 30

    model_config = SettingsConfigDict(env_prefix="logging_")

    @computed_field
    @property
    def log_dir(self) -> Path:
        if env_path := os.getenv("HEIMAN_LOG_DIR"):
            path = Path(env_path)
        else:
            # 使用 /tmp 避免沙盒权限问题
            path = Path("/tmp/heiman/logs")
        path.mkdir(parents=True, exist_ok=True)
        return path


class DirectorySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="dir_")

    @computed_field
    @property
    def static_dir(self) -> Path:
        if env_path := os.getenv("HEIMAN_STATIC_DIR"):
            path = Path(env_path)
        else:
            # settings.py -> config/ -> heiman/ -> src/ -> backend_root
            backend_root = Path(__file__).parent.parent.parent.parent
            path = backend_root / "static"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @computed_field
    @property
    def data_dir(self) -> Path:
        if env_path := os.getenv("HEIMAN_DATA_DIR"):
            path = Path(env_path)
        else:
            # 使用 /tmp 避免沙盒权限问题(与 log_dir 一致)
            path = Path("/tmp/heiman/data")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @computed_field
    @property
    def config_dir(self) -> Path:
        if env_path := os.getenv("HEIMAN_CONFIG_DIR"):
            path = Path(env_path)
        else:
            path = Path.home() / ".heiman" / "config"
        path.mkdir(parents=True, exist_ok=True)
        return path


class ServerSettings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 1912
    token: str = "heiman_test_token_123"

    model_config = SettingsConfigDict(env_prefix="server_")


class HeimanProfile(BaseSettings):
    label: str = "default"
    model: str = "gpt-4o"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""


class ModelSettings(BaseSettings):
    heiman: HeimanProfile = HeimanProfile()
    heiman_profiles: list[HeimanProfile] = []

    model_config = SettingsConfigDict(env_prefix="model_")


_env_file_path = Path(__file__).parent.parent.parent.parent / ".env"

class Settings(BaseSettings):
    heiman: HeimanSettings = HeimanSettings()
    sensor: SensorSettings = SensorSettings()
    rule: RuleSettings = RuleSettings()
    perf: PerfSettings = PerfSettings()
    logging: LoggingSettings = LoggingSettings()
    server: ServerSettings = ServerSettings()
    directories: DirectorySettings = DirectorySettings()
    model: ModelSettings = ModelSettings()

    model_config = SettingsConfigDict(env_file=str(_env_file_path), extra="ignore")

    timezone: str = "Asia/Shanghai"


_settings: Optional[Settings] = None


def _load_config_from_db() -> Optional[dict]:
    try:
        import json
        from heiman.database.kv_repo import get_kv_repo
        
        kv_repo = get_kv_repo()
        config_json = kv_repo.get("heiman_model_config")
        if config_json:
            config_dict = json.loads(config_json)
            logger.info("[CONFIG] Loaded model config from database: %s", config_dict)
            return config_dict
    except Exception as e:
        logger.error("[CONFIG] Failed to load config from database: %s", e)
    return None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        try:
            from dotenv import load_dotenv
            load_dotenv(_env_file_path, override=True)
        except Exception:
            pass
        _settings = Settings()
        
        saved_config = _load_config_from_db()
        if saved_config:
            for key, value in saved_config.items():
                if hasattr(_settings, key):
                    obj = getattr(_settings, key)
                    if isinstance(value, dict):
                        if key == "model":
                            for sub_key, sub_val in value.items():
                                if sub_key == "heiman" and isinstance(sub_val, dict):
                                    heiman_obj = getattr(obj, "heiman", None)
                                    if heiman_obj and hasattr(heiman_obj, '__dict__'):
                                        for h_key, h_val in sub_val.items():
                                            if hasattr(heiman_obj, h_key):
                                                setattr(heiman_obj, h_key, h_val)
                                                logger.info("[CONFIG] Restored model.heiman.%s from database", h_key)
                                elif sub_key == "heiman_profiles" and isinstance(sub_val, list):
                                    profile_list = []
                                    for profile_data in sub_val:
                                        if isinstance(profile_data, dict):
                                            profile = HeimanProfile(**profile_data)
                                            profile_list.append(profile)
                                    setattr(obj, "heiman_profiles", profile_list)
                                    logger.info("[CONFIG] Restored model.heiman_profiles from database (%d profiles)", len(profile_list))
                                elif hasattr(obj, sub_key):
                                    setattr(obj, sub_key, sub_val)
                                    logger.info("[CONFIG] Restored model.%s from database", sub_key)
                        elif hasattr(obj, '__dict__'):
                            for sub_key, sub_val in value.items():
                                if hasattr(obj, sub_key):
                                    setattr(obj, sub_key, sub_val)
                                    logger.info("[CONFIG] Restored %s.%s from database", key, sub_key)
                    else:
                        setattr(_settings, key, value)
                        logger.info("[CONFIG] Restored %s from database", key)

            if key == "model" and isinstance(value, dict):
                heiman_obj = getattr(_settings.model, "heiman", None)
                profiles = getattr(_settings.model, "heiman_profiles", [])
                if heiman_obj and hasattr(heiman_obj, '__dict__') and len(profiles) == 0:
                    profile_dict = {k: v for k, v in heiman_obj.__dict__.items() if not k.startswith('_')}
                    if profile_dict.get("label"):
                        profile = HeimanProfile(**profile_dict)
                        profiles.append(profile)
                        setattr(_settings.model, "heiman_profiles", profiles)
                        logger.info("[CONFIG] Auto-added heiman to profiles")
    return _settings


def reset_settings() -> None:
    global _settings
    logger.info("Resetting settings to defaults")
    _settings = None


def reload_settings() -> Settings:
    global _settings
    logger.info("Reloading settings from environment")
    _settings = Settings()
    return _settings


def _persist_config_to_db(config_dict: dict) -> None:
    try:
        import json
        from heiman.database.kv_repo import get_kv_repo
        
        kv_repo = get_kv_repo()
        config_json = json.dumps(config_dict)
        kv_repo.set("heiman_model_config", config_json)
        logger.info("[CONFIG] Model config persisted to database")
    except Exception as e:
        logger.error("[CONFIG] Failed to persist config: %s", e)


def update_shared_config(**kwargs) -> None:
    """Update shared config in-place. Supports nested dicts like model={'heiman': {...}}."""
    global _settings
    settings = get_settings()

    persist_data = {}

    for key, value in kwargs.items():
        if not hasattr(settings, key):
            continue
        obj = getattr(settings, key)
        if isinstance(value, dict):
            persist_data[key] = {}
            if key == "model":
                for sub_key, sub_val in value.items():
                    if sub_key == "heiman" and isinstance(sub_val, dict):
                        heiman_obj = getattr(obj, "heiman", None)
                        if heiman_obj and hasattr(heiman_obj, '__dict__'):
                            for h_key, h_val in sub_val.items():
                                if hasattr(heiman_obj, h_key):
                                    setattr(heiman_obj, h_key, h_val)
                            persist_data[key]["heiman"] = {k: v for k, v in heiman_obj.__dict__.items() if not k.startswith('_')}
                    elif sub_key == "heiman_profiles" and isinstance(sub_val, list):
                        profile_list = []
                        for profile_data in sub_val:
                            if isinstance(profile_data, dict):
                                profile = HeimanProfile(**profile_data)
                                profile_list.append(profile)
                            elif hasattr(profile_data, '__dict__'):
                                profile_list.append(profile_data)
                        setattr(obj, "heiman_profiles", profile_list)
                        persist_data[key]["heiman_profiles"] = [
                            {k: v for k, v in p.__dict__.items() if not k.startswith('_')}
                            for p in profile_list
                        ]
                    elif hasattr(obj, sub_key):
                        setattr(obj, sub_key, sub_val)
                        persist_data[key][sub_key] = sub_val
            elif hasattr(obj, '__dict__'):
                for sub_key, sub_val in value.items():
                    if hasattr(obj, sub_key):
                        setattr(obj, sub_key, sub_val)
                        persist_data[key][sub_key] = sub_val
        else:
            setattr(settings, key, value)
            persist_data[key] = value

    logger.info("Updated shared config: %s", list(kwargs.keys()))
    logger.debug("[CONFIG] Persisting config: %s", persist_data)
    
    if persist_data:
        _persist_config_to_db(persist_data)