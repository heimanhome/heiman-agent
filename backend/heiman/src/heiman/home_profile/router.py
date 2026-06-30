"""home_profile controller — family profile CRUD + commit + render."""

import logging

from fastapi import APIRouter, Depends, Query

from heiman.home_profile.schema import (
    CandidateWriteBody,
    ImportBody,
    ProfileWriteBody,
    ReassignBody,
    ResetBody,
)
from heiman.manager import get_manager
from heiman.middleware import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/home-profile", tags=["HomeProfile"])

manager = get_manager()


@router.get("/entries", summary="List Entries", response_model=dict)
async def list_entries(
    target: str = Query("both", pattern="^(profile|candidates|both)$"),
    current_user: str = Depends(verify_token),
):
    data = manager.home_profile_service.list_entries(target)
    return {"success": True, "data": data}


@router.post("/candidates:write", summary="Candidate Write", response_model=dict)
async def candidate_write(body: CandidateWriteBody, current_user: str = Depends(verify_token)):
    results = manager.home_profile_service.candidate_write(body.ops)
    return {"success": True, "data": [r.model_dump() for r in results]}


@router.post("/profile:write", summary="Profile Write", response_model=dict)
async def profile_write(body: ProfileWriteBody, current_user: str = Depends(verify_token)):
    results = manager.home_profile_service.profile_write(body.ops, body.user_edit)
    return {"success": True, "data": [r.model_dump() for r in results]}


@router.post("/commit", summary="Commit", response_model=dict)
async def commit(current_user: str = Depends(verify_token)):
    data = manager.home_profile_service.commit()
    return {"success": True, "data": data}


@router.post("/subject:reassign", summary="Reassign Subject", response_model=dict)
async def reassign_subject(body: ReassignBody, current_user: str = Depends(verify_token)):
    data = manager.home_profile_service.reassign_subject(body.mappings)
    return {"success": True, "data": data}


@router.get("/rendered", summary="Get Rendered Profile", response_model=dict)
async def rendered(current_user: str = Depends(verify_token)):
    data = manager.home_profile_service.rendered()
    return {"success": True, "data": {"markdown": data}}


@router.post("/import", summary="Import Legacy Data", response_model=dict)
async def import_data(body: ImportBody, current_user: str = Depends(verify_token)):
    data = manager.home_profile_service.import_data(body)
    return {"success": True, "data": data}


@router.post("/reset", summary="Reset Profile (Full Overwrite + Commit)", response_model=dict)
async def reset(body: ResetBody, current_user: str = Depends(verify_token)):
    data = manager.home_profile_service.reset(body)
    return {"success": True, "data": data}
