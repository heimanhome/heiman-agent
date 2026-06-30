import logging
from typing import Optional
from fastapi import APIRouter, Query

from heiman.manager import get_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("", response_model=dict)
async def get_rooms(
    home_id: Optional[str] = Query(None),
):
    try:
        mgr = get_manager()
        
        if not home_id:
            homes = await mgr.api_client.get_home_list()
            if homes:
                home_id = homes[0].get("id", homes[0].get("homeId"))
        
        if not home_id:
            return {"success": True, "data": []}
        
        rooms = await mgr.api_client.get_room_list(home_id)
        
        result = []
        for room in rooms:
            room_id = room.get("roomId", room.get("id", ""))
            room_name = room.get("roomName", room.get("name", ""))
            result.append({
                "id": str(room_id),
                "name": room_name,
                "homeId": home_id,
            })
        
        logger.info("[ROOM API] Get rooms - home_id=%s, count=%d", home_id, len(result))
        return {"success": True, "data": result}
    except Exception as e:
        logger.error("Failed to get rooms: %s", e)
        return {"success": False, "data": [], "message": str(e)}
