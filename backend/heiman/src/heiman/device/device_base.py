import logging
from datetime import datetime
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DeviceProtocol(str, Enum):
    MQTT = "mqtt"
    HTTP = "http"
    ZIGBEE = "zigbee"
    ZWAVE = "zwave"
    BLUETOOTH = "bluetooth"
    MATTER = "matter"
    WIFI = "wifi"
    LOCAL = "local"


class DeviceCategory(str, Enum):
    SENSOR = "sensor"
    SWITCH = "switch"
    LIGHT = "light"
    THERMOSTAT = "thermostat"
    LOCK = "lock"
    CAMERA = "camera"
    SPEAKER = "speaker"
    CURTAIN = "curtain"
    APPLIANCE = "appliance"
    SECURITY = "security"
    UNKNOWN = "unknown"


class DeviceState(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class DeviceCapability:
    name: str
    supported: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceProperty:
    name: str
    value: Any
    unit: Optional[str] = None
    timestamp: float = 0.0


@dataclass
class DeviceAction:
    name: str
    params: Dict[str, Any] = field(default_factory=dict)


class BaseDevice:
    def __init__(self, device_id: str, name: str, protocol: DeviceProtocol, category: DeviceCategory):
        self.device_id = device_id
        self.name = name
        self.protocol = protocol
        self.category = category
        self.state = DeviceState.UNKNOWN
        self.properties: Dict[str, DeviceProperty] = {}
        self.capabilities: Dict[str, DeviceCapability] = {}
        self.last_update = 0.0
        self.room_id: Optional[str] = None
        self.room_name: Optional[str] = None
        self.manufacturer: Optional[str] = None
        self.model: Optional[str] = None

    def update_property(self, name: str, value: Any, unit: Optional[str] = None):
        self.properties[name] = DeviceProperty(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.now().timestamp(),
        )
        self.last_update = datetime.now().timestamp()
        logger.debug(f"Device {self.device_id} property updated: {name} = {value}")

    def get_property(self, name: str) -> Optional[DeviceProperty]:
        return self.properties.get(name)

    def set_state(self, state: DeviceState):
        self.state = state
        logger.debug(f"Device {self.device_id} state changed to {state.value}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "protocol": self.protocol.value,
            "category": self.category.value,
            "state": self.state.value,
            "properties": {
                name: {
                    "value": prop.value,
                    "unit": prop.unit,
                    "timestamp": prop.timestamp,
                }
                for name, prop in self.properties.items()
            },
            "capabilities": {
                name: {
                    "supported": cap.supported,
                    "params": cap.params,
                }
                for name, cap in self.capabilities.items()
            },
            "last_update": self.last_update,
            "room_id": self.room_id,
            "room_name": self.room_name,
            "manufacturer": self.manufacturer,
            "model": self.model,
        }

    async def execute_action(self, action: DeviceAction) -> bool:
        raise NotImplementedError("execute_action must be implemented by subclass")

    async def refresh(self) -> bool:
        raise NotImplementedError("refresh must be implemented by subclass")