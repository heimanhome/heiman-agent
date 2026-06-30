import os
import pytest
from pathlib import Path
from unittest.mock import patch

from heiman.config.settings import (
    Settings,
    get_settings,
    reset_settings,
    reload_settings,
    DirectorySettings,
    LoggingSettings,
)


class TestDirectorySettings:
    def test_static_dir_default_path(self, tmp_path):
        with patch.dict(os.environ, {}, clear=True):
            settings = DirectorySettings()
            assert isinstance(settings.static_dir, Path)
            assert settings.static_dir.exists()

    def test_static_dir_env_override(self, tmp_path):
        custom_static = tmp_path / "custom_static"
        with patch.dict(os.environ, {"HEIMAN_STATIC_DIR": str(custom_static)}, clear=True):
            settings = DirectorySettings()
            assert settings.static_dir == custom_static
            assert custom_static.exists()

    def test_static_dir_points_to_project_static(self):
        """回归测试：确保 static_dir 指向正确的项目 static 目录
        之前的实现使用了 Path(__file__).parent.parent.parent，导致指向
        backend/heiman/src/static（不存在），从而产生 HTTP 404。
        应使用 parent.parent.parent.parent 来定位到 backend/heiman/static。
        """
        from heiman.config.settings import Path as SettingsPath

        settings_py = (
            SettingsPath(__file__).parent.parent
            / "src" / "heiman" / "config" / "settings.py"
        )

        with patch.dict(os.environ, {}, clear=True):
            settings = DirectorySettings()
            expected_root = settings_py.parent.parent.parent.parent
            assert settings.static_dir == expected_root / "static"
            assert (settings.static_dir / "index.html").exists()

    def test_data_dir_default_path(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = DirectorySettings()
            assert isinstance(settings.data_dir, Path)
            assert settings.data_dir.exists()

    def test_data_dir_env_override(self, tmp_path):
        custom_data = tmp_path / "custom_data"
        with patch.dict(os.environ, {"HEIMAN_DATA_DIR": str(custom_data)}, clear=True):
            settings = DirectorySettings()
            assert settings.data_dir == custom_data
            assert custom_data.exists()

    def test_config_dir_default_path(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = DirectorySettings()
            assert isinstance(settings.config_dir, Path)
            assert settings.config_dir.exists()

    def test_config_dir_env_override(self, tmp_path):
        custom_config = tmp_path / "custom_config"
        with patch.dict(os.environ, {"HEIMAN_CONFIG_DIR": str(custom_config)}, clear=True):
            settings = DirectorySettings()
            assert settings.config_dir == custom_config
            assert custom_config.exists()


class TestLoggingSettings:
    def test_log_dir_default_path(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = LoggingSettings()
            assert isinstance(settings.log_dir, Path)
            assert settings.log_dir.exists()

    def test_log_dir_env_override(self, tmp_path):
        custom_log = tmp_path / "custom_logs"
        with patch.dict(os.environ, {"HEIMAN_LOG_DIR": str(custom_log)}, clear=True):
            settings = LoggingSettings()
            assert settings.log_dir == custom_log
            assert custom_log.exists()

    def test_log_ttl_days_default(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = LoggingSettings()
            assert settings.log_ttl_days == 30


class TestSettingsLifecycle:
    def test_get_settings_singleton(self):
        reset_settings()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_reset_settings(self):
        s1 = get_settings()
        reset_settings()
        s2 = get_settings()
        assert s1 is not s2

    def test_reload_settings(self):
        s1 = get_settings()
        s2 = reload_settings()
        assert s1 is not s2

    def test_settings_timezone(self):
        settings = Settings()
        assert settings.timezone == "Asia/Shanghai"


class TestPerfSettings:
    def test_perf_defaults(self):
        settings = Settings()
        assert settings.perf.enabled is True
        assert settings.perf.cache_ttl_seconds == 300
        assert settings.perf.max_cache_size == 1000
        assert settings.perf.request_timeout == 10.0
        assert settings.perf.connection_pool_size == 10
