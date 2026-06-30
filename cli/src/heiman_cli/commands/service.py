"""service 命令组：start / stop / restart / status / logs"""

from __future__ import annotations

import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import click

from heiman_cli.config import heiman_home
from heiman_cli.output import print_result

_PROGRAM_NAME = "heiman-backend"
_SERVER_MODULE = "heiman.main"


def _log_dir() -> Path:
    return heiman_home() / "log"


def _supervisor_conf() -> Path:
    return heiman_home() / "supervisord.conf"


def _supervisor_pid_file() -> Path:
    return heiman_home() / "supervisord.pid"


def _supervisor_sock() -> Path:
    return heiman_home() / "supervisor.sock"


def _supervisor_log() -> Path:
    return _log_dir() / "supervisord.log"


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _is_port_in_use(base_url: str) -> bool:
    parsed = urlparse(base_url)
    host = parsed.hostname or "localhost"
    port = parsed.port
    if port is None:
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0


def _find_pid_by_port(base_url: str) -> int | None:
    parsed = urlparse(base_url)
    port = parsed.port
    if port is None:
        return None
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError:
        return _find_pid_by_port_ss(port)
    except Exception:
        return None
    pids = [int(x) for x in result.stdout.split() if x.isdigit()]
    return pids[0] if pids else None


def _has_port_lookup_tool() -> bool:
    return bool(shutil.which("lsof") or shutil.which("ss"))


