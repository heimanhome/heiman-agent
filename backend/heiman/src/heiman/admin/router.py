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


class HeimanConfigBody(BaseModel):
    label: str
    base_url: str
    model: str
    api_key: str | None = None
    original_label: str | None = None
    activate: bool = True


class HeimanSelectBody(BaseModel):
    label: str


class HeimanTestBody(BaseModel):
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    label: str | None = None


class HeimanModelsBody(BaseModel):
    base_url: str
    api_key: str | None = None
    label: str | None = None


def _mask_api_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "…" + key[-2:]
    return f"{key[:3]}…{key[-4:]}"


def _get_profile_attr(p, attr: str, default=""):
    if isinstance(p, dict):
        return p.get(attr, default)
    return getattr(p, attr, default)


def _key_by_label(label: str, provided: str | None) -> str:
    if provided and provided.strip():
        return provided.strip()
    if not label:
        return ""
    settings = get_settings()
    m = getattr(settings, "model", None)
    if m and hasattr(m, "heiman"):
        heiman_obj = m.heiman
        if _get_profile_attr(heiman_obj, "label") == label and _get_profile_attr(heiman_obj, "api_key"):
            return _get_profile_attr(heiman_obj, "api_key")
    if m and hasattr(m, "heiman_profiles"):
        for p in m.heiman_profiles:
            if _get_profile_attr(p, "label") == label and _get_profile_attr(p, "api_key"):
                return _get_profile_attr(p, "api_key")
    return ""


def _full_heiman_payload() -> dict:
    settings = get_settings()
    m = getattr(settings, "model", None)
    if not m or not hasattr(m, "heiman"):
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
    active = m.heiman
    profiles = getattr(m, "heiman_profiles", [])
    active_label = _get_profile_attr(active, "label")
    return {
        "active": {
            "label": active_label,
            "model": _get_profile_attr(active, "model"),
            "base_url": _get_profile_attr(active, "base_url"),
            "api_key_masked": _mask_api_key(_get_profile_attr(active, "api_key")),
            "has_key": bool(_get_profile_attr(active, "api_key")),
        },
        "profiles": [
            {
                "label": _get_profile_attr(p, "label"),
                "model": _get_profile_attr(p, "model"),
                "base_url": _get_profile_attr(p, "base_url"),
                "api_key_masked": _mask_api_key(_get_profile_attr(p, "api_key")),
                "has_key": bool(_get_profile_attr(p, "api_key")),
                "active": _get_profile_attr(p, "label") == active_label,
            }
            for p in profiles
        ],
    }


@router.get("/heiman-config", summary="Read heiman config")
def get_heiman_config(current_user: str = Depends(verify_token)):
    return {"success": True, "data": _full_heiman_payload()}


@router.put("/heiman-config", summary="Save heiman config")
def put_heiman_config(body: HeimanConfigBody, current_user: str = Depends(verify_token)):
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
    if m and hasattr(m, "heiman_profiles"):
        profiles = []
        for p in m.heiman_profiles:
            if isinstance(p, dict):
                profiles.append({
                    "label": p.get("label", ""),
                    "model": p.get("model", ""),
                    "base_url": p.get("base_url", ""),
                    "api_key": p.get("api_key", ""),
                })
            else:
                profiles.append({
                    "label": p.label,
                    "model": p.model,
                    "base_url": p.base_url,
                    "api_key": p.api_key,
                })

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

    update_dict = {"heiman_profiles": profiles}
    active_label = ""
    if m and hasattr(m, "heiman"):
        heiman_obj = m.heiman
        if isinstance(heiman_obj, dict):
            active_label = heiman_obj.get("label", "")
        else:
            active_label = heiman_obj.label

    if body.activate or active_label == (orig or label):
        update_dict["heiman"] = entry

    update_shared_config(model=update_dict)
    return {"success": True, "data": _full_heiman_payload()}


@router.post("/heiman-config/activate", summary="Activate heiman config")
def activate_heiman_config(body: HeimanSelectBody, current_user: str = Depends(verify_token)):
    from heiman.config.settings import update_shared_config

    label = body.label.strip()
    settings = get_settings()
    m = getattr(settings, "model", None)
    if m and hasattr(m, "heiman_profiles"):
        for p in m.heiman_profiles:
            if _get_profile_attr(p, "label") == label:
                update_shared_config(
                    model={
                        "heiman": {
                            "label": _get_profile_attr(p, "label"),
                            "model": _get_profile_attr(p, "model"),
                            "base_url": _get_profile_attr(p, "base_url"),
                            "api_key": _get_profile_attr(p, "api_key"),
                        }
                    }
                )
                return {"success": True, "data": _full_heiman_payload()}
    raise HTTPException(status_code=404, detail="档案不存在")


@router.post("/heiman-config/delete", summary="Delete heiman config")
def delete_heiman_config(body: HeimanSelectBody, current_user: str = Depends(verify_token)):
    from heiman.config.settings import update_shared_config

    label = body.label.strip()
    settings = get_settings()
    m = getattr(settings, "model", None)
    profiles = []
    if m and hasattr(m, "heiman_profiles"):
        profiles = [
            {"label": _get_profile_attr(p, "label"), "model": _get_profile_attr(p, "model"), "base_url": _get_profile_attr(p, "base_url"), "api_key": _get_profile_attr(p, "api_key")}
            for p in m.heiman_profiles
            if _get_profile_attr(p, "label") != label
        ]
    update_shared_config(model={"heiman_profiles": profiles})
    return {"success": True, "data": _full_heiman_payload()}


async def _probe_heiman(model: str, base_url: str, api_key: str) -> dict:
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


@router.post("/heiman-config/test", summary="Test heiman config connectivity")
async def test_heiman_config(
    body: HeimanTestBody, current_user: str = Depends(verify_token)
):
    settings = get_settings()
    m = getattr(settings, "model", None)
    heiman = m.heiman if m and hasattr(m, "heiman") else None

    model = (body.model or (heiman.model if heiman else "")).strip()
    base_url = (body.base_url or (heiman.base_url if heiman else "")).strip()
    api_key = _key_by_label((body.label or (heiman.label if heiman else "")).strip(), body.api_key)

    if not api_key:
        return {
            "success": True,
            "data": {"ok": False, "code": "no_key", "message": "未配置 API Key"},
        }
    result = await _probe_heiman(model, base_url, api_key)
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


@router.post("/heiman-config/models", summary="List available models")
async def list_heiman_models(
    body: HeimanModelsBody, current_user: str = Depends(verify_token)
):
    base_url = body.base_url.strip()
    api_key = _key_by_label((body.label or "").strip(), body.api_key)
    if not api_key:
        return {
            "success": True,
            "data": {"ok": False, "code": "no_key", "models": [], "message": "未配置 API Key"},
        }
    return {"success": True, "data": await _fetch_models(base_url, api_key)}
