"""Heiman CLI 入口。

所有命令默认输出 JSON（紧凑），加 --pretty 输出缩进格式。
退出码：0=成功，1=参数/校验错误，2=网络错误，3=业务错误。

调试日志：``$HEIMAN_HOME/config.json`` 中设置 ``{"debug": true}`` 后，每次调用会将
原始指令写入 ``$HEIMAN_HOME/log/heiman-cli.log``。
"""

import functools
import sys
from datetime import datetime, timezone

import click

from heiman_cli.commands.account import account_group
from heiman_cli.commands.admin import admin_group
from heiman_cli.commands.auth import auth_group
from heiman_cli.commands.config import config_group
from heiman_cli.commands.debug import debug_group
from heiman_cli.commands.device import device_group
from heiman_cli.commands.doctor import doctor_cmd
from heiman_cli.commands.event import event_group
from heiman_cli.commands.health import health_group
from heiman_cli.commands.home import home_group
from heiman_cli.commands.home_profile import home_profile_group
from heiman_cli.commands.monitor import monitor_group
from heiman_cli.commands.observability import observability_group
from heiman_cli.commands.person import person_group
from heiman_cli.commands.rule import rule_group
from heiman_cli.commands.service import service_group
from heiman_cli.commands.task import task_group
from heiman_cli.commands.ai import ai_group


@functools.lru_cache(maxsize=1)
def _resolve_version() -> str:
    """运行时版本：优先读已安装包元数据，未安装时回退 git describe，最后兜底。"""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("heiman-cli")
    except PackageNotFoundError:
        import subprocess

        try:
            out = subprocess.run(
                ["git", "describe", "--tags", "--always", "--dirty"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except Exception:
            pass
        return "0.0.0+unknown"


_VERSION = _resolve_version()


@click.group()
def cli():
    """heiman-cli — Heiman 智能家居传感器监控命令行工具。"""


cli.add_command(device_group)
cli.add_command(account_group)
cli.add_command(auth_group)
cli.add_command(health_group)
cli.add_command(home_group)
cli.add_command(event_group)
cli.add_command(rule_group)
cli.add_command(person_group)
cli.add_command(task_group)
cli.add_command(admin_group)
cli.add_command(service_group)
cli.add_command(config_group)
cli.add_command(debug_group)
cli.add_command(monitor_group)
cli.add_command(observability_group)
cli.add_command(home_profile_group)
cli.add_command(doctor_cmd)
cli.add_command(ai_group)


@cli.command("version")
@click.option("--pretty", is_flag=True)
def version_cmd(pretty):
    """显示版本信息。"""
    from heiman_cli.output import print_result

    print_result({"version": _VERSION}, pretty)


def _debug_log_invocation() -> None:
    """``config.json`` ``debug: true`` 时把命令行写入 ``$HEIMAN_HOME/log/heiman-cli.log``。"""
    from heiman_cli.config import load_config, heiman_home

    try:
        cfg = load_config()
    except Exception:
        return
    debug = cfg.get("debug", False)
    if isinstance(debug, str):
        debug = debug.lower() in ("true", "1", "yes", "on")
    if not debug:
        return
    log_file = heiman_home() / "log" / "heiman-cli.log"
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    line = f"{ts} [DEBUG] {' '.join(sys.argv)}\n"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def main() -> None:
    _debug_log_invocation()
    cli()
