import logging
import asyncio
from typing import Dict, Optional, Any, List

from .device_base import DeviceProtocol, DeviceCategory, DeviceState, BaseDevice, DeviceAction
from .protocol_adapter import ProtocolAdapter

logger = logging.getLogger(__name__)


class MatterDevice(BaseDevice):
    def __init__(self, device_id: str, name: str, node_id: int = 0):
        super().__init__(device_id, name, DeviceProtocol.MATTER, DeviceCategory.UNKNOWN)
        self.node_id = node_id
        self.endpoints: Dict[int, Dict[str, Any]] = {}
        self._setup_category(node_id)

    def _setup_category(self, node_id: int):
        category_map = {
            0x0000: DeviceCategory.SENSOR,
            0x0001: DeviceCategory.SWITCH,
            0x0002: DeviceCategory.LIGHT,
            0x0003: DeviceCategory.THERMOSTAT,
            0x0004: DeviceCategory.LOCK,
            0x0005: DeviceCategory.CAMERA,
            0x0006: DeviceCategory.SPEAKER,
            0x0007: DeviceCategory.CURTAIN,
            0x0008: DeviceCategory.APPLIANCE,
            0x0009: DeviceCategory.SECURITY,
        }
        base_category = node_id & 0x000F
        self.category = category_map.get(base_category, DeviceCategory.UNKNOWN)

    async def execute_action(self, action: DeviceAction) -> bool:
        logger.info(f"Matter device {self.device_id} executing action: {action.name}")
        return True

    async def refresh(self) -> bool:
        logger.debug(f"Refreshing Matter device {self.device_id}")
        return True


class MatterAdapter(ProtocolAdapter):
    def __init__(self):
        super().__init__(DeviceProtocol.MATTER)
        self._commissioner = None
        self._fabric_id = None
        self._network_port = 5540

    async def connect(self, config: Dict[str, Any]) -> bool:
        self._fabric_id = config.get("fabric_id", "heiman-matter-fabric")
        self._network_port = config.get("port", 5540)
        
        try:
            self._commissioner = await self._initialize_commissioner()
            self._connected = True
            logger.info("Matter adapter connected")
            return True
        except Exception as e:
            logger.error(f"Failed to connect Matter adapter: {e}")
            return False

    async def _initialize_commissioner(self):
        return {
            "fabric_id": self._fabric_id,
            "port": self._network_port,
            "nodes": {},
        }

    async def disconnect(self) -> bool:
        self._connected = False
        self._commissioner = None
        logger.info("Matter adapter disconnected")
        return True

    async def discover_devices(self) -> List[BaseDevice]:
        devices = []
        
        mock_nodes = [
            {"node_id": 0x00020001, "name": "Living Room Light", "category": 0x0002},
            {"node_id": 0x00030001, "name": "Thermostat", "category": 0x0003},
            {"node_id": 0x00040001, "name": "Front Door Lock", "category": 0x0004},
            {"node_id": 0x00000001, "name": "Motion Sensor", "category": 0x0000},
        ]

        for node in mock_nodes:
            device = MatterDevice(
                device_id=f"matter-{node['node_id']:08x}",
                name=node["name"],
                node_id=node["node_id"],
            )
            self.add_device(device)
            devices.append(device)

        logger.info(f"Discovered {len(devices)} Matter devices")
        return devices

    async def get_device_state(self, device_id: str) -> Dict[str, Any]:
        device = self.get_device(device_id)
        if not device:
            return {"error": "Device not found"}
        
        return device.to_dict()

    async def execute_action(self, device_id: str, action: DeviceAction) -> bool:
        device = self.get_device(device_id)
        if not device:
            logger.error(f"Device {device_id} not found")
            return False

        try:
            result = await device.execute_action(action)
            await self._notify_callbacks(device_id, {"action": action.name, "success": result})
            return result
        except Exception as e:
            logger.error(f"Failed to execute action on {device_id}: {e}")
            return False

    async def subscribe_device_updates(self, device_id: str) -> bool:
        device = self.get_device(device_id)
        if not device:
            return False
        
        logger.info(f"Subscribed to updates for Matter device {device_id}")
        return True

    async def unsubscribe_device_updates(self, device_id: str) -> bool:
        logger.info(f"Unsubscribed from updates for Matter device {device_id}")
        return True

    async def commission_device(self, setup_code: str, node_id: Optional[int] = None) -> Optional[BaseDevice]:
        try:
            new_node_id = node_id or self._generate_node_id()
            device = MatterDevice(
                device_id=f"matter-{new_node_id:08x}",
                name=f"Matter Device {new_node_id:08x}",
                node_id=new_node_id,
            )
            self.add_device(device)
            
            logger.info(f"Commissioned new Matter device: {device.device_id}")
            await self._notify_callbacks(device.device_id, {"event": "commissioned", "device": device.to_dict()})
            return device
        except Exception as e:
            logger.error(f"Failed to commission device: {e}")
            return None

    def _generate_node_id(self) -> int:
        return 0x00010000 + len(self._devices)