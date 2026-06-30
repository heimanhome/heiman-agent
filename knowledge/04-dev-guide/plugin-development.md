# Plugin Development Guide

## Overview

Heiman Agent supports a plugin system that allows extending functionality without modifying core code. Plugins can:
- Process sensor data
- Handle events
- Add custom actions
- Integrate with external services

## Plugin Structure

### Basic Plugin Template

```python
from plugins.base import BasePlugin, PluginConfig

plugin_config = PluginConfig(
    name="MyPlugin",
    version="1.0.0",
    description="My custom plugin",
    author="Your Name",
    enabled=True,
    config={
        "option1": "default_value",
        "option2": 123,
    },
)


class MyPlugin(BasePlugin):
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        # Initialize plugin-specific resources
    
    async def initialize(self) -> None:
        """Called when plugin is loaded"""
        pass
    
    async def shutdown(self) -> None:
        """Called when plugin is unloaded"""
        pass
    
    async def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process incoming events"""
        pass
    
    async def process_sensor_data(self, sensor_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process incoming sensor data"""
        pass
```

## Plugin Configuration

### PluginConfig Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Unique plugin name |
| `version` | str | Semantic version |
| `description` | str | Plugin description |
| `author` | str | Author name |
| `enabled` | bool | Whether plugin is enabled |
| `dependencies` | list | List of dependent plugins |
| `config` | dict | Plugin-specific configuration |

### Configuration Persistence

Plugin configurations are automatically saved to `~/.heiman/plugins/<plugin_name>.json` when modified via the PluginManager.

## Plugin Manager

### Loading Plugins

```python
from plugins.base import PluginManager

manager = PluginManager()

# Load single plugin
manager.load_plugin(Path("/path/to/plugin.py"))

# Load all plugins from directory
manager.load_plugins_from_directory(Path("/path/to/plugins/"))

# Initialize all plugins
await manager.initialize_all()
```

### Managing Plugins

```python
# List all plugins
plugins = manager.list_plugins()

# Get plugin by name
plugin = manager.get_plugin("MyPlugin")

# Enable/disable plugin
manager.enable_plugin("MyPlugin")
manager.disable_plugin("MyPlugin")

# Update plugin config
manager.set_plugin_config("MyPlugin", "option1", "new_value")
```

### Hooks System

Plugins can register hooks for specific event types:

```python
# Register hook for ALARM events
manager.register_hook("ALARM", "AlertPlugin")

# Unregister hook
manager.unregister_hook("ALARM", "AlertPlugin")
```

## Example Plugins

### Log Plugin

Records all events and sensor data to logs.

```python
plugin_config = PluginConfig(
    name="LogPlugin",
    version="1.0.0",
    description="Log all events and sensor data",
    author="Heiman",
)

class LogPlugin(BasePlugin):
    async def process_event(self, event):
        logger.info(f"Event: {event}")
        return {"processed": True}
    
    async def process_sensor_data(self, sensor_data):
        logger.info(f"Sensor: {sensor_data}")
        return {"processed": True}
```

### Webhook Plugin

Sends events to external webhook URLs.

```python
plugin_config = PluginConfig(
    name="WebhookPlugin",
    version="1.0.0",
    description="Send data to webhook",
    author="Heiman",
    config={
        "webhook_url": "",
        "secret": "",
    },
)

class WebhookPlugin(BasePlugin):
    async def process_event(self, event):
        if not self.config.config.get("webhook_url"):
            return None
        
        async with httpx.AsyncClient() as client:
            await client.post(
                self.config.config["webhook_url"],
                json={"type": "event", "data": event},
                headers={"X-Secret": self.config.config.get("secret", "")},
            )
        return {"processed": True}
```

### Alert Plugin

Triggers alerts based on sensor thresholds.

```python
plugin_config = PluginConfig(
    name="AlertPlugin",
    version="1.0.0",
    description="Trigger alerts on threshold breaches",
    author="Heiman",
    config={
        "thresholds": {
            "TEMPERATURE": {"high": 35},
            "SMOKE": {"high": 70},
        },
    },
)

class AlertPlugin(BasePlugin):
    async def process_sensor_data(self, sensor_data):
        sensor_type = sensor_data.get("type")
        value = sensor_data.get("value")
        
        thresholds = self.config.config.get("thresholds", {}).get(sensor_type, {})
        if "high" in thresholds and value > thresholds["high"]:
            alert = {
                "type": "HIGH_ALERT",
                "sensor_type": sensor_type,
                "value": value,
                "threshold": thresholds["high"],
            }
            # Process alert...
            return {"processed": True, "alert": alert}
        return None
```

