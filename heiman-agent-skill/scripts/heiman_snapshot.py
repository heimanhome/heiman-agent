#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""heiman_snapshot.py — 拉取海曼设备数据并产出结构化分析快照。

把阈值判定、严重级别映射、安全评分等易错逻辑固化在脚本里，
模型只需基于快照写结论，不需要每次手算。

用法
----
  python scripts/heiman_snapshot.py                 # 输出 JSON 快照（中文文案）
  python scripts/heiman_snapshot.py --lang en-US    # 输出英文文案的快照
  python scripts/heiman_snapshot.py --out snap.json # 落盘
  python scripts/heiman_snapshot.py --hours 168     # 附带 7 天历史趋势

语言说明
--------
`--lang` 只影响快照里给人看的文案：`type_label`、`readings` 的键名、
`issues[].message`、`comfort.*_verdict`、`error`。
机器可用字段（`level`、`status`、`device_id`、`metrics`、各类计数）在任何语言下都不变。

调用方应先按用户提问语言传入 `--lang`，可避免模型在英文回答中夹带中文文案；
快照自身也会回带 `lang` 字段，供下游确认渲染语言。

退出码：0 成功 / 2 服务不可达 / 3 业务错误
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

HERE = Path(__file__).resolve().parent
CTL = HERE / "heiman_ctl.py"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 1912

# 阈值（口径对齐后端源码，来源见 references/thresholds.md）
# CO：backend/heiman/src/heiman/ai/alert_analyzer.py  ->  _CO_DANGER / _CO_HIGH
CO_DANGER = 400   # >= 400 ppm -> critical
CO_HIGH = 100     # >= 100 ppm -> warning（对应后端 high）
# 历史查询：后端 /api/sensors/{did}/history 只接受 start_time/end_time/limit，**没有 hours 参数**
# （router/sensor_router.py -> get_sensor_history）。窗口由 start_time 表达。
HISTORY_LIMIT = 1000   # 后端 limit 上限 le=1000，默认 100
# 电量：后端 anomaly_detector.battery_low_threshold = 20 / alert_analyzer 离线归因 battery <= 10
BATTERY_LOW = 20
BATTERY_CRITICAL = 10
TEMP_LOW, TEMP_HIGH = 18, 26
TEMP_EXTREME_LOW, TEMP_EXTREME_HIGH = 10, 32
HUM_LOW, HUM_HIGH = 40, 60
HUM_EXTREME_LOW, HUM_EXTREME_HIGH = 30, 75
# 离线：后端 anomaly_detector.offline_threshold_minutes = 60
# 注：脚本的离线判定实际取自后端 status 字段，此常量当前未被引用，仅用于口径对齐
OFFLINE_THRESHOLD_MINUTES = 60

# --------------------------------------------------------------------------
# 文案（仅影响输出措辞，不影响判定逻辑）
# --------------------------------------------------------------------------

