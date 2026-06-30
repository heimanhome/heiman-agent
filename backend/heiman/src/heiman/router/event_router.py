from typing import Annotated
import json
import logging
import asyncio

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from heiman.database.event_repo import EventRepo
from heiman.dependencies import get_event_repo
from heiman.manager import get_manager
from heiman.schema.sensor import SensorEvent, SensorEventLevel, SensorEventType

router = APIRouter(prefix="/events", tags=["events"])
logger = logging.getLogger(__name__)


def _format_sse(event: dict) -> str:
    """Format an event dict as SSE message."""
    lines = []
    if "event" in event:
        lines.append(f"event: {event['event']}")
    if "id" in event:
        lines.append(f"id: {event['id']}")
    data_str = json.dumps(event.get("data", {}), ensure_ascii=False)
    lines.append(f"data: {data_str}")
    lines.append("")
    return "\n".join(lines) + "\n"


@router.get("", response_model=dict)
async def get_events(
    event_type: Annotated[SensorEventType | None, Query()] = None,
    level: Annotated[SensorEventLevel | None, Query()] = None,
    did: Annotated[str | None, Query()] = None,
    acknowledged: Annotated[bool | None, Query()] = None,
    after: Annotated[str | None, Query()] = None,
    before: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    home_id: Annotated[str | None, Query()] = None,
    event_repo: EventRepo = Depends(get_event_repo),
):
    try:
        mgr = get_manager()
        
        if mgr.api_client.is_authenticated:
            api_events = await mgr.api_client.get_alarm_logs(home_id, limit)
            db_events = event_repo.query(
                event_type=event_type.value if event_type else None,
                level=level.value if level else None,
                did=did,
                acknowledged=acknowledged,
                after=after,
                before=before,
                limit=limit,
            )
            
            all_events = api_events + db_events
            
            if event_type:
                all_events = [e for e in all_events if e.get("event_type") == event_type.value]
            
            if level:
                all_events = [e for e in all_events if e.get("level") == level.value]
            
            if did:
                all_events = [e for e in all_events if e.get("did") == did]
            
            if acknowledged is not None:
                all_events = [e for e in all_events if e.get("acknowledged") == acknowledged]
            
            all_events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            return {"success": True, "data": all_events[:limit]}
        else:
            db_events = event_repo.query(
                event_type=event_type.value if event_type else None,
                level=level.value if level else None,
                did=did,
                acknowledged=acknowledged,
                after=after,
                before=before,
                limit=limit,
            )
            return {"success": True, "data": db_events}
    except Exception as e:
        logger.error("Failed to get events: %s", e)
        return {"success": False, "data": [], "message": str(e)}


@router.post("/batch/acknowledge", response_model=dict)
async def batch_acknowledge_events(
    body: dict,
    event_repo: EventRepo = Depends(get_event_repo),
):
    try:
        event_ids = body.get("event_ids", [])
        if not event_ids:
            return {"success": False, "message": "No event_ids provided"}
        count = event_repo.acknowledge_many(event_ids)
        return {"success": True, "acknowledged_count": count}
    except Exception as e:
        logger.error("Failed to batch acknowledge events: %s", e)
        return {"success": False, "message": str(e)}


@router.get("/{event_id}", response_model=dict)
async def get_event(
    event_id: str,
    event_repo: EventRepo = Depends(get_event_repo),
):
    try:
        event = event_repo.get_by_id(event_id)
        if event:
            return {"success": True, "data": event}
        return {"success": False, "message": "Event not found"}
    except Exception as e:
        logger.error("Failed to get event %s: %s", event_id, e)
        return {"success": False, "message": str(e)}


@router.post("/{event_id}/acknowledge", response_model=dict)
async def acknowledge_event(
    event_id: str,
    event_repo: EventRepo = Depends(get_event_repo),
):
    try:
        success = event_repo.acknowledge(event_id)
        return {"success": success, "event_id": event_id}
    except Exception as e:
        logger.error("Failed to acknowledge event %s: %s", event_id, e)
        return {"success": False, "message": str(e)}


@router.get("/stream")
async def events_stream(request: Request, token: str = Query("")):
    """SSE real-time event stream.

    Supports token authentication via query parameter for SSE clients
    that can't set Authorization headers.
    """
    from heiman.config import get_settings
    from heiman.service.event_bus import get_event_bus

    settings = get_settings()
    expected_token = settings.server.token

    if expected_token and token != expected_token:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    bus = get_event_bus()
    queue = await bus.subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield _format_sse(event)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            await bus.unsubscribe(queue)
            logger.debug("SSE connection closed")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/stream/status", response_model=dict)
async def stream_status(current_user: str = Depends(lambda: "admin")):
    """Get SSE stream status (subscriber count, etc)."""
    from heiman.service.event_bus import get_event_bus
    bus = get_event_bus()
    return {
        "success": True,
        "data": {
            "subscribers": bus.subscriber_count,
            "history_size": len(bus.get_history()),
        },
    }