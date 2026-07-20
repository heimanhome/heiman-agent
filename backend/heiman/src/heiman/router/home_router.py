import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from heiman.manager import get_manager
from heiman.database.person_repo import get_person_repo

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
        person_repo = get_person_repo()
        
        logger.info("[HOME API] Fetching home list from Heiman API")
        homes = await mgr.api_client.get_home_list()
        
        if not isinstance(homes, list):
            logger.warning("[HOME API] Heiman API returned non-list response: %s", homes)
            homes = []
        
        result = []
        total_members_saved = 0
        total_members_failed = 0
        
        for home in homes:
            home_id_val = home.get("id", home.get("homeId", ""))
            home_name_val = home.get("name", home.get("homeName", "Unnamed Home"))
            
            if not home_id_val:
                logger.warning("[HOME API] Skipping home without ID: %s", home)
                continue
            
            if home_id and home_id_val != home_id:
                continue
            
            home_members = []
            try:
                logger.info("[HOME API] Fetching members for home: %s (%s)", home_name_val, home_id_val)
                home_members_data = await mgr.api_client.get_home_members(home_id_val)
                
                if not isinstance(home_members_data, list):
                    logger.warning("[HOME API] Heiman API returned non-list members for home %s: %s", home_id_val, home_members_data)
                    home_members_data = []
                
                if home_members_data and len(home_members_data) > 0:
                    for member in home_members_data:
                        try:
                            member_id = str(member.get("id", member.get("userId", "")))
                            member_name = member.get("nickName", member.get("userName", member.get("name", "User")))
                            member_avatar = member.get("headImgUrl", member.get("avatar", ""))
                            member_user_id = str(member.get("userId", member.get("id", "")))
                            is_home_root_val = member.get("isHomeRoot", 0)
                            
                            if not member_name or member_name.strip() == "":
                                member_name = "User"
                            
                            if is_home_root_val == 1:
                                member_role_str = "owner"
                                role_type = 0
                                is_home_root = 1
                            else:
                                member_role_str = "member"
                                role_type = 2
                                is_home_root = 0
                            
                            if not member_avatar and member_name:
                                member_avatar = member_name[0].upper()
                            
                            home_members.append({
                                "id": member_id,
                                "name": member_name,
                                "role": member_role_str,
                                "avatar": member_avatar,
                            })
                            
                            try:
                                person_repo.upsert_by_user_id(
                                    user_id=member_user_id,
                                    name=member_name,
                                    role=member_role_str,
                                    home_id=home_id_val,
                                    home_name=home_name_val,
                                    head_img_url=member_avatar,
                                    is_home_root=is_home_root,
                                    role_type=role_type,
                                )
                                total_members_saved += 1
                            except Exception as db_e:
                                logger.error("[HOME API] Failed to save member %s for home %s: %s", member_user_id, home_id_val, db_e)
                                total_members_failed += 1
                        except Exception as member_e:
                            logger.error("[HOME API] Error processing member data for home %s: %s", home_id_val, member_e)
                            total_members_failed += 1
            except Exception as e:
                logger.error("[HOME API] Failed to get home members for %s: %s", home_id_val, e)
        
            result.append({
                "id": home_id_val,
                "name": home_name_val,
                "address": home.get("address", "") or "",
                "members": home_members,
                "devices": home.get("deviceCount", 0),
                "createdAt": home.get("createTime", ""),
                "roomCount": home.get("roomCount", 0),
                "memberCount": home.get("memberCount", len(home_members)),
            })
        
        logger.info("[HOME API] Get homes list - count=%d, members_saved=%d, members_failed=%d", 
                   len(result), total_members_saved, total_members_failed)
        
        return {
            "success": True,
            "data": result,
            "meta": {
                "homeCount": len(result),
                "totalMembersSaved": total_members_saved,
                "totalMembersFailed": total_members_failed,
            },
        }
    except Exception as e:
        logger.error("[HOME API] Failed to get homes: %s", e, exc_info=True)
        return {"success": False, "data": [], "message": str(e)}


