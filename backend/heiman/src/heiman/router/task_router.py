"""Task SSOT Controller (`/tasks`)."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, Query

from heiman.database.task_repo import TaskLinkConflict
from heiman.manager import get_manager
from heiman.middleware import verify_token
from heiman.middleware.exceptions import ConflictException, ResourceNotFoundException
from heiman.schema.task import (
    TaskCreateRequest,
    TaskLinkAddRequest,
    TaskUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("", summary="Create Task", response_model=dict)
async def create_task(req: TaskCreateRequest, current_user: str = Depends(verify_token)):
    logger.info("Create task - User: %s, task_id: %s", current_user, req.task_id)
    try:
        get_manager().task_service.create_task(req)
    except TaskLinkConflict as e:
        raise ConflictException(str(e)) from e
    return {"success": True, "data": {"task_id": req.task_id}}


@router.get("", summary="List Tasks (dedupe view)", response_model=dict)
async def list_tasks(current_user: str = Depends(verify_token)):
    logger.info("List tasks - User: %s", current_user)
    views = get_manager().task_service.list_for_dedupe()
    return {"success": True, "data": [v.model_dump() for v in views]}


@router.get("/{task_id}", summary="Get Task", response_model=dict)
async def get_task(task_id: str, current_user: str = Depends(verify_token)):
    logger.info("Get task - User: %s, task_id: %s", current_user, task_id)
    view = get_manager().task_service.get_full_view(task_id)
    if view is None:
        raise ResourceNotFoundException(f"task_not_found: {task_id}")
    return {"success": True, "data": view.model_dump()}


@router.post("/{task_id}/links", summary="Add Link", response_model=dict)
async def add_link(
    task_id: str,
    req: TaskLinkAddRequest,
    current_user: str = Depends(verify_token),
):
    logger.info(
        "Add link - User: %s, task_id: %s, kind: %s", current_user, task_id, req.kind
    )
    try:
        get_manager().task_service.add_link(task_id, req)
    except TaskLinkConflict as e:
        raise ConflictException(str(e)) from e
    return {"success": True, "data": {"message": "Link added"}}


@router.patch(
    "/{task_id}", summary="Update Task Description", response_model=dict
)
async def update_task(
    task_id: str,
    req: TaskUpdateRequest,
    current_user: str = Depends(verify_token),
):
    logger.info("Update task - User: %s, task_id: %s", current_user, task_id)
    ok = get_manager().task_service.update_description(task_id, req)
    if not ok:
        raise ResourceNotFoundException(f"task_not_found: {task_id}")
    return {"success": True, "data": {"message": "Task updated"}}


@router.post(
    "/{task_id}/disable", summary="Disable Task", response_model=dict
)
async def disable_task(task_id: str, current_user: str = Depends(verify_token)):
    logger.info("Disable task - User: %s, task_id: %s", current_user, task_id)
    try:
        result = get_manager().task_service.disable_task(task_id)
    except TaskLinkConflict as e:
        raise ResourceNotFoundException(str(e)) from e
    return {"success": True, "data": result}


@router.post("/{task_id}/enable", summary="Enable Task", response_model=dict)
async def enable_task(task_id: str, current_user: str = Depends(verify_token)):
    logger.info("Enable task - User: %s, task_id: %s", current_user, task_id)
    try:
        result = get_manager().task_service.enable_task(task_id)
    except TaskLinkConflict as e:
        raise ResourceNotFoundException(str(e)) from e
    return {"success": True, "data": result}


@router.delete("/{task_id}", summary="Delete Task", response_model=dict)
async def delete_task(
    task_id: str,
    reason: str = Query(
        "completed",
        pattern="^(completed|expired|abandoned)$",
        description="terminate 原因（query 参数）",
    ),
    current_user: str = Depends(verify_token),
):
    logger.info(
        "Delete task - User: %s, task_id: %s, reason: %s",
        current_user,
        task_id,
        reason,
    )
    result = get_manager().task_service.delete_task(task_id, reason=reason)
    if result is None:
        raise ResourceNotFoundException(f"task_not_found: {task_id}")
    return {"success": True, "data": result}