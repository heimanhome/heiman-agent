"""Person controller — family member CRUD + sync from Heiman API."""

import logging

from fastapi import APIRouter, Depends, Query

from heiman.database.person_repo import UNSET
from heiman.manager import get_manager
from heiman.middleware import verify_token
from heiman.schema.person import PersonCreate, PersonUpdate


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/identity", tags=["Identity"])

manager = get_manager()


@router.get("/persons", summary="List Persons", response_model=dict)
async def list_persons(
    home_id: str | None = Query(default=None),
    current_user: str = Depends(verify_token),
):
    logger.info("List persons - user: %s, home_id: %s", current_user, home_id)
    persons = manager.person_service.list_persons(home_id=home_id)
    data = []
    for p in persons:
        d = p.model_dump()
        data.append(d)
    return {"success": True, "data": data}


@router.post("/persons", summary="Create Person", response_model=dict)
async def create_person(body: PersonCreate, current_user: str = Depends(verify_token)):
    logger.info("Create person - user: %s, name: %s", current_user, body.name)
    person_id = manager.person_service.create_person(body.name, body.role)
    return {"success": True, "data": {"person_id": person_id}}


@router.put("/persons/{person_id}", summary="Update Person", response_model=dict)
async def update_person(
    person_id: str, body: PersonUpdate, current_user: str = Depends(verify_token)
):
    logger.info("Update person - user: %s, id: %s", current_user, person_id)
    role_provided = "role" in body.model_fields_set
    role_arg = body.role if role_provided else UNSET
    manager.person_service.update_person(person_id, body.name, role_arg)
    try:
        manager.home_profile_service.commit()
    except Exception as e:
        logger.warning("级联刷新家庭档案失败 person_id=%s: %s", person_id, e)
    return {"success": True, "data": {"message": "Person updated"}}


@router.delete("/persons/{person_id}", summary="Delete Person", response_model=dict)
async def delete_person(person_id: str, current_user: str = Depends(verify_token)):
    logger.info("Delete person - user: %s, id: %s", current_user, person_id)
    manager.person_service.delete_person(person_id)
    try:
        manager.home_profile_service.remove_subject(person_id)
    except Exception as e:
        logger.warning("级联清家庭档案失败 person_id=%s: %s", person_id, e)
    return {"success": True, "data": {"message": "Person deleted"}}


@router.post("/persons/sync", summary="Sync Persons from Heiman", response_model=dict)
async def sync_persons(
    home_id: str = Query(...),
    current_user: str = Depends(verify_token),
):
    logger.info("Sync persons from Heiman - user: %s, home_id: %s", current_user, home_id)
    result = await manager.person_service.sync_from_heiman(home_id)
    return {"success": True, "data": result}
