import logging
from datetime import datetime

from heiman.adapter.adapter_base import BaseDeviceAdapter, DeviceData, PerceptionDevice
from heiman.schema.sensor import SensorData

logger = logging.getLogger(__name__)


class SensorCollector:
    def __init__(self, adapters: list[BaseDeviceAdapter]):
        self._adapters: dict[str, BaseDeviceAdapter] = {
            adapter.device_type: adapter for adapter in adapters
        }
    
    async def sync_all_devices(self) -> None:
        for adapter in self._adapters.values():
            await adapter.sync_devices()
    
    def collect(self, did: str, *, drain: bool = True) -> DeviceData | None:
        for adapter in self._adapters.values():
            if did in adapter.get_connected_devices():
                return adapter.collect(did, drain=drain)
        return None
    
    def collect_batch(
        self, dids: list[str] | None = None, *, drain: bool = True
    ) -> dict[str, DeviceData]:
        result: dict[str, DeviceData] = {}
        
        target_dids = dids if dids else list(self.get_all_active_sources().keys())
        
        for did in target_dids:
            device_data = self.collect(did, drain=drain)
            if device_data and device_data.has_data:
                result[did] = device_data
        
        return result
    
    def get_all_active_sources(self) -> dict[str, PerceptionDevice]:
        result: dict[str, PerceptionDevice] = {}
        for adapter in self._adapters.values():
            result.update(adapter.get_connected_devices())
        return result
    
    def get_sensor_data_list(self) -> list[SensorData]:
        result: list[SensorData] = []
        
        for adapter in self._adapters.values():
            for did in adapter.get_connected_devices().keys():
                device_data = adapter.collect(did, drain=False)
                if device_data and device_data.sensor_data:
                    result.append(device_data.sensor_data)
        
        return result
    
    def clear_all_buffers(self) -> None:
        for adapter in self._adapters.values():
            adapter.clear_buffers()
    
    def get_adapter(self, device_type: str) -> BaseDeviceAdapter | None:
        return self._adapters.get(device_type)
    
    async def shutdown(self) -> None:
        for adapter in self._adapters.values():
            await adapter.shutdown()