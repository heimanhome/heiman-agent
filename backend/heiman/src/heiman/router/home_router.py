import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from heiman.manager import get_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/homes", tags=["homes"])


class Member(BaseModel):
    id: str
    name: str
    role: str
    avatar: str


class HomeResponse(BaseModel):
    id: str
    name: str
    address: str
    members: List[Member]
    devices: int
    createdAt: str


class CreateHomeRequest(BaseModel):
    name: str
    address: Optional[str] = ""


class UpdateHomeRequest(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None


class AddMemberRequest(BaseModel):
    name: str
    role: Optional[str] = "member"


class UpdateMemberRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None


@router.get("", response_model=dict)
async def get_homes(home_id: Optional[str] = Query(None)):
    try:
        mgr = get_manager()
        homes = await mgr.api_client.get_home_list()
        
        result = []
        for home in homes:
            home_id_val = home.get("id", home.get("homeId", ""))
            if home_id and home_id_val != home_id:
                continue
            
            result.append({
                "id": home_id_val,
                "name": home.get("name", home.get("homeName", "Unnamed Home")),
                "address": home.get("address", "") or "",
                "members": [],
                "devices": home.get("deviceCount", 0),
                "createdAt": home.get("createTime", ""),
            })
        
        logger.info("[HOME API] Get homes list - count=%d", len(result))
        return {"success": True, "data": result}
    except Exception as e:
        logger.error("Failed to get homes: %s", e)
        return {"success": False, "data": [], "message": str(e)}


@router.get("/{home_id}", response_model=dict)
async def get_home(home_id: str):
    try:
        mgr = get_manager()
        homes = await mgr.api_client.get_home_list()
        home = next((h for h in homes if h.get("id", h.get("homeId", "")) == home_id), None)
        
        if not home:
            raise HTTPException(status_code=404, detail="Home not found")
        
        devices = await mgr.api_client.get_devices(home_id)
        
        home_members = await mgr.api_client.get_home_members(home_id)
        user_info = await mgr.api_client.get_user_info()
        member_list = []
        
        if home_members and len(home_members) > 0:
            for member in home_members:
                member_id = str(member.get("id", member.get("userId", "")))
                member_name = member.get("nickName", member.get("userName", member.get("name", "User")))
                member_role = member.get("role", "member")
                member_avatar = member.get("headImgUrl", member.get("avatar", ""))
                
                if not member_avatar and member_name:
                    member_avatar = member_name[0].upper()
                
                member_list.append({
                    "id": member_id,
                    "name": member_name,
                    "role": member_role if member_role in ["owner", "admin", "member"] else "member",
                    "avatar": member_avatar,
                })
        elif user_info:
            member_list.append({
                "id": str(user_info.get("id", user_info.get("userId", ""))),
                "name": user_info.get("nickName", user_info.get("nickname", user_info.get("userName", "User"))),
                "role": "owner",
                "avatar": user_info.get("headImgUrl", user_info.get("avatar", "")) or (user_info.get("nickName", user_info.get("nickname", "U")) or "U")[0].upper(),
            })
        
        logger.info("[HOME API] Get home detail - home_id=%s, members=%d", home_id, len(member_list))
        
        return {
            "success": True,
            "data": {
                "id": home_id,
                "name": home.get("name", home.get("homeName", "Unnamed Home")),
                "address": home.get("address", "") or "",
                "members": member_list,
                "devices": len(devices),
                "createdAt": home.get("createTime", ""),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get home %s: %s", home_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=dict)
async def create_home(data: CreateHomeRequest):
    return {"success": False, "message": "Creating homes via API is not supported. Please use the Heiman app."}


@router.put("/{home_id}", response_model=dict)
async def update_home(home_id: str, data: UpdateHomeRequest):
    return {"success": False, "message": "Updating homes via API is not supported. Please use the Heiman app."}


@router.delete("/{home_id}", response_model=dict)
async def delete_home(home_id: str):
    return {"success": False, "message": "Deleting homes via API is not supported. Please use the Heiman app."}


@router.post("/{home_id}/members", response_model=dict)
async def add_member(home_id: str, data: AddMemberRequest):
    return {"success": False, "message": "Adding members via API is not supported. Please use the Heiman app."}


@router.delete("/{home_id}/members/{member_id}", response_model=dict)
async def remove_member(home_id: str, member_id: str):
    return {"success": False, "message": "Removing members via API is not supported. Please use the Heiman app."}


@router.put("/{home_id}/members/{member_id}", response_model=dict)
async def update_member(home_id: str, member_id: str, data: UpdateMemberRequest):
    return {"success": False, "message": "Updating members via API is not supported. Please use the Heiman app."}