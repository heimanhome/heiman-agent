import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from heiman.manager import get_manager
from heiman.schema.sensor import SensorType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["devices"])

SENSOR_TYPE_MAP = {
    SensorType.SMOKE: "smoke",
    SensorType.CO: "co",
    SensorType.WATER: "water",
    SensorType.TEMPERATURE: "temperature",
    SensorType.HUMIDITY: "humidity",
    SensorType.CONTACT: "contact",
    SensorType.MOTION: "motion",
    SensorType.PLUG: "plug",
    SensorType.SIREN: "siren",
    SensorType.BUTTON: "button",
    SensorType.GATEWAY: "gateway",
    SensorType.REMOTE: "remote",
}

PROPERTY_TO_SENSOR_TYPE = {
    "SmokeSensorState": SensorType.SMOKE,
    "HeatSensorStatus": SensorType.SMOKE,
    "CurrentTemperature": SensorType.TEMPERATURE,
    "CurrentHumidity": SensorType.HUMIDITY,
    "GasSensorState": SensorType.CO,
    "coValue": SensorType.CO,
    "CONC": SensorType.CO,
    "gasValue": SensorType.CO,
    "GAS": SensorType.CO,
    "WaterSensorState": SensorType.WATER,
    "soaking_state": SensorType.WATER,
    "ContactState": SensorType.CONTACT,
    "SwitchState": SensorType.PLUG,
    "open_state": SensorType.CONTACT,
    "OF": SensorType.MOTION,
    "DetectState": SensorType.MOTION,
    "MotionState": SensorType.MOTION,
    "motion": SensorType.MOTION,
    "pir": SensorType.MOTION,
    "Status": SensorType.PLUG,
    "OnOff": SensorType.PLUG,
    "PowerSwitch": SensorType.PLUG,
    "ON": SensorType.PLUG,
    "actp": SensorType.PLUG,
    "PowerSwitch_1": SensorType.PLUG,
    "PowerSwitch_2": SensorType.PLUG,
    "PowerSwitch_3": SensorType.PLUG,
    "AlarmState": SensorType.SIREN,
    "SirenState": SensorType.SIREN,
    "AlarmSwitch": SensorType.SIREN,
    "ButtonState": SensorType.BUTTON,
    "Press": SensorType.BUTTON,
    "Alarm": SensorType.BUTTON,
    "alarmSta": SensorType.BUTTON,
    "SceneID": SensorType.REMOTE,
    "CurtainPosition": SensorType.REMOTE,
    "FallDown": SensorType.MOTION,
    "LockState": SensorType.CONTACT,
    "RingSwitch": SensorType.REMOTE,
    "HandState": SensorType.REMOTE,
    "temperature": SensorType.TEMPERATURE,
    "humidity": SensorType.HUMIDITY,
    "smoke": SensorType.SMOKE,
    "gas": SensorType.CO,
    "water": SensorType.WATER,
    "contact": SensorType.CONTACT,
    "switch": SensorType.PLUG,
    "plug": SensorType.PLUG,
    "siren": SensorType.SIREN,
    "button": SensorType.BUTTON,
}

UNIT_MAP = {
    SensorType.TEMPERATURE: "°C",
    SensorType.HUMIDITY: "%",
    SensorType.CO: "ppm",
    SensorType.SMOKE: "",
    SensorType.WATER: "",
    SensorType.CONTACT: "",
    SensorType.MOTION: "",
    SensorType.PLUG: "",
    SensorType.SIREN: "",
    SensorType.BUTTON: "",
    SensorType.GATEWAY: "",
    SensorType.REMOTE: "",
}

