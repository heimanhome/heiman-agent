import logging
from typing import Dict, Optional, Any, List
from abc import ABC, abstractmethod

from .device_base import DeviceProtocol, BaseDevice, DeviceAction

logger = logging.getLogger(__name__)


class ProtocolAdapter(ABC):
    def __init__(self, protocol: DeviceProtocol):
        self.protocol = protocol
        self._connected = False
        self._devices: Dict[str, BaseDevice] = {}
        self._callbacks: List = []

    @abstractmethod
    async def connect(self, config: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        pass

    @abstractmethod
    async def discover_devices(self) -> List[BaseDevice]:
        pass

    @abstractmethod
    async def get_device_state(self, device_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def execute_action(self, device_id: str, action: DeviceAction) -> bool:
        pass

    @abstractmethod
    async def subscribe_device_updates(self, device_id: str) -> bool:
        pass

    @abstractmethod
    async def unsubscribe_device_updates(self, device_id: str) -> bool:
        pass

    def is_connected(self) -> bool:
        return self._connected

    def add_device(self, device: BaseDevice):
        self._devices[device.device_id] = device
        logger.info(f"Device added: {device.device_id} ({device.name})")

    def remove_device(self, device_id: str):
        if device_id in self._devices:
            del self._devices[device_id]
            logger.info(f"Device removed: {device_id}")

    def get_device(self, device_id: str) -> Optional[BaseDevice]:
        return self._devices.get(device_id)

    def list_devices(self) -> List[BaseDevice]:
        return list(self._devices.values())

    def register_callback(self, callback):
        self._callbacks.append(callback)
        logger.debug(f"Callback registered for {self.protocol.value} adapter")

    def unregister_callback(self, callback):
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            logger.debug(f"Callback unregistered for {self.protocol.value} adapter")

    async def _notify_callbacks(self, device_id: str, data: Dict[str, Any]):
        for callback in self._callbacks:
            try:
                await callback(device_id, data)
            except Exception as e:
                logger.error(f"Error notifying callback: {e}")


class AdapterRegistry:
    _instance = None
    _adapters: Dict[DeviceProtocol, ProtocolAdapter] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register_adapter(self, protocol: DeviceProtocol, adapter: ProtocolAdapter):
        self._adapters[protocol] = adapter
        logger.info(f"Registered adapter for {protocol.value} protocol")

    def get_adapter(self, protocol: DeviceProtocol) -> Optional[ProtocolAdapter]:
        return self._adapters.get(protocol)

    def list_adapters(self) -> List[DeviceProtocol]:
        return list(self._adapters.keys())

    async def connect_all(self) -> bool:
        success_count = 0
        total_count = len(self._adapters)
        
        for protocol, adapter in self._adapters.items():
            try:
                if await adapter.connect({}):
                    success_count += 1
                    logger.info(f"Connected {protocol.value} adapter")
                else:
                    logger.warning(f"Failed to connect {protocol.value} adapter")
            except Exception as e:
                logger.error(f"Error connecting {protocol.value} adapter: {e}")

        return success_count == total_count

    async def disconnect_all(self):
        for protocol, adapter in self._adapters.items():
            try:
                await adapter.disconnect()
                logger.info(f"Disconnected {protocol.value} adapter")
            except Exception as e:
                logger.error(f"Error disconnecting {protocol.value} adapter: {e}")


def get_adapter_registry() -> AdapterRegistry:
    return AdapterRegistry()