I18N: dict[str, dict[str, str]] = {
    "zh-CN": {
        "type_smoke": "烟雾报警器",
        "type_co": "一氧化碳报警器",
        "type_temperature": "温湿度传感器",
        "type_plug": "门磁探测器",
        "type_water": "水浸传感器",
        "type_motion": "人体移动传感器",
        "type_switch": "开关",
        "type_gateway": "网关",
        "state_smoke": "烟雾",
        "state_water": "水浸",
        "state_gas": "燃气",
        "state_contact": "门磁",
        "state_motion": "移动",
        "v_normal": "正常",
        "v_alarm": "报警",
        "v_fault": "故障",
        "v_closed": "关门",
        "v_open": "开门",
        "v_none": "无",
        "v_moving": "有移动",
        "v_unknown": "未知({raw})",
        "key_temperature": "温度",
        "key_humidity": "湿度",
        "key_co": "CO",
        "key_note": "备注",
        "room_unassigned": "未分配房间",
        "issue_state": "{label}：{text}",
        "issue_co_critical": "CO 浓度 {value:g} ppm 达到 {limit} ppm",
        "issue_co_warning": "CO 浓度 {value:g} ppm 偏高，建议通风",
        "issue_temperature_extreme": "温度 {value:g} °C 处于极端区间",
        "issue_humidity_extreme": "湿度 {value:g} % 超出正常区间",
        "issue_tamper": "防拆告警",
        "issue_battery_critical": "电量仅 {value:g}%，需立即更换",
        "issue_battery_low": "电量偏低 {value:g}%，建议更换",
        "issue_offline": "设备离线，建议检查电源与网络",
        "note_contact_false_alarm": "status=alarm 来自 value 枚举，contactState=0 表示已关门，非真实告警",
        "comfort_within": "{label} {value:.1f}{unit}，处于舒适区间",
        "comfort_deviate": "{label} {value:.1f}{unit}，偏离舒适区间 {low}–{high}{unit}",
        "err_unreachable_http": "服务不可达：HTTP {code}",
        "err_unreachable": "服务不可达：{name}: {detail}",
    },
    "en-US": {
        "type_smoke": "Smoke alarm",
        "type_co": "Carbon monoxide alarm",
        "type_temperature": "Temperature & humidity sensor",
        "type_plug": "Door contact sensor",
        "type_water": "Water leak sensor",
        "type_motion": "Motion sensor",
        "type_switch": "Switch",
        "type_gateway": "Gateway",
        "state_smoke": "Smoke",
        "state_water": "Water leak",
        "state_gas": "Gas",
        "state_contact": "Contact",
        "state_motion": "Motion",
        "v_normal": "normal",
        "v_alarm": "alarm",
        "v_fault": "fault",
        "v_closed": "closed",
        "v_open": "open",
        "v_none": "none",
        "v_moving": "motion detected",
        "v_unknown": "unknown ({raw})",
        "key_temperature": "temperature",
        "key_humidity": "humidity",
        "key_co": "co",
        "key_note": "note",
        "room_unassigned": "Unassigned",
        "issue_state": "{label}: {text}",
        "issue_co_critical": "CO level {value:g} ppm reached {limit} ppm",
        "issue_co_warning": "CO level {value:g} ppm is elevated, ventilate the room",
        "issue_temperature_extreme": "Temperature {value:g} °C is in the extreme range",
        "issue_humidity_extreme": "Humidity {value:g} % is outside the normal range",
        "issue_tamper": "Tamper alarm",
        "issue_battery_critical": "Battery only {value:g}%, replace immediately",
        "issue_battery_low": "Battery low at {value:g}%, replacement recommended",
        "issue_offline": "Device offline, check power supply and network",
        "note_contact_false_alarm": "status=alarm comes from the value enum; contactState=0 means the door is closed, so this is not a real alarm",
        "comfort_within": "{label} {value:.1f}{unit}, within the comfort range",
        "comfort_deviate": "{label} {value:.1f}{unit}, outside the comfort range {low}–{high}{unit}",
        "err_unreachable_http": "Service unreachable: HTTP {code}",
        "err_unreachable": "Service unreachable: {name}: {detail}",
    },
}

LANG = "zh-CN"
SUPPORTED_LANGS = tuple(I18N.keys())


def t(key: str, **kw) -> str:
    """取当前语言的文案；缺失时回退中文，再回退 key 本身。"""
    table = I18N.get(LANG) or I18N["zh-CN"]
    text = table.get(key) or I18N["zh-CN"].get(key, key)
    return text.format(**kw) if kw else text


TYPE_KEYS = {
    "smoke": "type_smoke",
    "co": "type_co",
    "temperature": "type_temperature",
    "plug": "type_plug",
    "water": "type_water",
    "motion": "type_motion",
    "switch": "type_switch",
    "gateway": "type_gateway",
}

# 各类型的状态位：(字段, 标签文案 key, {值: (值文案 key, 级别)})
STATE_BITS = {
    "smoke": [("smokeState", "state_smoke", {"0": ("v_normal", "info"), "1": ("v_alarm", "critical"), "2": ("v_fault", "warning")})],
    "co": [("gasState", "state_gas", {"0": ("v_normal", "info"), "1": ("v_alarm", "critical"), "2": ("v_fault", "warning")})],
    "water": [("waterState", "state_water", {"0": ("v_normal", "info"), "1": ("v_alarm", "critical"), "2": ("v_fault", "warning")})],
    "plug": [("contactState", "state_contact", {"0": ("v_closed", "info"), "1": ("v_open", "warning")})],
    "motion": [("motionState", "state_motion", {"0": ("v_none", "info"), "1": ("v_moving", "info")})],
}
SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}


# --------------------------------------------------------------------------
# 取数
# --------------------------------------------------------------------------