PRODUCT_NAME_KEYWORDS = [
    ("烟雾", SensorType.SMOKE),
    ("烟感", SensorType.SMOKE),
    ("smoke", SensorType.SMOKE),
    ("温感", SensorType.SMOKE),
    ("heat", SensorType.SMOKE),
    ("燃气", SensorType.CO),
    ("gas", SensorType.CO),
    ("CO", SensorType.CO),
    ("co", SensorType.CO),
    ("一氧化碳", SensorType.CO),
    ("水浸", SensorType.WATER),
    ("水位", SensorType.WATER),
    ("water", SensorType.WATER),
    ("漏水", SensorType.WATER),
    ("温湿度", SensorType.TEMPERATURE),
    ("温度", SensorType.TEMPERATURE),
    ("temp", SensorType.TEMPERATURE),
    ("humidity", SensorType.HUMIDITY),
    ("湿度", SensorType.HUMIDITY),
    ("门磁", SensorType.CONTACT),
    ("门窗", SensorType.CONTACT),
    ("contact", SensorType.CONTACT),
    ("door", SensorType.CONTACT),
    ("人体", SensorType.MOTION),
    ("存在", SensorType.MOTION),
    ("占位", SensorType.MOTION),
    ("occupancy", SensorType.MOTION),
    ("presence", SensorType.MOTION),
    ("pir", SensorType.MOTION),
    ("PIR", SensorType.MOTION),
    ("motion", SensorType.MOTION),
    ("红外", SensorType.MOTION),
    ("振动", SensorType.MOTION),
    ("shock", SensorType.MOTION),
    ("跌倒", SensorType.MOTION),
    ("fall", SensorType.MOTION),
    ("插座", SensorType.PLUG),
    ("开关", SensorType.PLUG),
    ("switch", SensorType.PLUG),
    ("plug", SensorType.PLUG),
    ("power", SensorType.PLUG),
    ("light", SensorType.PLUG),
    ("灯", SensorType.PLUG),
    ("计量", SensorType.PLUG),
    ("声光", SensorType.SIREN),
    ("警号", SensorType.SIREN),
    ("siren", SensorType.SIREN),
    ("门铃", SensorType.REMOTE),
    ("curtain", SensorType.REMOTE),
    ("窗帘", SensorType.REMOTE),
    ("门锁", SensorType.CONTACT),
    ("lock", SensorType.CONTACT),
    ("机械手", SensorType.REMOTE),
    ("阀门", SensorType.REMOTE),
    ("应急", SensorType.BUTTON),
    ("紧急", SensorType.BUTTON),
    ("按钮", SensorType.BUTTON),
    ("button", SensorType.BUTTON),
    ("SOS", SensorType.BUTTON),
    ("sos", SensorType.BUTTON),
    ("网关", SensorType.GATEWAY),
    ("gateway", SensorType.GATEWAY),
    ("GW", SensorType.GATEWAY),
    ("gw", SensorType.GATEWAY),
    ("遥控", SensorType.REMOTE),
    ("remote", SensorType.REMOTE),
    ("情景", SensorType.REMOTE),
    ("scene", SensorType.REMOTE),
    ("空调", SensorType.REMOTE),
    ("ac", SensorType.REMOTE),
]


def _get_product_info(product_id: str) -> dict | None:
    try:
        from heiman.database.connector import get_db_connector
        from heiman.database.product_repo import ProductRepo
        db = get_db_connector()
        repo = ProductRepo(db)
        return repo.get_product(product_id)
    except Exception as e:
        logger.debug("[Device Router] Failed to get product info for %s: %s", product_id, e)
        return None


