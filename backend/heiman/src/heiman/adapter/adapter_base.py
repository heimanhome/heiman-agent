from abc import ABC, abstractmethod
from datetime import datetime

from heiman.schema.sensor import SensorData


class PerceptionDevice:
    def __init__(
        self,
        did: str,
        name: str,
        device_type: str,
        room_id: str | None = None,
        room_name: str | None = None,
        online: bool = False,
    ):
        self.did = did
        self.name = name
        self.device_type = device_type
        self.room_id = room_id
        self.room_name = room_name
        self.online = online


class DeviceData:
    def __init__(
        self,
        meta: PerceptionDevice,
        sensor_data: SensorData | None = None,
        timestamp: datetime | None = None,
    ):
        self.meta = meta
        self.sensor_data = sensor_data
        self.timestamp = timestamp or datetime.now()
    
    @property
    def has_data(self) -> bool:
        return self.sensor_data is not None


class BaseDeviceAdapter(ABC):
    device_type: str
    
    @abstractmethod
    async def discover_devices(
        self,
        online_only: bool = True,
        cap: bool = True,
    ) -> dict[str, PerceptionDevice]:
        pass
    
    @abstractmethod
    async def connect_device(
        self, did: str, source: PerceptionDevice | None = None
    ) -> None:
        pass
    
    @abstractmethod
    async def disconnect_device(self, did: str) -> None:
        pass
    
    @abstractmethod
    def collect(self, did: str, *, drain: bool = True) -> DeviceData | None:
        pass
    
    @abstractmethod
    def get_connected_devices(self) -> dict[str, PerceptionDevice]:
        pass
    
    def clear_buffers(self) -> None:
        pass
    
    async def sync_devices(self) -> None:
        discovered = await self.discover_devices()
        connected = self.get_connected_devices()
        
        discovered_dids = set(discovered.keys())
        connected_dids = set(connected.keys())
        
        for did in discovered_dids - connected_dids:
            await self.connect_device(did, source=discovered[did])
        
        for did in connected_dids - discovered_dids:
            await self.disconnect_device(did)
    
    async def shutdown(self) -> None:
        for did in list(self.get_connected_devices().keys()):
            await self.disconnect_device(did)