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


class OmniProfile(BaseSettings):
    label: str = "default"
    model: str = "gpt-4o"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""


class ModelSettings(BaseSettings):
    omni: OmniProfile = OmniProfile()
    omni_profiles: list[OmniProfile] = []

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


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        try:
            from dotenv import load_dotenv
            load_dotenv(_env_file_path, override=True)
        except Exception:
            pass
        _settings = Settings()
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


def update_shared_config(**kwargs) -> None:
    """Update shared config in-place. Supports nested dicts like model={'omni': {...}}."""
    global _settings
    settings = get_settings()

    for key, value in kwargs.items():
        if not hasattr(settings, key):
            continue
        if isinstance(value, dict) and hasattr(getattr(settings, key), '__dict__'):
            obj = getattr(settings, key)
            for sub_key, sub_val in value.items():
                if hasattr(obj, sub_key):
                    setattr(obj, sub_key, sub_val)
        else:
            setattr(settings, key, value)

    logger.info("Updated shared config: %s", list(kwargs.keys()))