def resolve_endpoint() -> tuple[str, str]:
    """返回 (base_url, token)，复用 heiman_ctl 的配置解析。"""
    sys.path.insert(0, str(HERE))
    try:
        import heiman_ctl as ctl  # type: ignore

        project = ctl.resolve_project(None)
        host, port = ctl.runtime_settings(project)
        token = ctl.server_token(project)
        return f"http://{host}:{port}", token
    except Exception:  # noqa: BLE001
        host = os.environ.get("SERVER_HOST", DEFAULT_HOST)
        port = os.environ.get("SERVER_PORT", str(DEFAULT_PORT))
        token = os.environ.get("SERVER_TOKEN", "heiman_test_token_123")
        return f"http://{host}:{port}", token


def get(base: str, token: str, path: str):
    """请求本地后端。

    始终绕过 http_proxy：本机设置了全局代理时，代理会连 127.0.0.1 一起转发
    并返回 502，会让原本健康的服务被误判为不可用。
    """

    req = urllib.request.Request(base + path, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def safe_get(base: str, token: str, path: str, default=None):
    try:
        payload = get(base, token, path)
    except Exception:  # noqa: BLE001
        return default
    if isinstance(payload, dict):
        if payload.get("success") is False:
            return default
        return payload.get("data", payload)
    return payload


# --------------------------------------------------------------------------
# 归一化与判定
# --------------------------------------------------------------------------


def num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def normalize_room(s: dict) -> str:
    room = s.get("room_name")
    if room in (None, "", "None", "null"):
        return t("room_unassigned")
    return str(room)


def has_cjk(text: str) -> bool:
    """是否含汉字（用于英文模式下给云端中文设备名拼英文注释）。"""
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def has_cjk(text: str) -> bool:
    """是否含汉字（用于英文模式下给云端中文设备名拼英文注释）。"""
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def evaluate_sensor(s: dict) -> dict:
    """把一条传感器记录转成带判定结果的条目。

    `readings` 用当前语言的标签做键，便于直接阅读；
    `metrics` 用稳定的英文键保存数值，供程序消费（环境汇总、趋势、下游集成）。
    """
    stype = s.get("sensor_type") or "unknown"
    issues: list[dict] = []
    readings: dict = {}
    metrics: dict = {}

    # 状态位判定
    for field, label_key, mapping in STATE_BITS.get(stype, []):
        raw = s.get(field)
        if raw is None:
            continue
        key = str(int(raw)) if isinstance(raw, (int, float)) else str(raw)
        vkey, sev = mapping.get(key, (None, "info"))
        text = t(vkey) if vkey else t("v_unknown", raw=raw)
        label = t(label_key)
        readings[label] = text
        metrics[field] = num(raw) if num(raw) is not None else raw
        if sev != "info":
            issues.append({"level": sev, "type": field, "message": t("issue_state", label=label, text=text)})

    # 一氧化碳浓度：浓度在 `value`（unit=ppm）；`gasState` 是状态位，已在上面按 STATE_BITS 判定。
    # 后端依据：classifier/event_classifier.py 用 `sensor_data.value` 作为 CO 浓度；
    #          database/sensor_repo.py 中 gasState 的 unit 为空 => 状态位，不是浓度。
    # （注意 0 是合法读数，不能用 `or` 链）
    if stype == "co":
        co = num(s.get("value"))
        if co is not None:
            unit = s.get("unit") or "ppm"
            readings[t("key_co")] = f"{co:g} {unit}"
            metrics["co"] = co
            if co >= CO_DANGER:
                issues.append({"level": "critical", "type": "co_ppm", "message": t("issue_co_critical", value=co, limit=CO_DANGER)})
            elif co >= CO_HIGH:
                issues.append({"level": "warning", "type": "co_ppm", "message": t("issue_co_warning", value=co)})

    # 温湿度
    temp = num(s.get("temperature"))
    hum = num(s.get("humidity"))
    if temp is not None:
        readings[t("key_temperature")] = f"{temp:g} °C"
        metrics["temperature"] = temp
        if temp < TEMP_EXTREME_LOW or temp > TEMP_EXTREME_HIGH:
            issues.append({"level": "warning", "type": "temperature", "message": t("issue_temperature_extreme", value=temp)})
    if hum is not None:
        readings[t("key_humidity")] = f"{hum:g} %"
        metrics["humidity"] = hum
        if hum > HUM_EXTREME_HIGH or hum < HUM_EXTREME_LOW:
            issues.append({"level": "warning", "type": "humidity", "message": t("issue_humidity_extreme", value=hum)})

    # 防拆
    tamper = num(s.get("tamperState"))
    if tamper == 1:
        issues.append({"level": "warning", "type": "tamperState", "message": t("issue_tamper")})

    # 电量（网关 -1 表示市电）
    battery = num(s.get("battery"))
    if battery is not None and battery >= 0:
        metrics["battery"] = battery
        if battery < BATTERY_CRITICAL:
            issues.append({"level": "critical", "type": "battery", "message": t("issue_battery_critical", value=battery)})
        elif battery < BATTERY_LOW:
            issues.append({"level": "warning", "type": "battery", "message": t("issue_battery_low", value=battery)})

    # 离线
    status = str(s.get("status") or "").lower()
    if status == "offline":
        issues.append({"level": "warning", "type": "offline", "message": t("issue_offline")})

    # 门磁特例：status=alarm 但 contactState=0 时降级为提示
    if stype == "plug" and status == "alarm" and num(s.get("contactState")) == 0:
        issues = [i for i in issues if i["type"] != "contactState"]
        readings[t("key_note")] = t("note_contact_false_alarm")

    level = "info"
    for i in issues:
        if SEVERITY_RANK[i["level"]] > SEVERITY_RANK[level]:
            level = i["level"]

    type_label = t(TYPE_KEYS[stype]) if stype in TYPE_KEYS else stype
    dev_name = s.get("name") or ""
    # 英文模式下直接给出拼好注释的展示名：模型照抄即可，避免表格里出现裸中文设备名
    if LANG.startswith("en") and has_cjk(dev_name):
        name_display = f"{dev_name} ({type_label})"
    else:
        name_display = dev_name

    return {
        "device_id": s.get("did"),
        "name": s.get("name"),
        "name_display": name_display,
        "type": stype,
        "type_label": type_label,
        "room": normalize_room(s),
        "status": status or None,
        "battery": battery,
        "readings": readings,
        "metrics": metrics,
        "issues": issues,
        "level": level,
        "timestamp": s.get("timestamp"),
    }


def comfort_summary(entries: list[dict]) -> dict:
    """只统计在线设备，避免离线设备的陈旧读数污染环境评估。"""
    live = [e for e in entries if e["status"] != "offline"]
    temps = [e["metrics"].get("temperature") for e in live]
    hums = [e["metrics"].get("humidity") for e in live]
    temps = [v for v in temps if v is not None]
    hums = [v for v in hums if v is not None]

    def verdict(value, low, high, label_key, unit):
        if value is None:
            return None
        label = t(label_key)
        if low <= value <= high:
            return t("comfort_within", label=label, value=value, unit=unit)
        return t("comfort_deviate", label=label, value=value, unit=unit, low=low, high=high)

    avg_temp = sum(temps) / len(temps) if temps else None
    avg_hum = sum(hums) / len(hums) if hums else None

    return {
        "temperature_avg": round(avg_temp, 1) if avg_temp is not None else None,
        "humidity_avg": round(avg_hum, 1) if avg_hum is not None else None,
        "sample_count": len(live),
        "temperature_verdict": verdict(avg_temp, TEMP_LOW, TEMP_HIGH, "key_temperature", "°C"),
        "humidity_verdict": verdict(avg_hum, HUM_LOW, HUM_HIGH, "key_humidity", "%"),
    }


def safety_score(entries: list[dict], events: list[dict]) -> tuple[int, dict]:
    score = 100
    alarm_penalty = 0
    for ev in events or []:
        lv = str(ev.get("level") or ev.get("severity") or "").upper()
        if lv in ("CRITICAL", "EMERGENCY"):
            alarm_penalty -= 20
        elif lv == "HIGH":
            alarm_penalty -= 10
        elif lv in ("MEDIUM", "WARNING"):
            alarm_penalty -= 5

    monitored = [e for e in entries if e["type"] != "gateway"]
    total = len(monitored) or 1
    online = sum(1 for e in monitored if e["status"] != "offline")
    online_penalty = -10 if online / total < 0.9 else 0

    low_batt = sum(1 for e in entries if e["battery"] is not None and 0 <= e["battery"] < BATTERY_LOW)
    battery_penalty = -5 * low_batt

    score += alarm_penalty + online_penalty + battery_penalty
    score = max(0, min(100, score))
    return score, {
        "alarm_penalty": alarm_penalty,
        "online_penalty": online_penalty,
        "battery_penalty": battery_penalty,
        "online_rate": round(online / total, 3),
    }


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------


def build_snapshot(hours: int | None) -> dict:
    base, token = resolve_endpoint()

    try:
        get(base, token, "/health")
    except urllib.error.HTTPError as e:
        if e.code != 503:
            return {"ok": False, "error": t("err_unreachable_http", code=e.code), "base_url": base}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": t("err_unreachable", name=type(e).__name__, detail=e), "base_url": base}

    raw_sensors = safe_get(base, token, "/api/sensors", []) or []
    raw_devices = safe_get(base, token, "/api/devices", []) or []
    homes = safe_get(base, token, "/api/homes", []) or []
    events = safe_get(base, token, "/api/events", []) or []
    rooms = safe_get(base, token, "/api/rooms", []) or []
    persons = safe_get(base, token, "/api/identity/persons", []) or []

    if isinstance(raw_sensors, dict):
        raw_sensors = raw_sensors.get("data", [])
    if isinstance(raw_devices, dict):
        raw_devices = raw_devices.get("data", [])

    entries = [evaluate_sensor(s) for s in raw_sensors]
    entries.sort(key=lambda e: (-SEVERITY_RANK[e["level"]], e["type"], e["name"] or ""))

    score, breakdown = safety_score(entries, events)

    alerts = [
        {"device": e["name"], "type": e["type_label"], "room": e["room"], "level": e["level"], **i}
        for e in entries
        for i in e["issues"]
        if i["level"] != "info"
    ]

    home = homes[0] if homes else {}
    snapshot = {
        "ok": True,
        "lang": LANG,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "base_url": base,
        "home": {
            "id": home.get("id"),
            "name": home.get("name"),
            "room_count": home.get("roomCount"),
            "member_count": home.get("memberCount"),
        },
        "rooms": [r.get("name") for r in rooms],
        "members": [{"name": p.get("name"), "role": p.get("role")} for p in persons],
        "device_count": {
            "total": len(entries),
            "monitored": sum(1 for e in entries if e["type"] != "gateway"),
            "online": sum(1 for e in entries if e["type"] != "gateway" and e["status"] != "offline"),
            "offline": [e["name"] for e in entries if e["status"] == "offline"],
            "gateway": [e["name"] for e in entries if e["type"] == "gateway"],
        },
        "safety_score": score,
        "score_breakdown": breakdown,
        "event_count": len(events),
        "alerts": alerts,
        "critical_count": sum(1 for a in alerts if a["level"] == "critical"),
        "warning_count": sum(1 for a in alerts if a["level"] == "warning"),
        "comfort": comfort_summary(entries),
        "sensors": entries,
    }

    if LANG.startswith("en"):
        # 把渲染约束注入工具输出本身：模型每次取数都会看到，不依赖会话是否重新加载了 SKILL.md
        snapshot["rendering_hint"] = (
            "Output rule: every Chinese device/room name must be rendered as "
            "'original name (English gloss)' - including EVERY table cell. "
            "Use each sensor's name_display field as-is; never leave a bare Chinese "
            "name alone in a table cell."
        )

    if hours:
        # 后端 /history 没有 hours 参数：用 start_time 表达回溯窗口（与后端自带 CLI
        # commands/sensor.py 同款写法），并把 limit 提到后端上限，避免只拿到默认 100 条。
        start_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        query = urlencode({"start_time": start_time, "limit": HISTORY_LIMIT})
        histories = {}
        for e in entries:
            did = e.get("device_id")
            if not did:
                continue
            hist = safe_get(base, token, f"/api/sensors/{did}/history?{query}")
            if hist:
                histories[e["name"]] = hist
        snapshot["history"] = histories

    return snapshot


def main() -> int:
    global LANG

    ap = argparse.ArgumentParser(description="生成海曼设备分析快照 / Generate Heiman device analysis snapshot")
    ap.add_argument(
        "--hours",
        type=int,
        help="附带历史数据的回溯小时数（脚本内部换算为 start_time）/ history lookback in hours",
    )
    ap.add_argument("--out", help="写入文件路径 / output file path")
    ap.add_argument(
        "--lang",
        default="zh-CN",
        choices=list(SUPPORTED_LANGS),
        help="快照文案语言，需与用户提问语言一致 / snapshot text language",
    )
    args = ap.parse_args()

    LANG = args.lang

    snap = build_snapshot(args.hours)
    text = json.dumps(snap, ensure_ascii=False, indent=2)

    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(json.dumps({"ok": snap.get("ok"), "written": args.out}, ensure_ascii=False, indent=2))
    else:
        print(text)

    return 0 if snap.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
