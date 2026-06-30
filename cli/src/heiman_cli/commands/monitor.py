"""monitor 命令组：查看运行时监控状态。"""

from __future__ import annotations

import click

from heiman_cli.client import api_get
from heiman_cli.output import print_result


@click.group("monitor")
def monitor_group():
    """节点监控：查看运行时传感器和系统状态。"""


@monitor_group.command("status")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def monitor_status(pretty):
    """获取进程元数据（节点数量、运行时间、系统信息）。"""
    data = api_get("/api/monitor/status")
    print_result(data, pretty)


@monitor_group.command("nodes")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def monitor_nodes(pretty):
    """列出所有业务节点。"""
    data = api_get("/api/monitor/nodes")
    print_result(data, pretty)


@monitor_group.command("node")
@click.argument("name")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def monitor_node(name, pretty):
    """获取单个节点快照。"""
    data = api_get(f"/api/monitor/nodes/{name}")
    print_result(data, pretty)


@monitor_group.command("sensors")
@click.option("--pretty", is_flag=True, help="表格格式输出")
def monitor_sensors(pretty):
    """查询传感器运行状态。"""
    data = api_get("/api/sensors")

    if pretty:
        _print_sensor_table(data)
    else:
        online = sum(1 for s in data if s.get("status") != "OFFLINE")
        print_result({
            "total": len(data),
            "online": online,
            "offline": len(data) - online,
            "sensors": data,
        }, pretty)


@monitor_group.command("events")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def monitor_events(pretty):
    """监控事件状态。"""
    result = api_get("/api/events")
    unacknowledged = sum(1 for e in result if not e.get("acknowledged"))
    print_result({
        "total": len(result),
        "unacknowledged": unacknowledged,
        "events": result,
    }, pretty)


@monitor_group.command("resources")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def monitor_resources(pretty):
    """查询系统资源使用情况（CPU / 内存 / 磁盘等）。"""
    try:
        data = api_get("/api/monitor/resources")
        print_result(data, pretty)
    except Exception:
        data = _get_local_resources()
        print_result(data, pretty)


@monitor_group.command("memory")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def monitor_memory(pretty):
    """获取最新内存快照。"""
    data = api_get("/api/monitor/memory")
    print_result(data, pretty)


@monitor_group.command("memory-series")
@click.option("--window", type=click.Choice(["1h", "6h", "24h", "3d"]), default="1h", show_default=True, help="时间窗口")
@click.option("--bucket", type=click.Choice(["1m", "5m", "1h"]), default="1m", show_default=True, help="时间桶")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def monitor_memory_series(window, bucket, pretty):
    """获取内存时序数据。"""
    data = api_get(f"/api/monitor/memory/series?window={window}&bucket={bucket}")
    print_result(data, pretty)


@monitor_group.command("rules")
@click.option("--pretty", is_flag=True, help="JSON 格式化输出")
def monitor_rules(pretty):
    """监控规则引擎状态。"""
    result = api_get("/api/rules")
    active = sum(1 for r in result if r.get("enabled"))
    print_result({
        "total": len(result),
        "active": active,
        "inactive": len(result) - active,
        "rules": result,
    }, pretty)


def _get_local_resources() -> dict:
    import psutil

    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "cpu": {
            "percent": cpu_percent,
            "count": psutil.cpu_count(),
        },
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "percent": memory.percent,
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
        },
    }


def _print_sensor_table(data: list[dict]) -> None:
    if not data:
        print("No sensors registered.")
        return

    hdr = f"{'ID':<32} {'NAME':<20} {'TYPE':<12} {'STATUS':<10} {'VALUE':<16} LAST_UPDATE"
    print(hdr)
    print("-" * len(hdr))

    for s in data:
        sensor_id = s.get("id", "?")[:32]
        name = s.get("name", "?")[:20]
        sensor_type = s.get("type", "?")[:12]
        status = s.get("status", "?")[:10]
        value = _fmt_value(s)
        last_update = s.get("last_update", "")[:20]

        print(f"{sensor_id:<32} {name:<20} {sensor_type:<12} {status:<10} {value:<16} {last_update}")


def _fmt_value(sensor: dict) -> str:
    value = sensor.get("value")
    unit = sensor.get("unit", "")
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f} {unit}"
    return f"{value} {unit}".strip()