"""``heiman-cli debug`` 子命令组：调试工具。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from heiman_cli.client import api_get, api_post
from heiman_cli.config import heiman_home, load_config
from heiman_cli.output import print_result


@click.group("debug")
def debug_group():
    """调试工具：ping / logs / config / routes / env / trace。"""


@debug_group.command("ping")
@click.option("--pretty", is_flag=True)
def debug_ping(pretty):
    """测试后端连接。"""
    result = api_get("/health")
    print_result(result, pretty)


@debug_group.command("logs")
@click.option("--follow", "-f", is_flag=True, help="持续跟踪日志")
@click.option("--lines", "-n", default=50, show_default=True, help="显示最后 N 行")
def debug_logs(follow, lines):
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


@debug_group.command("config")
@click.option("--pretty", is_flag=True)
def debug_config(pretty):
    """打印当前配置（含环境变量覆盖）。"""
    cfg = load_config()
    print_result(cfg, pretty)


@debug_group.command("routes")
@click.option("--pretty", is_flag=True)
def debug_routes(pretty):
    """列出所有 API 路由。"""
    try:
        result = api_get("/api/debug/routes")
        print_result(result, pretty)
    except Exception as e:
        print(json.dumps({"error": f"routes endpoint not available: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


@debug_group.command("env")
@click.option("--pretty", is_flag=True)
def debug_env(pretty):
    """打印环境变量（过滤 HEIMAN_ 前缀）。"""
    env_vars = {k: v for k, v in os.environ.items() if k.startswith("HEIMAN_")}
    print_result({"env": env_vars}, pretty)


@debug_group.command("trace")
@click.option("--pretty", is_flag=True)
def debug_trace(pretty):
    """触发后端追踪。"""
    try:
        result = api_post("/api/debug/trace")
        print_result(result, pretty)
    except Exception as e:
        print(json.dumps({"error": f"trace endpoint not available: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


@debug_group.command("cache")
@click.option("--clear", is_flag=True, help="清除缓存")
@click.option("--pretty", is_flag=True)
def debug_cache(clear, pretty):
    """管理缓存。"""
    if clear:
        try:
            result = api_post("/api/debug/cache/clear")
            print_result(result, pretty)
        except Exception as e:
            print(json.dumps({"error": f"cache clear failed: {e}"}, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
    else:
        try:
            result = api_get("/api/debug/cache")
            print_result(result, pretty)
        except Exception as e:
            print(json.dumps({"error": f"cache endpoint not available: {e}"}, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)


@debug_group.command("system-info")
@click.option("--pretty", is_flag=True)
def debug_system_info(pretty):
    """获取系统信息。"""
    try:
        result = api_get("/api/debug/system-info")
        print_result(result, pretty)
    except Exception as e:
        print(json.dumps({"error": f"system-info endpoint not available: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)