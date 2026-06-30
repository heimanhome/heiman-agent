"""Admin router - system status, debug controls, log packing."""

import logging
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, StrictBool

from heiman.admin import log_pack as _log_pack_mod
from heiman.config import get_settings
from heiman.database.rule_repo import RuleRepo
from heiman.manager import get_manager
from heiman.middleware.auth_middleware import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


class DebugOverrideBody(BaseModel):
    enabled: StrictBool


@router.get("/status", summary="System Status")
async def get_system_status(current_user: str = Depends(verify_token)):
    """Check system component status."""
    logger.info("Get system status API called - User: %s", current_user)

    mgr = get_manager()

    api_ok = not getattr(mgr, "_offline_mode", False)

    try:
        rule_repo = RuleRepo()
        total_rules = rule_repo.count_all()
        enabled_rules = rule_repo.count_enabled()
        sqlite_ok = True
    except Exception:
        total_rules = 0
        enabled_rules = 0
        sqlite_ok = False

    try:
        from heiman.service.observability_service import ObservabilityService
        obs = ObservabilityService()
        sensor_stats = obs.get_sensor_stats()
        total_sensors = sensor_stats.total_sensors
        online_sensors = sensor_stats.online_sensors
    except Exception:
        total_sensors = 0
        online_sensors = 0

    data = {
        "api": {"ok": api_ok},
        "sqlite": {"ok": sqlite_ok},
        "sensor": {
            "total_sensors": total_sensors,
            "online_sensors": online_sensors,
        },
        "rule_engine": {
            "total_rules": total_rules,
            "enabled_rules": enabled_rules,
        },
    }

    logger.info("System status retrieved: %s", data)
    return {"success": True, "data": data}


@router.get("/debug", summary="Debug switch status")
def get_debug_state(current_user: str = Depends(verify_token)):
    """Get current debug state."""
    settings = get_settings()
    debug_flag_path = settings.logging.log_dir.parent / ".debug_heiman"
    enabled = debug_flag_path.exists()
    return {"success": True, "data": {"enabled": enabled}}


@router.post("/debug", summary="Set debug switch")
def set_debug_override(
    body: DebugOverrideBody, current_user: str = Depends(verify_token)
):
    """Set debug mode on/off. Creates/deletes flag file for persistence."""
    settings = get_settings()
    debug_flag_path = settings.logging.log_dir.parent / ".debug_heiman"

    if body.enabled:
        debug_flag_path.touch()
        logger.info("Debug mode enabled by user: %s", current_user)
    else:
        if debug_flag_path.exists():
            debug_flag_path.unlink()
        logger.info("Debug mode disabled by user: %s", current_user)

    return {"success": True, "data": {"enabled": body.enabled}}


@router.post("/debug/log-pack", summary="Build log pack")
def post_log_pack(current_user: str = Depends(verify_token)):
    """Build a zip pack of logs and database for debugging."""
    try:
        result = _log_pack_mod.build_log_pack()
    except _log_pack_mod.LogPackSizeExceeded as e:
        raise HTTPException(status_code=422, detail=e.info)
    return {"success": True, "data": result}


class OmniConfigBody(BaseModel):
    label: str
    base_url: str
    model: str
    api_key: str | None = None
    original_label: str | None = None
    activate: bool = True


class OmniSelectBody(BaseModel):
    label: str


class OmniTestBody(BaseModel):
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    label: str | None = None


class OmniModelsBody(BaseModel):
    base_url: str
    api_key: str | None = None
    label: str | None = None


def _mask_api_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "…" + key[-2:]
    return f"{key[:3]}…{key[-4:]}"


def _key_by_label(label: str, provided: str | None) -> str:
    if provided and provided.strip():
        return provided.strip()
    if not label:
        return ""
    settings = get_settings()
    m = getattr(settings, "model", None)
    if m and hasattr(m, "omni") and m.omni.label == label and m.omni.api_key:
        return m.omni.api_key
    if m and hasattr(m, "omni_profiles"):
        for p in m.omni_profiles:
            if p.label == label and p.api_key:
                return p.api_key
    return ""


def _full_omni_payload() -> dict:
    settings = get_settings()
    m = getattr(settings, "model", None)
    if not m or not hasattr(m, "omni"):
        return {
            "active": {
                "label": "",
                "model": "",
                "base_url": "",
                "api_key_masked": "",
                "has_key": False,
            },
            "profiles": [],
        }
    active = m.omni
    profiles = getattr(m, "omni_profiles", [])
    return {
        "active": {
            "label": active.label,
            "model": active.model,
            "base_url": active.base_url,
            "api_key_masked": _mask_api_key(active.api_key),
            "has_key": bool(active.api_key),
        },
        "profiles": [
            {
                "label": p.label,
                "model": p.model,
                "base_url": p.base_url,
                "api_key_masked": _mask_api_key(p.api_key),
                "has_key": bool(p.api_key),
                "active": p.label == active.label,
            }
            for p in profiles
        ],
    }


@router.get("/omni-config", summary="Read omni config")
def get_omni_config(current_user: str = Depends(verify_token)):
    return {"success": True, "data": _full_omni_payload()}


