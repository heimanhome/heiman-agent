"""admin 命令组：系统管理功能。"""

from __future__ import annotations

import json
import sys
import click

from heiman_cli.client import api_get, api_post, api_put
from heiman_cli.output import print_result


@click.group("admin")
def admin_group():
    """系统管理：状态 / 日志 / 统计 / 清理。"""


@admin_group.command("status")
@click.option("--pretty", is_flag=True)
def admin_status(pretty):
    """系统状态（传感器连接、数据库、规则引擎）。"""
    try:
        data = api_get("/api/admin/status")
        print_result(data, pretty)
    except Exception:
        # Fallback to /health endpoint
        data = api_get("/health")
        print_result(data, pretty)


@admin_group.command("info")
@click.option("--pretty", is_flag=True)
def admin_info(pretty):
    """获取系统信息。"""
    result = api_get("/")
    print_result(result, pretty)


@admin_group.command("debug")
@click.option("--pretty", is_flag=True)
def admin_debug(pretty):
    """获取 Debug 开关状态。"""
    data = api_get("/api/admin/debug")
    print_result(data, pretty)


@admin_group.command("debug-enable")
@click.option("--pretty", is_flag=True)
def admin_debug_enable(pretty):
    """开启 Debug 模式。"""
    data = api_post("/api/admin/debug", {"enabled": True})
    print_result(data, pretty)


@admin_group.command("debug-disable")
@click.option("--pretty", is_flag=True)
def admin_debug_disable(pretty):
    """关闭 Debug 模式。"""
    data = api_post("/api/admin/debug", {"enabled": False})
    print_result(data, pretty)


@admin_group.command("log-pack")
@click.option("--pretty", is_flag=True)
def admin_log_pack(pretty):
    """打包日志文件。"""
    try:
        data = api_post("/api/admin/debug/log-pack")
        print_result(data, pretty)
    except Exception as e:
        print(json.dumps({"code": 501, "message": f"log-pack endpoint error: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


@admin_group.command("omni-config")
@click.option("--pretty", is_flag=True)
def admin_omni_config(pretty):
    """获取 Omni 模型配置。"""
    data = api_get("/api/admin/omni-config")
    print_result(data, pretty)


@admin_group.command("omni-save")
@click.option("--label", required=True, help="档案名称")
@click.option("--base-url", required=True, help="Base URL")
@click.option("--model", required=True, help="模型名称")
@click.option("--api-key", help="API Key")
@click.option("--activate", is_flag=True, help="激活此配置")
@click.option("--pretty", is_flag=True)
def admin_omni_save(label, base_url, model, api_key, activate, pretty):
    """保存 Omni 模型配置。"""
    data = api_put("/api/admin/omni-config", {
        "label": label,
        "base_url": base_url,
        "model": model,
        "api_key": api_key or "",
        "activate": activate,
    })
    print_result(data, pretty)


@admin_group.command("omni-activate")
@click.option("--label", required=True, help="档案名称")
@click.option("--pretty", is_flag=True)
def admin_omni_activate(label, pretty):
    """激活 Omni 模型配置。"""
    data = api_post("/api/admin/omni-config/activate", {"label": label})
    print_result(data, pretty)


@admin_group.command("omni-delete")
@click.option("--label", required=True, help="档案名称")
@click.option("--pretty", is_flag=True)
def admin_omni_delete(label, pretty):
    """删除 Omni 模型配置。"""
    data = api_post("/api/admin/omni-config/delete", {"label": label})
    print_result(data, pretty)


@admin_group.command("omni-test")
@click.option("--model", help="模型名称")
@click.option("--base-url", help="Base URL")
@click.option("--api-key", help="API Key")
@click.option("--label", help="档案名称")
@click.option("--pretty", is_flag=True)
def admin_omni_test(model, base_url, api_key, label, pretty):
    """测试 Omni 配置连通性。"""
    payload = {}
    if model:
        payload["model"] = model
    if base_url:
        payload["base_url"] = base_url
    if api_key:
        payload["api_key"] = api_key
    if label:
        payload["label"] = label

    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        data = loop.run_until_complete(_test_omni_async(payload))
        print_result(data, pretty)
    except Exception as e:
        print(json.dumps({"code": 500, "message": f"test failed: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


async def _test_omni_async(payload: dict) -> dict:
    import httpx
    base_url = payload.get("base_url")
    api_key = payload.get("api_key")

    if not base_url or not api_key:
        return {"success": False, "code": "no_key", "message": "base_url and api_key required"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"bearer {api_key}"},
            )
    except Exception as e:
        return {"success": False, "code": "unreachable", "message": f"无法连接: {e}"}

    if r.status_code == 200:
        return {"success": True, "code": "ok", "message": "连接正常"}
    if r.status_code in (401, 403):
        return {"success": False, "code": "bad_key", "message": "API Key 无效或无权限"}
    return {"success": False, "code": "http_error", "message": f"HTTP {r.status_code}"}


@admin_group.command("stats")
@click.option(
    "--period",
    type=click.Choice(["today", "week", "month"]),
    default="today",
    show_default=True,
    help="统计周期",
)
@click.option("--pretty", is_flag=True)
def admin_stats(period, pretty):
    """传感器数据统计。"""
    try:
        data = api_get(f"/api/admin/stats?period={period}")
        print_result(data, pretty)
    except Exception as e:
        print(json.dumps({"code": 501, "message": f"stats endpoint not available: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


@admin_group.command("logs")
@click.option("--follow", "-f", is_flag=True, help="持续跟踪日志（类似 tail -f）")
@click.option("--lines", "-n", default=50, show_default=True, help="显示最后 N 行")
@click.option("--pretty", is_flag=True)
def admin_logs(follow, lines, pretty):
    """查看后端日志。"""
    from heiman_cli.commands.service import _find_latest_log, _log_dir

    log_dir = _log_dir()
    if not log_dir.exists():
        print(json.dumps({"error": f"log dir not found: {log_dir}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    latest = _find_latest_log()
    if not latest:
        print(json.dumps({"error": f"no backend log in {log_dir}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    import os

    cmd = ["tail", f"-n{lines}"]
    if follow:
        cmd.append("-f")
    cmd.append(str(latest))
    os.execvp("tail", cmd)


@admin_group.command("cleanup")
@click.option("--dry-run", is_flag=True, help="模拟清理，不实际删除")
@click.option("--older-than", default="30", help="删除早于指定天数的记录")
@click.option("--pretty", is_flag=True)
def admin_cleanup(dry_run, older_than, pretty):
    """清理历史数据。"""
    try:
        data = api_post("/api/admin/cleanup", {
            "dry_run": dry_run,
            "older_than_days": int(older_than),
        })
        print_result(data, pretty)
    except Exception as e:
        print(json.dumps({"code": 501, "message": f"cleanup endpoint not available: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


@admin_group.command("reset")
@click.option("--confirm", is_flag=True, help="确认重置（将删除所有数据）")
@click.option("--pretty", is_flag=True)
def admin_reset(confirm, pretty):
    """重置系统（删除所有数据）。"""
    if not confirm:
        print(json.dumps({
            "error": "请添加 --confirm 参数确认重置操作，此操作将删除所有数据",
            "hint": "heiman-cli admin reset --confirm",
        }, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    try:
        data = api_post("/api/admin/reset")
        print_result(data, pretty)
    except Exception as e:
        print(json.dumps({"code": 501, "message": f"reset endpoint not available: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