def _find_pid_by_port_ss(port: int) -> int | None:
    import re

    try:
        result = subprocess.run(
            ["ss", "-tlnp", f"sport = :{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    m = re.search(r"pid=(\d+)", result.stdout)
    return int(m.group(1)) if m else None


def _find_supervisord_pids() -> list[int]:
    conf = str(_supervisor_conf())
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return []
    pids: list[int] = []
    for line in result.stdout.splitlines():
        pid_str, _, cmd = line.strip().partition(" ")
        if "supervisord" in cmd and conf in cmd:
            try:
                pids.append(int(pid_str))
            except ValueError:
                pass
    return pids


def _terminate(pid: int, grace: float = 6.0) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + grace
    while time.time() < deadline:
        time.sleep(0.2)
        if not _is_running(pid):
            return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _process_uptime_seconds(pid: int) -> int | None:
    try:
        result = subprocess.run(
            ["ps", "-o", "etimes=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    s = result.stdout.strip()
    return int(s) if s.isdigit() else None


def _server_cmd_or_exit(pretty: bool) -> list[str]:
    from heiman_cli.config import get_value

    try:
        python_bin = get_value("server.python_bin")
    except KeyError:
        python_bin = ""

    if not python_bin:
        print_result(
            {
                "error": "server.python_bin 未配置",
                "hint": "配置方法: heiman-cli config set server.python_bin /path/to/python",
            },
            pretty,
        )
        sys.exit(1)

    p = Path(str(python_bin))
    if not p.exists() or not os.access(p, os.X_OK):
        print_result(
            {
                "error": f"server.python_bin 指向的解释器不可执行: {python_bin}",
                "hint": "通过 heiman-cli config set server.python_bin <path> 更新",
            },
            pretty,
        )
        sys.exit(1)

    return [str(p), "-m", _SERVER_MODULE]


def _parse_uptime_seconds(uptime_str: str) -> int | None:
    try:
        days = 0
        if " days, " in uptime_str:
            day_part, uptime_str = uptime_str.split(" days, ")
            days = int(day_part)
        elif " day, " in uptime_str:
            day_part, uptime_str = uptime_str.split(" day, ")
            days = int(day_part)
        h, m, s = uptime_str.split(":")
        return days * 86400 + int(h) * 3600 + int(m) * 60 + int(s)
    except Exception:
        return None


def _find_latest_log() -> Path | None:
    log_dir = _log_dir()
    if not log_dir.exists():
        return None
    supervised = log_dir / "heiman-backend.log"
    if supervised.exists():
        return supervised
    candidates = sorted(log_dir.glob("heiman-backend_*.log"))
    return candidates[-1] if candidates else None


def _find_latest_log_str() -> str | None:
    log = _find_latest_log()
    return str(log) if log else None


def _generate_supervisor_conf(server_cmd: str) -> None:
    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    sup_conf_path = _supervisor_conf()
    conf = f"""\
[supervisord]
logfile={_supervisor_log()}
logfile_maxbytes=10MB
logfile_backups=2
pidfile={_supervisor_pid_file()}
nodaemon=false
silent=true

[unix_http_server]
file={_supervisor_sock()}

[supervisorctl]
serverurl=unix://{_supervisor_sock()}

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[program:{_PROGRAM_NAME}]
command={server_cmd}
autorestart=true
startretries=3
startsecs=5
stopwaitsecs=30
redirect_stderr=true
stdout_logfile={log_dir}/heiman-backend.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=20
environment=HEIMAN_SUPERVISED="1",HEIMAN_HOME="{heiman_home()}"
"""
    if sup_conf_path.exists() and sup_conf_path.read_text() == conf:
        return
    sup_conf_path.write_text(conf)


def _supervisord_is_running() -> bool:
    if not _supervisor_sock().exists() or not _supervisor_conf().exists():
        return False
    result = _supervisorctl("pid")
    return result.returncode == 0 and result.stdout.strip().isdigit()


def _supervisorctl(*args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["supervisorctl", "-c", str(_supervisor_conf()), *args],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args, returncode=1, stdout="", stderr="timeout"
        )


def _get_backend_pid_from_supervisor() -> int | None:
    result = _supervisorctl("status", _PROGRAM_NAME)
    line = result.stdout.strip()
    if "RUNNING" not in line:
        return None
    import re

    m = re.search(r"pid\s+(\d+)", line)
    return int(m.group(1)) if m else None


def _resolve_backend_pid(cfg: dict, timeout: float = 8.0) -> int | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        pid = _get_backend_pid_from_supervisor()
        if pid:
            return pid
        time.sleep(0.3)
    return _find_pid_by_port(cfg["server"]["url"])


def _wait_for_health(cfg: dict, pretty: bool) -> None:
    import httpx

    health_url = cfg["server"]["url"].rstrip("/") + "/health"
    deadline = time.time() + 30
    while time.time() < deadline:
        status = _supervisorctl("status", _PROGRAM_NAME).stdout
        if "FATAL" in status:
            print_result({"error": "process failed to start, check logs"}, pretty)
            sys.exit(1)
        try:
            if httpx.get(health_url, timeout=2, verify=False).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    print_result(
        {"error": "service did not become ready within 30s, check logs"}, pretty
    )
    sys.exit(1)


@click.group("service")
def service_group():
    """服务管理：启动 / 停止 / 重启 / 状态 / 日志。"""


@service_group.command("start")
@click.option("--foreground", is_flag=True, help="前台运行（不 daemonize）")
@click.option("--pretty", is_flag=True)
def service_start(foreground, pretty):
    """启动 Heiman Agent Backend 服务。"""
    if _supervisord_is_running():
        backend_pid = _get_backend_pid_from_supervisor()
        if backend_pid:
            print_result(
                {"code": 1, "message": f"already running (pid={backend_pid})"}, pretty
            )
            sys.exit(1)

    from heiman_cli.config import load_config

    cfg = load_config()
    if _is_port_in_use(cfg["server"]["url"]):
        print_result(
            {"code": 1, "message": f"port already in use: {cfg['server']['url']}"},
            pretty,
        )
        sys.exit(1)

    cmd = _server_cmd_or_exit(pretty)

    if foreground:
        os.execvp(cmd[0], cmd)
    else:
        _generate_supervisor_conf(shlex.join(cmd))

        if _supervisord_is_running():
            _supervisorctl("reread")
            _supervisorctl("update")
            result = _supervisorctl("start", _PROGRAM_NAME)
            if result.returncode != 0:
                print_result(
                    {"error": f"supervisorctl start failed: {result.stdout.strip()}"},
                    pretty,
                )
                sys.exit(1)
        else:
            for orphan in _find_supervisord_pids():
                _terminate(orphan)
            _supervisor_sock().unlink(missing_ok=True)
            _supervisor_pid_file().unlink(missing_ok=True)
            try:
                subprocess.run(
                    ["supervisord", "-c", str(_supervisor_conf())],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print_result({"error": f"supervisord failed to start: {e}"}, pretty)
                sys.exit(1)

        _wait_for_health(cfg, pretty)
        backend_pid = _resolve_backend_pid(cfg)
        print_result({"code": 0, "message": "started", "pid": backend_pid}, pretty)


@service_group.command("stop")
@click.option("--pretty", is_flag=True)
@click.pass_context
def service_stop(ctx, pretty):
    """停止 Heiman Agent Backend 服务。"""
    _do_stop(pretty=pretty, quiet=ctx.obj.get("quiet", False) if ctx.obj else False)


def _do_stop(pretty: bool, quiet: bool = False) -> None:
    from heiman_cli.config import load_config

    cfg = load_config()

    control_up = _supervisord_is_running()
    backend_pid = _get_backend_pid_from_supervisor() if control_up else None
    if backend_pid is None:
        backend_pid = _find_pid_by_port(cfg["server"]["url"])
    acted = control_up or bool(_find_supervisord_pids()) or backend_pid is not None

    if control_up:
        try:
            sup_pid = int(_supervisor_pid_file().read_text().strip())
        except (ValueError, OSError):
            result = _supervisorctl("pid")
            out = result.stdout.strip()
            sup_pid = int(out) if out.isdigit() else None
        _supervisorctl("shutdown")
        if sup_pid:
            _terminate(sup_pid, grace=40.0)

    for pid in _find_supervisord_pids():
        _terminate(pid)

    port_pid = _find_pid_by_port(cfg["server"]["url"])
    if port_pid:
        _terminate(port_pid)

    for f in (_supervisor_sock(), _supervisor_pid_file()):
        f.unlink(missing_ok=True)

    if _is_port_in_use(cfg["server"]["url"]) and not _has_port_lookup_tool():
        print_result(
            {
                "error": f"端口仍被占用，且系统无 lsof / ss 可定位残留进程: {cfg['server']['url']}",
                "hint": "请安装 lsof 或 ss（iproute2）后重试，或手动 kill 占用该端口的进程",
            },
            pretty,
        )
        sys.exit(1)

    if not quiet:
        msg = "stopped" if acted else "not running"
        print_result({"code": 0, "message": msg, "pid": backend_pid}, pretty)


@service_group.command("restart")
@click.option("--pretty", is_flag=True)
@click.pass_context
def service_restart(ctx, pretty):
    """重启 Heiman Agent Backend 服务。"""
    if _supervisord_is_running():
        cmd = _server_cmd_or_exit(pretty)
        _generate_supervisor_conf(shlex.join(cmd))
        _supervisorctl("reread")
        _supervisorctl("update")
        result = _supervisorctl("restart", _PROGRAM_NAME)
        if result.returncode != 0:
            print_result(
                {"error": f"supervisorctl restart failed: {result.stdout.strip()}"},
                pretty,
            )
            sys.exit(1)

        from heiman_cli.config import load_config

        cfg = load_config()
        _wait_for_health(cfg, pretty)
        backend_pid = _resolve_backend_pid(cfg)
        print_result({"code": 0, "message": "restarted", "pid": backend_pid}, pretty)
    else:
        _do_stop(pretty=pretty, quiet=True)
        ctx.invoke(service_start, foreground=False, pretty=pretty)


@service_group.command("status")
@click.option("--pretty", is_flag=True)
def service_status(pretty):
    """查询服务进程状态（PID、端口、uptime）。"""
    from heiman_cli.config import load_config

    cfg = load_config()

    if _supervisord_is_running():
        result = _supervisorctl("status", _PROGRAM_NAME)
        line = result.stdout.strip()
        parts = line.split()
        state = parts[1] if len(parts) > 1 else "UNKNOWN"
        if state == "RUNNING":
            import re

            pid = None
            uptime_seconds = None
            m_pid = re.search(r"pid\s+(\d+)", line)
            if m_pid:
                pid = int(m_pid.group(1))
            m_uptime = re.search(r"uptime\s+(.+)", line)
            if m_uptime:
                uptime_seconds = _parse_uptime_seconds(m_uptime.group(1))

            print_result(
                {
                    "running": True,
                    "managed": True,
                    "pid": pid,
                    "uptime_seconds": uptime_seconds,
                    "log_file": _find_latest_log_str(),
                    "server": {"url": cfg["server"]["url"]},
                },
                pretty,
            )
            return
        else:
            print_result(
                {
                    "running": False,
                    "managed": True,
                    "supervisor_state": state,
                    "log_file": _find_latest_log_str(),
                },
                pretty,
            )
            return

    managed = False
    pid = _find_pid_by_port(cfg["server"]["url"])
    if not pid:
        print_result({"running": False}, pretty)
        return

    uptime_seconds = _process_uptime_seconds(pid)

    print_result(
        {
            "running": True,
            "managed": managed,
            "pid": pid,
            "uptime_seconds": uptime_seconds,
            "log_file": _find_latest_log_str(),
            "server": {"url": cfg["server"]["url"]},
        },
        pretty,
    )


@service_group.command("kill")
@click.option("--pretty", is_flag=True)
def service_kill(pretty):
    """强制杀掉所有 supervisord 守护进程与残留 backend，清运行时文件。"""
    from heiman_cli.config import load_config

    cfg = load_config()
    killed_supervisord: list[int] = []
    killed_backend: list[int] = []

    for pid in _find_supervisord_pids():
        _terminate(pid)
        killed_supervisord.append(pid)
    port_pid = _find_pid_by_port(cfg["server"]["url"])
    if port_pid:
        _terminate(port_pid)
        killed_backend.append(port_pid)

    removed: list[str] = []
    for f in (_supervisor_sock(), _supervisor_pid_file()):
        if f.exists():
            f.unlink(missing_ok=True)
            removed.append(str(f))

    if _is_port_in_use(cfg["server"]["url"]) and not _has_port_lookup_tool():
        print_result(
            {
                "error": f"端口仍被占用，且系统无 lsof / ss 可定位残留进程: {cfg['server']['url']}",
                "hint": "请安装 lsof 或 ss（iproute2）后重试，或手动 kill 占用该端口的进程",
            },
            pretty,
        )
        sys.exit(1)

    print_result(
        {
            "code": 0,
            "message": "cleaned",
            "killed_supervisord": killed_supervisord,
            "killed_backend": killed_backend,
            "removed": removed,
        },
        pretty,
    )


@service_group.command("logs")
@click.option("--follow", "-f", is_flag=True, help="持续跟踪日志（类似 tail -f）")
@click.option("--lines", "-n", default=50, show_default=True, help="显示最后 N 行")
def service_logs(follow, lines):
    """查看服务日志。"""
    log_dir = _log_dir()
    if not log_dir.exists():
        click.echo(f"log dir not found: {log_dir}", err=True)
        sys.exit(1)

    latest = _find_latest_log()
    if not latest:
        click.echo(f"no backend log in {log_dir}", err=True)
        sys.exit(1)

    cmd = ["tail", f"-n{lines}"]
    if follow:
        cmd.append("-f")
    cmd.append(str(latest))

    os.execvp("tail", cmd)