"""插件系统基础模块。

提供插件基类、配置管理和插件管理器。
"""

import importlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class PluginConfig:
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    enabled: bool = True
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    schema: Dict[str, Any] = field(default_factory=dict)
    hooks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginConfig":
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            enabled=data.get("enabled", True),
            dependencies=data.get("dependencies", []),
            config=data.get("config", {}),
            schema=data.get("schema", {}),
            hooks=data.get("hooks", []),
        )

    def validate_config(self) -> List[str]:
        errors = []
        for key, spec in self.schema.items():
            if spec.get("required", False) and key not in self.config:
                errors.append(f"missing required config: {key}")
            if key in self.config:
                value = self.config[key]
                expected_type = spec.get("type")
                if expected_type and not isinstance(value, expected_type):
                    errors.append(f"config '{key}' expects {expected_type.__name__}, got {type(value).__name__}")
                min_val = spec.get("min")
                if min_val is not None and value < min_val:
                    errors.append(f"config '{key}' must be >= {min_val}")
                max_val = spec.get("max")
                if max_val is not None and value > max_val:
                    errors.append(f"config '{key}' must be <= {max_val}")
        return errors


class BasePlugin(ABC):
    config: PluginConfig
    _initialized: bool = False
    _error_count: int = 0
    _max_errors: int = 5

    def __init__(self, config: PluginConfig):
        self.config = config

    @abstractmethod
    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        pass

    @abstractmethod
    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def process_sensor_data(self, sensor_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass

    def get_name(self) -> str:
        return self.config.name

    def get_version(self) -> str:
        return self.config.version

    def get_description(self) -> str:
        return self.config.description

    def is_enabled(self) -> bool:
        return self.config.enabled

    def enable(self) -> None:
        self.config.enabled = True

    def disable(self) -> None:
        self.config.enabled = False

    def get_config(self) -> Dict[str, Any]:
        return self.config.config

    def set_config(self, key: str, value: Any) -> None:
        self.config.config[key] = value

    def validate_config(self) -> List[str]:
        return self.config.validate_config()

    def record_error(self) -> bool:
        self._error_count += 1
        if self._error_count >= self._max_errors:
            logger.warning(f"Plugin {self.get_name()} has exceeded max errors ({self._max_errors}), disabling")
            self.disable()
            return True
        return False

    def reset_error_count(self) -> None:
        self._error_count = 0

    def get_error_count(self) -> int:
        return self._error_count

    def is_initialized(self) -> bool:
        return self._initialized

    def set_initialized(self, value: bool) -> None:
        self._initialized = value

    async def health_check(self) -> Dict[str, Any]:
        return {
            "name": self.get_name(),
            "version": self.get_version(),
            "enabled": self.is_enabled(),
            "initialized": self.is_initialized(),
            "error_count": self.get_error_count(),
        }


class PluginManager:
    def __init__(self, config_dir: Optional[Path] = None):
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_configs: Dict[str, PluginConfig] = {}
        self.config_dir = config_dir or Path.home() / ".heiman" / "plugins"
        self._hooks: Dict[str, List[str]] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._sensor_handlers: List[Callable] = []

    def load_plugin(self, plugin_path: Path) -> bool:
        try:
            spec = importlib.util.spec_from_file_location(
                plugin_path.stem, plugin_path
            )
            if spec is None or spec.loader is None:
                logger.error(f"Failed to load plugin: {plugin_path}")
                return False

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            plugin_class = None
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and issubclass(obj, BasePlugin) and obj != BasePlugin:
                    plugin_class = obj
                    break

            if plugin_class is None:
                logger.warning(f"No plugin class found in: {plugin_path}")
                return False

            saved_config = self._load_plugin_config(plugin_class.__name__)
            module_config = getattr(module, 'plugin_config', None)

            if saved_config:
                config = saved_config
            elif module_config:
                config = module_config
            else:
                config = PluginConfig(name=plugin_class.__name__)

            validation_errors = config.validate_config()
            if validation_errors:
                logger.warning(f"Plugin {config.name} config validation errors: {validation_errors}")

            plugin = plugin_class(config)
            self.plugins[plugin.get_name()] = plugin
            self.plugin_configs[plugin.get_name()] = config

            for hook in config.hooks:
                self.register_hook(hook, plugin.get_name())

            logger.info(f"Loaded plugin: {plugin.get_name()} v{plugin.get_version()}")
            return True

        except Exception as e:
            logger.error(f"Error loading plugin {plugin_path}: {e}")
            return False

    def load_plugins_from_directory(self, directory: Path) -> None:
        if not directory.exists():
            logger.warning(f"Plugin directory not found: {directory}")
            return

        for plugin_file in directory.glob("*.py"):
            if plugin_file.stem == "__init__":
                continue
            self.load_plugin(plugin_file)

    def _load_plugin_config(self, plugin_name: str) -> Optional[PluginConfig]:
        config_file = self.config_dir / f"{plugin_name}.json"
        if not config_file.exists():
            return None
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PluginConfig.from_dict(data)
        except Exception as e:
            logger.error(f"Error loading config for {plugin_name}: {e}")
            return None

    def _save_plugin_config(self, plugin_name: str, config: PluginConfig) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        config_file = self.config_dir / f"{plugin_name}.json"
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved config for {plugin_name}")
        except Exception as e:
            logger.error(f"Error saving config for {plugin_name}: {e}")

    async def initialize_all(self) -> Dict[str, bool]:
        results = {}
        for plugin_name, plugin in self.plugins.items():
            if plugin.is_enabled():
                try:
                    await plugin.initialize()
                    plugin.set_initialized(True)
                    plugin.reset_error_count()
                    results[plugin_name] = True
                    logger.info(f"Initialized plugin: {plugin_name}")
                except Exception as e:
                    logger.error(f"Error initializing plugin {plugin_name}: {e}")
                    plugin.record_error()
                    results[plugin_name] = False
        return results

    async def shutdown_all(self) -> Dict[str, bool]:
        results = {}
        for plugin_name, plugin in self.plugins.items():
            if plugin.is_enabled():
                try:
                    await plugin.shutdown()
                    plugin.set_initialized(False)
                    results[plugin_name] = True
                    logger.info(f"Shutdown plugin: {plugin_name}")
                except Exception as e:
                    logger.error(f"Error shutting down plugin {plugin_name}: {e}")
                    results[plugin_name] = False
        return results

    async def process_event(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        event_type = event.get("type", "")
        hooks = self._hooks.get(event_type, []) + list(self.plugins.keys())

        for plugin_name in hooks:
            plugin = self.plugins.get(plugin_name)
            if plugin and plugin.is_enabled():
                try:
                    result = await plugin.process_event(event)
                    if result:
                        results.append(result)
                    plugin.reset_error_count()
                except Exception as e:
                    logger.error(f"Error processing event in plugin {plugin_name}: {e}")
                    if plugin.record_error():
                        await self._on_plugin_disabled(plugin_name)
        return results

    async def process_sensor_data(self, sensor_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        for plugin in self.plugins.values():
            if plugin.is_enabled():
                try:
                    result = await plugin.process_sensor_data(sensor_data)
                    if result:
                        results.append(result)
                    plugin.reset_error_count()
                except Exception as e:
                    logger.error(f"Error processing sensor data in plugin {plugin.get_name()}: {e}")
                    if plugin.record_error():
                        await self._on_plugin_disabled(plugin.get_name())
        return results

    async def _on_plugin_disabled(self, plugin_name: str) -> None:
        logger.info(f"Plugin {plugin_name} was disabled due to too many errors")

    def register_hook(self, event_type: str, plugin_name: str) -> None:
        if event_type not in self._hooks:
            self._hooks[event_type] = []
        if plugin_name not in self._hooks[event_type]:
            self._hooks[event_type].append(plugin_name)
            logger.info(f"Registered hook: {event_type} -> {plugin_name}")

    def unregister_hook(self, event_type: str, plugin_name: str) -> None:
        if event_type in self._hooks and plugin_name in self._hooks[event_type]:
            self._hooks[event_type].remove(plugin_name)
            logger.info(f"Unregistered hook: {event_type} -> {plugin_name}")

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        return self.plugins.get(name)

    def list_plugins(self) -> List[Dict[str, Any]]:
        result = []
        for plugin in self.plugins.values():
            result.append({
                "name": plugin.get_name(),
                "version": plugin.get_version(),
                "description": plugin.get_description(),
                "enabled": plugin.is_enabled(),
                "author": plugin.config.author,
                "initialized": plugin.is_initialized(),
                "error_count": plugin.get_error_count(),
            })
        return result

    def enable_plugin(self, name: str) -> bool:
        plugin = self.plugins.get(name)
        if plugin:
            plugin.enable()
            self._save_plugin_config(name, plugin.config)
            logger.info(f"Enabled plugin: {name}")
            return True
        return False

    def disable_plugin(self, name: str) -> bool:
        plugin = self.plugins.get(name)
        if plugin:
            plugin.disable()
            self._save_plugin_config(name, plugin.config)
            logger.info(f"Disabled plugin: {name}")
            return True
        return False

    def set_plugin_config(self, name: str, key: str, value: Any) -> bool:
        plugin = self.plugins.get(name)
        if plugin:
            plugin.set_config(key, value)
            self._save_plugin_config(name, plugin.config)
            logger.info(f"Updated config for {name}: {key} = {value}")
            return True
        return False

    def get_plugin_status(self, name: str) -> Optional[Dict[str, Any]]:
        plugin = self.plugins.get(name)
        if not plugin:
            return None
        return {
            "name": plugin.get_name(),
            "version": plugin.get_version(),
            "description": plugin.get_description(),
            "enabled": plugin.is_enabled(),
            "author": plugin.config.author,
            "config": plugin.get_config(),
            "dependencies": plugin.config.dependencies,
            "schema": plugin.config.schema,
            "hooks": plugin.config.hooks,
            "initialized": plugin.is_initialized(),
            "error_count": plugin.get_error_count(),
        }

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        results = {}
        for plugin_name, plugin in self.plugins.items():
            results[plugin_name] = await plugin.health_check()
        return results

    def reload_plugin(self, name: str) -> bool:
        plugin = self.plugins.get(name)
        if not plugin:
            return False

        config = plugin.config
        plugin_path = None
        for p in self.config_dir.glob("*.py"):
            if p.stem.lower() == name.lower():
                plugin_path = p
                break

        if plugin_path:
            del self.plugins[name]
            return self.load_plugin(plugin_path)
        return False

    def get_hooks(self) -> Dict[str, List[str]]:
        return dict(self._hooks)

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        graph = {}
        for plugin_name, plugin in self.plugins.items():
            graph[plugin_name] = plugin.config.dependencies
        return graph

    def check_dependencies(self) -> Dict[str, List[str]]:
        missing = {}
        installed_plugins = set(self.plugins.keys())
        for plugin_name, plugin in self.plugins.items():
            deps = plugin.config.dependencies
            missing_deps = [d for d in deps if d not in installed_plugins]
            if missing_deps:
                missing[plugin_name] = missing_deps
        return missing