@router.get("", response_model=dict)
async def get_devices(
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    home_id: Optional[str] = Query(None),
):
    try:
        mgr = get_manager()

        if mgr.api_client.is_authenticated:
            all_devices = await mgr.api_client.get_all_devices(home_id)
            if all_devices:
                logger.info("[DEVICE API] Raw device keys: %s", list(all_devices[0].keys()))
                logger.info("[DEVICE API] Has deriveMetadata: %s", 'deriveMetadata' in all_devices[0])
            rooms = await mgr.api_client.get_room_list(home_id or "")

            room_name_map = {}
            for room in rooms:
                rid = str(room.get("roomId", room.get("id", "")))
                rname = room.get("roomName", room.get("name", ""))
                if rid and rname:
                    room_name_map[rid] = rname

            devices = []
            for device in all_devices:
                device_id = str(device.get("id", device.get("deviceId", "")))
                device_name = device.get("deviceName", device.get("name", ""))
                room_id = str(device.get("roomId", ""))
                room_name = device.get("roomName", "") or room_name_map.get(room_id, "")

                state_info = device.get("state", {})
                if isinstance(state_info, dict):
                    device_status = state_info.get("value", "offline")
                else:
                    device_status = device.get("state", "offline")

                device_type_info = device.get("deviceType", {})
                if isinstance(device_type_info, dict):
                    device_type = device_type_info.get("value", "unknown")
                else:
                    device_type = device.get("deviceType", "unknown")

                if type and device_type != type:
                    continue

                if status and device_status != status:
                    continue

                if search:
                    search_lower = search.lower()
                    if search_lower not in device_name.lower():
                        continue

                battery = -1
                rssi = -999
                switch_state = None
                smoke_state = None
                gas_state = None
                water_state = None
                temperature = None
                humidity = None
                co2 = None
                pm25 = None
                pm10 = None
                hcho = None
                motion_state = None
                tamper_state = None
                sensor_life_status = None
                alarm_state = None
                properties = device.get("properties", {})
                derive_metadata = device.get("deriveMetadata", "[]")
                derive_metadata_list = []
                
                if isinstance(derive_metadata, str):
                    try:
                        import json
                        derive_metadata_list = json.loads(derive_metadata)
                    except (json.JSONDecodeError, TypeError):
                        derive_metadata_list = []
                elif isinstance(derive_metadata, list):
                    derive_metadata_list = derive_metadata

                if isinstance(properties, dict):
                    bat_val = properties.get("BatteryPercentage")
                    if bat_val is not None:
                        battery = bat_val
                    if battery == 0 or battery == -1:
                        if "battery_value" in device:
                            bv = device.get("battery_value")
                            if bv is not None:
                                battery = bv

                for prop in derive_metadata_list:
                    if isinstance(prop, dict):
                        prop_id = prop.get("property", "")
                        if prop_id in ["BatteryPercentage", "battery_value"]:
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    battery = int(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "battery":
                            try:
                                val = prop.get("value", "")
                                if isinstance(val, str):
                                    val = val.replace("%", "")
                                    battery = int(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "SwitchState":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    switch_state = int(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "ContactState":
                            if switch_state is None:
                                try:
                                    val = prop.get("numberValue", prop.get("value"))
                                    if val is not None:
                                        switch_state = int(float(val))
                                except (ValueError, TypeError):
                                    pass
                        elif prop_id == "RSSI" or prop_id == "rsrp" or prop_id == "signalStrength":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    rssi = int(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "DeviceINFO":
                            if rssi == -999:
                                info_val = prop.get("value")
                                if isinstance(info_val, dict):
                                    dbm = info_val.get("DBM")
                                    if dbm is not None:
                                        try:
                                            rssi = int(float(dbm))
                                        except (ValueError, TypeError):
                                            pass
                                elif isinstance(info_val, str):
                                    try:
                                        import json as _json
                                        info_dict = _json.loads(info_val)
                                        dbm = info_dict.get("DBM")
                                        if dbm is not None:
                                            rssi = int(float(dbm))
                                    except (_json.JSONDecodeError, ValueError, TypeError):
                                        pass
                        elif prop_id == "SmokeSensorState":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    smoke_state = int(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "GasSensorState":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    gas_state = int(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "WaterSensorState":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    water_state = int(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "CurrentTemperature":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    temperature = float(val)
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "CurrentHumidity":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    humidity = float(val)
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "co2":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    co2 = int(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "PM25":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    pm25 = int(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "PM10":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    pm10 = int(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "HCHO":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    hcho = float(val)
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "MotionAlarmState":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    motion_state = int(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "TamperState":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    tamper_state = int(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "SensorLifeStatus":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    sensor_life_status = int(float(val))
                            except (ValueError, TypeError):
                                pass
                        elif prop_id == "Alarm":
                            try:
                                val = prop.get("numberValue", prop.get("value"))
                                if val is not None:
                                    alarm_state = int(float(val))
                            except (ValueError, TypeError):
                                pass

                if isinstance(properties, dict) and switch_state is None:
                    for sk in ["SwitchState", "ContactState"]:
                        if sk in properties:
                            try:
                                switch_state = int(float(properties[sk]))
                                break
                            except (ValueError, TypeError):
                                pass

                value = 0
                unit = ""
                sensor_type_str = None
                product_id = str(device.get("productId", ""))

                if product_id:
                    product_info = _get_product_info(product_id)
                    if product_info:
                        classified_name = product_info.get("classified_name", "")
                        product_name = product_info.get("name", "")
                        for keyword, st in PRODUCT_NAME_KEYWORDS:
                            if keyword.lower() in classified_name.lower() or keyword.lower() in product_name.lower():
                                sensor_type_str = SENSOR_TYPE_MAP.get(st, st.value if hasattr(st, 'value') else str(st))
                                unit = UNIT_MAP.get(st, "")
                                break

                if not sensor_type_str:
                    for prop in derive_metadata_list:
                        if isinstance(prop, dict):
                            prop_id = prop.get("property", "")
                            prop_val = prop.get("value")
                            if prop_id in PROPERTY_TO_SENSOR_TYPE:
                                st = PROPERTY_TO_SENSOR_TYPE[prop_id]
                                sensor_type_str = SENSOR_TYPE_MAP.get(st, st.value if hasattr(st, 'value') else str(st))
                                if prop_val is not None:
                                    try:
                                        num_val = prop.get("numberValue")
                                        if num_val is not None:
                                            value = num_val
                                        else:
                                            value = float(prop_val) if prop_val else 0
                                    except (ValueError, TypeError):
                                        value = 0
                                unit = UNIT_MAP.get(st, "")
                                break

                if isinstance(properties, dict) and not sensor_type_str:
                    for prop_key, prop_val in properties.items():
                        if prop_key in PROPERTY_TO_SENSOR_TYPE:
                            st = PROPERTY_TO_SENSOR_TYPE[prop_key]
                            sensor_type_str = SENSOR_TYPE_MAP.get(st, st.value if hasattr(st, 'value') else str(st))
                            value = prop_val if prop_val is not None else 0
                            unit = UNIT_MAP.get(st, "")
                            break

                if not sensor_type_str:
                    device_name_lower = device_name.lower()
                    for keyword, st in PRODUCT_NAME_KEYWORDS:
                        if keyword.lower() in device_name_lower:
                            sensor_type_str = SENSOR_TYPE_MAP.get(st, st.value if hasattr(st, 'value') else str(st))
                            unit = UNIT_MAP.get(st, "")
                            break

                if not sensor_type_str:
                    product_name = str(device.get("productName", ""))
                    for keyword, st in PRODUCT_NAME_KEYWORDS:
                        if keyword.lower() in product_name.lower():
                            sensor_type_str = SENSOR_TYPE_MAP.get(st, st.value if hasattr(st, 'value') else str(st))
                            unit = UNIT_MAP.get(st, "")
                            break

                if sensor_type_str == "contact":
                    if switch_state is not None:
                        if switch_state in [0, 2]:
                            value = "门窗关闭"
                        elif switch_state in [1, 3]:
                            value = "门窗打开"
                        else:
                            value = str(switch_state)
                    else:
                        value = ""
                
                devices.append({
                    "id": device_id,
                    "name": device_name,
                    "type": sensor_type_str or device_type,
                    "status": device_status,
                    "value": value,
                    "unit": unit,
                    "room": room_name or "",
                    "battery": battery,
                    "rssi": rssi,
                    "switchState": switch_state,
                    "smokeState": smoke_state,
                    "gasState": gas_state,
                    "waterState": water_state,
                    "temperature": temperature,
                    "humidity": humidity,
                    "co2": co2,
                    "pm25": pm25,
                    "pm10": pm10,
                    "hcho": hcho,
                    "motionState": motion_state,
                    "tamperState": tamper_state,
                    "sensorLifeStatus": sensor_life_status,
                    "alarmState": alarm_state,
                    "lastUpdate": "Just now",
                    "home_id": str(device.get("homeId", "")),
                    "productName": device.get("productName", ""),
                    "photoUrl": device.get("photoUrl", ""),
                    "parentId": device.get("parentId", ""),
                    "productId": str(device.get("productId", "")),
                    "deriveMetadata": derive_metadata_list,
                })

            logger.info("[DEVICE API] Get devices - home_id=%s, count=%d", home_id, len(devices))

            status_change_events = mgr.detect_device_status_changes(devices)
            for event in status_change_events:
                try:
                    mgr.event_repo.insert(event)
                except Exception as ev_err:
                    logger.warning("[DEVICE API] Failed to insert status change event: %s", ev_err)

            return {"success": True, "data": devices}
        else:
            logger.info("[DEVICE API] Offline mode - returning cached sensor data")
            devices = []
            connected_devices = mgr.adapter.get_connected_devices()
            for did, device in connected_devices.items():
                sensor_data = mgr.adapter.collect(did)
                if sensor_data and sensor_data.sensor_data:
                    sd = sensor_data.sensor_data
                    devices.append({
                        "id": did,
                        "name": device.name,
                        "type": SENSOR_TYPE_MAP.get(sd.sensor_type, "unknown"),
                        "status": "online" if device.online else "offline",
                        "value": sd.value,
                        "unit": UNIT_MAP.get(sd.sensor_type, ""),
                        "room": "Unknown",
                        "battery": 100,
                        "lastUpdate": "Just now",
                        "home_id": "",
                        "productName": "",
                        "photoUrl": "",
                        "parentId": "",
                    })
            return {"success": True, "data": devices}
    except Exception as e:
        logger.error("Failed to get devices: %s", e)
        return {"success": False, "data": [], "message": str(e)}


@router.get("/{device_id}", response_model=dict)
async def get_device(device_id: str, home_id: Optional[str] = Query(None)):
    try:
        mgr = get_manager()

        if mgr.api_client.is_authenticated:
            devices = await mgr.api_client.get_all_devices(home_id)
            device = next((d for d in devices if str(d.get("id", d.get("deviceId", ""))) == device_id), None)
            
            if not device:
                sensor_data_list = await mgr.api_client.get_sensor_data(home_id=home_id)
                sensor_data = next((s for s in sensor_data_list if s.did == device_id), None)
                
                if not sensor_data:
                    raise HTTPException(status_code=404, detail="Device not found")
                
                device_type = SENSOR_TYPE_MAP.get(sensor_data.sensor_type, "unknown")
                device_status = "online" if sensor_data.status != "offline" else "offline"
                
                return {
                    "success": True,
                    "data": {
                        "id": sensor_data.did,
                        "name": sensor_data.name,
                        "type": device_type,
                        "status": device_status,
                        "value": sensor_data.value,
                        "unit": sensor_data.unit or UNIT_MAP.get(sensor_data.sensor_type, ""),
                        "room": sensor_data.room_name or "Unknown",
                        "battery": 100,
                        "lastUpdate": sensor_data.timestamp.isoformat() if sensor_data.timestamp else "Just now",
                        "home_id": sensor_data.home_id,
                        "productId": "",
                        "productName": "",
                        "deriveMetadata": [],
                    },
                }
            
            device_type = device.get("type", "unknown")
            device_status = device.get("status", "offline")
            
            return {
                "success": True,
                "data": {
                    "id": device.get("id", device.get("deviceId", device_id)),
                    "name": device.get("name", device.get("deviceName", "Unknown")),
                    "deviceName": device.get("name", device.get("deviceName", "Unknown")),
                    "type": device_type,
                    "status": device_status,
                    "room": device.get("room", ""),
                    "home_id": device.get("home_id", ""),
                    "productId": device.get("productId", ""),
                    "productName": device.get("productName", ""),
                    "properties": device.get("properties", {}),
                    "deriveMetadata": device.get("deriveMetadata", []),
                    "photoUrl": device.get("photoUrl", ""),
                    "battery": device.get("battery", 100),
                    "lastUpdate": device.get("lastUpdate", ""),
                },
            }
        else:
            return {"success": False, "message": "Not authenticated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get device %s: %s", device_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=dict)
async def create_device(data: dict):
    return {"success": False, "message": "Creating devices via API is not supported. Please use the Heiman app."}


@router.put("/{device_id}", response_model=dict)
async def update_device(device_id: str, data: dict):
    return {"success": False, "message": "Updating devices via API is not supported. Please use the Heiman app."}


@router.delete("/{device_id}", response_model=dict)
async def delete_device(device_id: str):
    return {"success": False, "message": "Deleting devices via API is not supported. Please use the Heiman app."}


@router.post("/{device_id}/toggle", response_model=dict)
async def toggle_device(device_id: str):
    try:
        mgr = get_manager()
        
        success = await mgr.api_client.control_device(
            device_id=device_id,
            property_identifier="Switch",
            value=True,
        )
        
        if success:
            return {"success": True, "message": "Device toggled successfully"}
        else:
            return {"success": False, "message": "Failed to toggle device"}
    except Exception as e:
        logger.error("Failed to toggle device %s: %s", device_id, e)
        return {"success": False, "message": str(e)}


@router.post("/{device_id}/control", response_model=dict)
async def control_device(device_id: str, data: dict):
    """Generic device property control endpoint for panel plugins."""
    try:
        mgr = get_manager()

        property_identifier = data.get("property_identifier")
        value = data.get("value")

        if not property_identifier:
            return {"success": False, "message": "property_identifier is required"}

        success = await mgr.api_client.control_device(
            device_id=device_id,
            property_identifier=property_identifier,
            value=value,
        )

        if success:
            return {"success": True, "message": "Control command sent successfully"}
        else:
            return {"success": False, "message": "Failed to send control command"}
    except Exception as e:
        logger.error("Failed to control device %s: %s", device_id, e)
        return {"success": False, "message": str(e)}


@router.get("/{device_id}/panel", response_model=dict)
async def get_device_panel(device_id: str, home_id: Optional[str] = Query(None)):
    try:
        mgr = get_manager()

        if not mgr.api_client.is_authenticated:
            return {"success": False, "message": "Not authenticated"}

        devices = await mgr.api_client.get_all_devices(home_id)
        device = next((d for d in devices if str(d.get("id", d.get("deviceId", ""))) == device_id), None)

        if not device:
            return {"success": False, "message": "Device not found"}

        product_id = str(device.get("productId", ""))
        if not product_id:
            return {"success": False, "message": "Device has no productId"}

        panel_info = await mgr.api_client.get_device_panel(product_id)

        if not panel_info or not panel_info.get("panelUrl"):
            return {"success": False, "message": "No panel available for this device"}

        panel_url = panel_info.get("panelUrl")

        return {
            "success": True,
            "data": {
                "deviceId": device_id,
                "deviceName": device.get("deviceName", device.get("name", "")),
                "productId": product_id,
                "productName": device.get("productName", ""),
                "panelUrl": panel_url,
            },
        }
    except Exception as e:
        logger.error("Failed to get device panel for %s: %s", device_id, e)
        return {"success": False, "message": str(e)}


@router.post("/panel/session/close", response_model=dict)
async def close_panel_session(data: dict):
    try:
        mgr = get_manager()
        session_id = data.get("sessionId")
        
        if not session_id:
            return {"success": False, "message": "sessionId is required"}

        await mgr.api_client.close_panel_session(session_id)
        return {"success": True, "message": "Session closed successfully"}
    except Exception as e:
        logger.error("Failed to close panel session %s: %s", data.get("sessionId"), e)
        return {"success": False, "message": str(e)}