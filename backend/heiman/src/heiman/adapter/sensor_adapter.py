import logging
from datetime import datetime

from heiman.adapter.adapter_base import BaseDeviceAdapter, DeviceData, PerceptionDevice
from heiman.client.heiman_api_client import HeimanApiClient
from heiman.config import get_settings
from heiman.schema.sensor import SensorData

logger = logging.getLogger(__name__)


class SensorDeviceAdapter(BaseDeviceAdapter):
    device_type = "sensor"
    
    def __init__(self, api_client: HeimanApiClient):
        self._api_client = api_client
        self._devices: dict[str, PerceptionDevice] = {}
        self._sensor_data_cache: dict[str, SensorData] = {}
        self._last_sync_time: float = 0
    
    async def discover_devices(
        self,
        online_only: bool = True,
        cap: bool = True,
    ) -> dict[str, PerceptionDevice]:
        if not self._api_client.is_authenticated:
            await self._api_client.login()
        
        sensor_data_list = await self._api_client.get_sensor_data()
        
        result: dict[str, PerceptionDevice] = {}
        for sensor_data in sensor_data_list:
            if online_only and sensor_data.status == "offline":
                continue
            
            result[sensor_data.did] = PerceptionDevice(
                did=sensor_data.did,
                name=sensor_data.name,
                device_type=sensor_data.sensor_type.value,
                room_id=sensor_data.room_id,
                room_name=sensor_data.room_name,
                online=sensor_data.status != "offline",
            )
        
        return result
    
    async def connect_device(
        self, did: str, source: PerceptionDevice | None = None
    ) -> None:
        if did in self._devices:
            return
        
        if source is None:
            discovered = await self.discover_devices()
            if did not in discovered:
                logger.warning("Sensor %s not found, cannot connect", did)
                return
            source = discovered[did]
        
        self._devices[did] = source
        logger.info("Connected sensor: %s (%s)", did, source.name)
    
    async def disconnect_device(self, did: str) -> None:
        state = self._devices.pop(did, None)
        self._sensor_data_cache.pop(did, None)
        if state:
            logger.info("Disconnected sensor: %s", did)
    
    def collect(self, did: str, *, drain: bool = True) -> DeviceData | None:
        sensor_data = self._sensor_data_cache.get(did)
        if not sensor_data:
            return None
        
        device = self._devices.get(did)
        if not device:
            return None
        
        return DeviceData(
            meta=device,
            sensor_data=sensor_data,
            timestamp=sensor_data.timestamp,
        )

    def update_from_mqtt(self, device_id: str, properties: dict):
        try:
            sensor_data = self._api_client._parse_sensor_data({
                "deviceId": device_id,
                "properties": properties,
            })
            
            if sensor_data:
                self._sensor_data_cache[device_id] = sensor_data
                
                if device_id not in self._devices:
                    self._devices[device_id] = PerceptionDevice(
                        did=device_id,
                        name=f"Device {device_id[:8]}",
                        device_type=sensor_data.sensor_type.value,
                        online=True,
                    )
                
                logger.info("[Adapter] Updated sensor from MQTT: %s - %s", device_id, sensor_data.sensor_type)
        except Exception as e:
            logger.error("[Adapter] Error updating from MQTT: %s", e)

    def get_connected_devices(self) -> dict[str, PerceptionDevice]:
        return self._devices.copy()
    
    async def sync_devices(self) -> None:
        discovered = await self.discover_devices()
        
        for did, device in discovered.items():
            if did not in self._devices:
                await self.connect_device(did, source=device)
        
        connected_dids = set(self._devices.keys())
        discovered_dids = set(discovered.keys())
        for did in connected_dids - discovered_dids:
            await self.disconnect_device(did)
    
    async def refresh_sensor_data(self) -> None:
        sensor_data_list = await self._api_client.get_sensor_data()
        
        for sensor_data in sensor_data_list:
            self._sensor_data_cache[sensor_data.did] = sensor_data
            
            if sensor_data.did not in self._devices:
                await self.connect_device(
                    sensor_data.did,
                    source=PerceptionDevice(
                        did=sensor_data.did,
                        name=sensor_data.name,
                        device_type=sensor_data.sensor_type.value,
                        room_id=sensor_data.room_id,
                        room_name=sensor_data.room_name,
                        online=sensor_data.status != "offline",
                    ),
                )
        
        logger.debug("Refreshed sensor data for %d devices", len(sensor_data_list))