@router.put("/omni-config", summary="Save omni config")
def put_omni_config(body: OmniConfigBody, current_user: str = Depends(verify_token)):
    from heiman.config.settings import update_shared_config

    label = body.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="档案名不能为空")
    base_url = body.base_url.strip()
    model = body.model.strip()
    orig = (body.original_label or "").strip()

    settings = get_settings()
    m = getattr(settings, "model", None)
    profiles = []
    if m and hasattr(m, "omni_profiles"):
        profiles = [
            {"label": p.label, "model": p.model, "base_url": p.base_url, "api_key": p.api_key}
            for p in m.omni_profiles
        ]

    target = next((p for p in profiles if p["label"] == orig), None) if orig else None
    clash = next((p for p in profiles if p["label"] == label and p is not target), None)
    if clash:
        raise HTTPException(status_code=409, detail=f"档案名「{label}」已存在")

    key = _key_by_label(orig or label, body.api_key)
    entry = {"label": label, "base_url": base_url, "model": model, "api_key": key}

    if target:
        profiles[profiles.index(target)] = entry
    else:
        profiles.append(entry)

    update_dict = {"omni_profiles": profiles}
    active_label = m.omni.label if m and hasattr(m, "omni") else ""

    if body.activate or active_label == (orig or label):
        update_dict["omni"] = entry

    update_shared_config(model=update_dict)
    return {"success": True, "data": _full_omni_payload()}


@router.post("/omni-config/activate", summary="Activate omni config")
def activate_omni_config(body: OmniSelectBody, current_user: str = Depends(verify_token)):
    from heiman.config.settings import update_shared_config

    label = body.label.strip()
    settings = get_settings()
    m = getattr(settings, "model", None)
    if m and hasattr(m, "omni_profiles"):
        for p in m.omni_profiles:
            if p.label == label:
                update_shared_config(
                    model={
                        "omni": {
                            "label": p.label,
                            "model": p.model,
                            "base_url": p.base_url,
                            "api_key": p.api_key,
                        }
                    }
                )
                return {"success": True, "data": _full_omni_payload()}
    raise HTTPException(status_code=404, detail="档案不存在")


@router.post("/omni-config/delete", summary="Delete omni config")
def delete_omni_config(body: OmniSelectBody, current_user: str = Depends(verify_token)):
    from heiman.config.settings import update_shared_config

    label = body.label.strip()
    settings = get_settings()
    m = getattr(settings, "model", None)
    profiles = []
    if m and hasattr(m, "omni_profiles"):
        profiles = [
            {"label": p.label, "model": p.model, "base_url": p.base_url, "api_key": p.api_key}
            for p in m.omni_profiles
            if p.label != label
        ]
    update_shared_config(model={"omni_profiles": profiles})
    return {"success": True, "data": _full_omni_payload()}


async def _probe_omni(model: str, base_url: str, api_key: str) -> dict:
    base_url = base_url.rstrip("/")
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"bearer {api_key}"},
            )
    except Exception as e:
        return {"ok": False, "code": "unreachable", "message": f"无法连接 Base URL（{type(e).__name__}）"}
    latency_ms = round((time.monotonic() - t0) * 1000)
    if r.status_code == 200:
        found = False
        try:
            ids = {m.get("id") for m in (r.json().get("data") or [])}
            found = model in ids
        except Exception:
            pass
        return {
            "ok": True,
            "code": "ok_model_found" if found else "ok",
            "status": 200,
            "latency_ms": latency_ms,
            "message": "连接正常，模型可用" if found else "连接正常",
        }
    if r.status_code in (401, 403):
        return {"ok": False, "code": "bad_key", "status": r.status_code, "message": "API Key 无效或无权限"}
    return {"ok": False, "code": "http_error", "status": r.status_code, "message": f"HTTP {r.status_code}"}


@router.post("/omni-config/test", summary="Test omni config connectivity")
async def test_omni_config(
    body: OmniTestBody, current_user: str = Depends(verify_token)
):
    settings = get_settings()
    m = getattr(settings, "model", None)
    omni = m.omni if m and hasattr(m, "omni") else None

    model = (body.model or (omni.model if omni else "")).strip()
    base_url = (body.base_url or (omni.base_url if omni else "")).strip()
    api_key = _key_by_label((body.label or (omni.label if omni else "")).strip(), body.api_key)

    if not api_key:
        return {
            "success": True,
            "data": {"ok": False, "code": "no_key", "message": "未配置 API Key"},
        }
    result = await _probe_omni(model, base_url, api_key)
    return {"success": True, "data": result}


async def _fetch_models(base_url: str, api_key: str) -> dict:
    base_url = base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{base_url}/models", headers={"Authorization": f"bearer {api_key}"}
            )
    except Exception as e:
        return {"ok": False, "code": "unreachable", "models": [], "message": f"无法连接 Base URL（{type(e).__name__}）"}
    if r.status_code == 200:
        try:
            ids = [m.get("id") for m in (r.json().get("data") or []) if m.get("id")]
        except Exception:
            ids = []
        return {"ok": True, "models": sorted(ids)}
    if r.status_code in (401, 403):
        return {"ok": False, "code": "bad_key", "models": [], "message": "API Key 无效或无权限"}
    return {
        "ok": False,
        "code": "http_error",
        "models": [],
        "message": f"HTTP {r.status_code}",
    }


@router.post("/omni-config/models", summary="List available models")
async def list_omni_models(
    body: OmniModelsBody, current_user: str = Depends(verify_token)
):
    base_url = body.base_url.strip()
    api_key = _key_by_label((body.label or "").strip(), body.api_key)
    if not api_key:
        return {
            "success": True,
            "data": {"ok": False, "code": "no_key", "models": [], "message": "未配置 API Key"},
        }
    return {"success": True, "data": await _fetch_models(base_url, api_key)}