## Plugin Development Workflow

### 1. Create Plugin File

Create a new Python file in `plugins/examples/` or any custom directory.

### 2. Implement BasePlugin Methods

Implement all abstract methods:
- `initialize()`: Setup resources
- `shutdown()`: Cleanup resources
- `process_event()`: Handle events
- `process_sensor_data()`: Handle sensor data

### 3. Test the Plugin

```python
import asyncio
from plugins.base import PluginManager

async def test_plugin():
    manager = PluginManager()
    manager.load_plugin(Path("/path/to/your/plugin.py"))
    await manager.initialize_all()
    
    # Test event processing
    event = {"type": "INFO", "message": "test"}
    result = await manager.process_event(event)
    print(result)
    
    # Test sensor data processing
    sensor_data = {"id": "test", "type": "TEMPERATURE", "value": 25}
    result = await manager.process_sensor_data(sensor_data)
    print(result)
    
    await manager.shutdown_all()

asyncio.run(test_plugin())
```

### 4. Deploy the Plugin

Copy the plugin file to the plugins directory:

```bash
cp my_plugin.py heiman-agent/plugins/
```

Restart the service to load the new plugin:

```bash
heiman-cli service restart
```

## Best Practices

### Error Handling

Always handle exceptions in plugin methods:

```python
async def process_event(self, event):
    try:
        # Your code here
    except Exception as e:
        logger.error(f"Error processing event: {e}")
        return None
```

### Resource Management

Use `initialize()` and `shutdown()` for resource management:

```python
class MyPlugin(BasePlugin):
    def __init__(self, config):
        super().__init__(config)
        self.client = None
    
    async def initialize(self):
        self.client = httpx.AsyncClient()
    
    async def shutdown(self):
        if self.client:
            await self.client.aclose()
```

### Configuration Validation

Validate configuration in `initialize()`:

```python
async def initialize(self):
    webhook_url = self.config.config.get("webhook_url")
    if not webhook_url:
        logger.warning("webhook_url not configured")
        self.config.enabled = False
```

### Performance Considerations

- Avoid blocking operations in async methods
- Use connection pooling for HTTP clients
- Batch operations when possible
- Limit memory usage

## Debugging Plugins

### Enable Debug Logging

```bash
heiman-cli config set debug true --no-restart
```

### View Logs

```bash
heiman-cli admin logs -f
```

### Check Plugin Status

```python
from plugins.base import PluginManager

manager = PluginManager()
manager.load_plugins_from_directory(Path("/path/to/plugins"))

status = manager.get_plugin_status("MyPlugin")
print(status)
```

## Plugin API Reference

### BasePlugin Methods

| Method | Description |
|--------|-------------|
| `get_name()` | Returns plugin name |
| `get_version()` | Returns plugin version |
| `get_description()` | Returns plugin description |
| `is_enabled()` | Returns enabled status |
| `enable()` | Enables the plugin |
| `disable()` | Disables the plugin |
| `get_config()` | Returns plugin-specific config |
| `set_config(key, value)` | Sets config value |

### PluginManager Methods

| Method | Description |
|--------|-------------|
| `load_plugin(path)` | Loads a single plugin |
| `load_plugins_from_directory(dir)` | Loads all plugins from directory |
| `initialize_all()` | Initializes all plugins |
| `shutdown_all()` | Shuts down all plugins |
| `process_event(event)` | Processes event through all plugins |
| `process_sensor_data(data)` | Processes sensor data through all plugins |
| `register_hook(type, name)` | Registers hook for event type |
| `unregister_hook(type, name)` | Unregisters hook |
| `list_plugins()` | Returns list of plugins |
| `get_plugin(name)` | Returns plugin by name |
| `enable_plugin(name)` | Enables plugin |
| `disable_plugin(name)` | Disables plugin |
| `set_plugin_config(name, key, value)` | Updates plugin config |
| `get_plugin_status(name)` | Returns plugin status |