@router.get("/{home_id}", response_model=dict)
async def get_home(home_id: str):
    try:
        mgr = get_manager()
        person_repo = get_person_repo()
        
        logger.info("[HOME API] Fetching home detail: %s", home_id)
        homes = await mgr.api_client.get_home_list()
        home = next((h for h in homes if h.get("id", h.get("homeId", "")) == home_id), None)
        
        if not home:
            logger.warning("[HOME API] Home not found: %s", home_id)
            raise HTTPException(status_code=404, detail="Home not found")
        
        home_name_val = home.get("name", home.get("homeName", "Unnamed Home"))
        
        devices = []
        try:
            devices = await mgr.api_client.get_devices(home_id)
            if not isinstance(devices, list):
                logger.warning("[HOME API] Heiman API returned non-list devices for home %s", home_id)
                devices = []
        except Exception as e:
            logger.error("[HOME API] Failed to get devices for home %s: %s", home_id, e)
        
        home_members_data = []
        try:
            home_members_data = await mgr.api_client.get_home_members(home_id)
            if not isinstance(home_members_data, list):
                logger.warning("[HOME API] Heiman API returned non-list members for home %s", home_id)
                home_members_data = []
        except Exception as e:
            logger.error("[HOME API] Failed to get home members for %s: %s", home_id, e)
        
        user_info = None
        try:
            user_info = await mgr.api_client.get_user_info()
        except Exception as e:
            logger.warning("[HOME API] Failed to get user info: %s", e)
        
        member_list = []
        members_saved = 0
        members_failed = 0
        
        if home_members_data and len(home_members_data) > 0:
            for member in home_members_data:
                try:
                    member_id = str(member.get("id", member.get("userId", "")))
                    member_name = member.get("nickName", member.get("userName", member.get("name", "User")))
                    member_avatar = member.get("headImgUrl", member.get("avatar", ""))
                    member_user_id = str(member.get("userId", member.get("id", "")))
                    is_home_root_val = member.get("isHomeRoot", 0)
                    
                    if not member_name or member_name.strip() == "":
                        member_name = "User"
                    
                    if is_home_root_val == 1:
                        member_role_str = "owner"
                        role_type = 0
                        is_home_root = 1
                    else:
                        member_role_str = "member"
                        role_type = 2
                        is_home_root = 0
                    
                    if not member_avatar and member_name:
                        member_avatar = member_name[0].upper()
                    
                    member_list.append({
                        "id": member_id,
                        "name": member_name,
                        "role": member_role_str,
                        "avatar": member_avatar,
                    })
                    
                    try:
                        person_repo.upsert_by_user_id(
                            user_id=member_user_id,
                            name=member_name,
                            role=member_role_str,
                            home_id=home_id,
                            home_name=home_name_val,
                            head_img_url=member_avatar,
                            is_home_root=is_home_root,
                            role_type=role_type,
                        )
                        members_saved += 1
                    except Exception as db_e:
                        logger.error("[HOME API] Failed to save member %s for home %s: %s", member_user_id, home_id, db_e)
                        members_failed += 1
                except Exception as member_e:
                    logger.error("[HOME API] Error processing member data for home %s: %s", home_id, member_e)
                    members_failed += 1
        elif user_info:
            try:
                user_id = str(user_info.get("id", user_info.get("userId", "")))
                user_name = user_info.get("nickName", user_info.get("nickname", user_info.get("userName", "User")))
                user_avatar = user_info.get("headImgUrl", user_info.get("avatar", "")) or (user_info.get("nickName", user_info.get("nickname", "U")) or "U")[0].upper()
                
                member_list.append({
                    "id": user_id,
                    "name": user_name,
                    "role": "owner",
                    "avatar": user_avatar,
                })
                
                try:
                    person_repo.upsert_by_user_id(
                        user_id=user_id,
                        name=user_name,
                        role="owner",
                        home_id=home_id,
                        home_name=home_name_val,
                        head_img_url=user_avatar,
                        is_home_root=1,
                        role_type=0,
                    )
                    members_saved += 1
                except Exception as db_e:
                    logger.error("[HOME API] Failed to save user %s for home %s: %s", user_id, home_id, db_e)
                    members_failed += 1
            except Exception as e:
                logger.error("[HOME API] Error processing user info for home %s: %s", home_id, e)
                members_failed += 1
        
        logger.info("[HOME API] Get home detail - home_id=%s, members=%d, saved=%d, failed=%d, devices=%d", 
                   home_id, len(member_list), members_saved, members_failed, len(devices))
        
        return {
            "success": True,
            "data": {
                "id": home_id,
                "name": home_name_val,
                "address": home.get("address", "") or "",
                "members": member_list,
                "devices": len(devices),
                "createdAt": home.get("createTime", ""),
                "roomCount": home.get("roomCount", 0),
                "memberCount": home.get("memberCount", len(member_list)),
                "deviceOnlineCnt": home.get("deviceOnlineCnt", 0),
                "rooms": home.get("roomList", []),
            },
            "meta": {
                "membersSaved": members_saved,
                "membersFailed": members_failed,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[HOME API] Failed to get home %s: %s", home_id, e, exc_info=True)
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