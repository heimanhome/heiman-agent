#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""heiman_ctl.py — Heiman Agent 本地服务管理器（WorkBuddy 技能脚本）。

只用 Python 标准库，Windows / macOS / Linux 通用。

子命令
------
  doctor                     环境自检（Python、项目目录、venv、端口、依赖）
  install  [--force]         创建 venv 并安装 backend / cli 依赖，生成 .env
  start    [--port N]        后台启动后端服务，等待 /health 通过
  stop                       停止后端服务
  restart                    重启
  status                     输出 JSON：是否已安装 / 是否运行中 / 端口 / 健康状态
  health                     调用 /health，输出 JSON
  logs     [-n N] [-f]       查看后端日志
  api      <METHOD> <PATH>   带鉴权调用本地后端 REST API，输出 JSON
          [--lang zh-CN|en-US]  期望返回文案语言，作为 Accept-Language 发送
  cli      <args...>         透传调用 heiman-cli
  where                      输出探测到的项目根目录与各路径

语言说明
--------
`api` 返回的是后端原始数据（字段名、枚举值可能为中文）。`--lang` 只是把它作为
`Accept-Language` 请求头传给后端，并在输出里回带 `lang` 字段供确认。后端若不支持
内容协商，该头会被忽略——此时调用方仍须按用户提问语言转述后再输出，
不得照抄中文原文（见 SKILL.md「执行总原则」第 6 条）。

退出码
------
  0 成功 / 1 用法或环境错误 / 2 网络或服务不可用 / 3 业务错误
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------
# 常量与路径
# --------------------------------------------------------------------------

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 1912
# 本地服务默认测试令牌（非真实凭据）。生产环境请通过 backend/heiman/.env 的 SERVER_TOKEN 覆盖。
DEFAULT_TOKEN = "heiman_test_token_123"

HOME_DIR = Path(os.environ.get("HEIMAN_HOME") or (Path.home() / ".heiman"))
STATE_FILE = HOME_DIR / "agent.json"
PID_FILE = HOME_DIR / "run" / "heiman-agent.pid"
LOG_DIR = HOME_DIR / "logs"
DATA_DIR = HOME_DIR / "data"
CONF_DIR = HOME_DIR / "config"
VENV_DIR = HOME_DIR / "venv"
BACKEND_LOG = LOG_DIR / "backend.log"

# 项目根目录自动探测候选（按顺序）
PROJECT_CANDIDATES = [
    Path("D:/heiman-agent"),
    Path("C:/heiman-agent"),
    Path.home() / "heiman-agent",
    Path.home() / "Documents" / "heiman-agent",
    Path.home() / "Desktop" / "heiman-agent",
    Path.home() / "Projects" / "heiman-agent",
    Path.home() / "trae_projects" / "heiman-agent",
    Path.home() / "Documents" / "trae_projects" / "heiman-agent",
]

IS_WINDOWS = os.name == "nt"


# --------------------------------------------------------------------------
# 输出helpers
# --------------------------------------------------------------------------


def emit(payload: dict, code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


def info(msg: str) -> None:
    print(f"[heiman] {msg}", file=sys.stderr)


def fail(msg: str, code: int = 1, **extra) -> int:
    payload = {"ok": False, "error": msg}
    payload.update(extra)
    return emit(payload, code)


# --------------------------------------------------------------------------
# 语言（与 heiman_snapshot.py 保持同一套取值，全链路一致）
# --------------------------------------------------------------------------

LANG_ALIASES = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-hans": "zh-CN",
    "cn": "zh-CN",
    "chinese": "zh-CN",
    "中文": "zh-CN",
    "en": "en-US",
    "en-us": "en-US",
    "en-gb": "en-US",
    "english": "en-US",
    "英文": "en-US",
}
SUPPORTED_LANGS = ("zh-CN", "en-US")


def normalize_lang(value: str | None) -> str:
    """把用户/调用方给的语言标识归一到 zh-CN / en-US。

    无法识别时回退 zh-CN（保持默认行为，不破坏向后兼容）。
    注意：不在此处"猜"提问语言——语言只在入口判定一次，见 SKILL.md 执行总原则第 6 条。
    """
    if not value:
        return "zh-CN"
    key = value.strip().lower()
    if key in LANG_ALIASES:
        return LANG_ALIASES[key]
    for supported in SUPPORTED_LANGS:          # 形如 en-US;q=0.9 / zh-CN,zh
        if key.startswith(supported.lower()):
            return supported
    return "zh-CN"


# --------------------------------------------------------------------------
# 项目定位
# --------------------------------------------------------------------------


def looks_like_project(path: Path) -> bool:
    return (path / "backend" / "heiman" / "pyproject.toml").is_file()


def read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    merged = read_state()
    merged.update(data)
    STATE_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def resolve_project(explicit: str | None = None) -> Path | None:
    """按优先级定位项目根目录：--project > 环境变量 > 状态文件 > 常见路径。"""
    if explicit:
        p = Path(explicit).expanduser().resolve()
        return p if looks_like_project(p) else None

    env = os.environ.get("HEIMAN_AGENT_HOME")
    if env:
        p = Path(env).expanduser()
        if looks_like_project(p):
            return p.resolve()

    state = read_state()
    if root := state.get("project_root"):
        p = Path(root)
        if looks_like_project(p):
            return p

    for cand in PROJECT_CANDIDATES:
        if looks_like_project(cand):
            return cand.resolve()

    return None


def venv_python() -> Path:
    if IS_WINDOWS:
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def venv_script(name: str) -> Path:
    if IS_WINDOWS:
        return VENV_DIR / "Scripts" / f"{name}.exe"
    return VENV_DIR / "bin" / name


# --------------------------------------------------------------------------
# 运行状态
# --------------------------------------------------------------------------


def read_pid() -> int | None:
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return pid if pid > 0 else None


def pid_alive(pid: int) -> bool:
    if IS_WINDOWS:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            errors="replace",
        )
        return str(pid) in (out.stdout or "")
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def port_open(host: str, port: int, timeout: float = 0.6) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def http_get(url: str, token: str | None = None, timeout: float = 5.0):
    req = urllib.request.Request(url, method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        try:
            return resp.status, json.loads(body)
        except json.JSONDecodeError:
            return resp.status, body


def health(host: str, port: int, timeout: float = 5.0) -> dict:
    try:
        status, body = http_get(f"http://{host}:{port}/health", timeout=timeout)
        return {"reachable": True, "status_code": status, "body": body}
    except urllib.error.HTTPError as e:
        return {"reachable": True, "status_code": e.code, "body": e.read().decode("utf-8", "replace")}
    except Exception as e:  # noqa: BLE001
        return {"reachable": False, "error": f"{type(e).__name__}: {e}"}


def server_token(project: Path | None) -> str:
    """从 backend/heiman/.env 读取 SERVER_TOKEN，缺省用内置默认值。"""
    if project:
        env_file = project / "backend" / "heiman" / ".env"
        try:
            for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("SERVER_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            pass
    return os.environ.get("SERVER_TOKEN") or DEFAULT_TOKEN


def runtime_settings(project: Path | None) -> tuple[str, int]:
    """返回 (host, port)。优先状态文件，其次默认值。"""
    state = read_state()
    host = state.get("host") or DEFAULT_HOST
    port = int(state.get("port") or DEFAULT_PORT)
    return host, port


def build_env(project: Path, host: str, port: int) -> dict:
    env = os.environ.copy()
    env["HEIMAN_HOME"] = str(HOME_DIR)
    env["HEIMAN_DATA_DIR"] = str(DATA_DIR)
    env["HEIMAN_LOG_DIR"] = str(LOG_DIR)
    env["HEIMAN_CONFIG_DIR"] = str(CONF_DIR)
    env["HEIMAN_STATIC_DIR"] = str(project / "backend" / "heiman" / "static")
    env["SERVER_HOST"] = host
    env["SERVER_PORT"] = str(port)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


# --------------------------------------------------------------------------
# 子命令
# --------------------------------------------------------------------------


def cmd_where(args) -> int:
    project = resolve_project(args.project)
    return emit(
        {
            "ok": project is not None,
            "project_root": str(project) if project else None,
            "heiman_home": str(HOME_DIR),
            "venv": str(VENV_DIR),
            "venv_python": str(venv_python()),
            "venv_ready": venv_python().is_file(),
            "state_file": str(STATE_FILE),
            "log_file": str(BACKEND_LOG),
            "installed": venv_python().is_file(),
        },
        0 if project else 1,
    )


def cmd_doctor(args) -> int:
    project = resolve_project(args.project)
    host, port = runtime_settings(project)
    checks = {
        "python": {"ok": sys.version_info >= (3, 10), "value": sys.version.split()[0]},
        "project_root": {"ok": project is not None, "value": str(project) if project else None},
        "venv_ready": {"ok": venv_python().is_file(), "value": str(venv_python())},
        "port_free": {
            "ok": not port_open(host, port),
            "value": f"{host}:{port}",
            "note": "占用中说明服务可能已在运行",
        },
        "git": {"ok": shutil.which("git") is not None, "value": shutil.which("git")},
    }
    ok = checks["python"]["ok"] and checks["project_root"]["ok"]
    return emit({"ok": ok, "checks": checks}, 0 if ok else 1)


def cmd_install(args) -> int:
    project = resolve_project(args.project)
    if not project:
        return fail(
            "未找到 heiman-agent 项目根目录。请用 --project <路径> 指定，"
            "或设置环境变量 HEIMAN_AGENT_HOME。",
            extra={"probed": [str(p) for p in PROJECT_CANDIDATES]},
        )

    host, port = runtime_settings(project)
    steps: list[dict] = []

    for d in (HOME_DIR, LOG_DIR, DATA_DIR, CONF_DIR, PID_FILE.parent):
        d.mkdir(parents=True, exist_ok=True)

    # 1) venv
    if not venv_python().is_file() or args.force:
        info(f"创建虚拟环境: {VENV_DIR}")
        r = subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            capture_output=True,
            text=True,
            errors="replace",
        )
        steps.append({"step": "venv", "ok": r.returncode == 0, "output": (r.stdout + r.stderr).strip()[-2000:]})
        if r.returncode != 0:
            return emit({"ok": False, "steps": steps}, 1)
    else:
        steps.append({"step": "venv", "ok": True, "output": "已存在，跳过"})

    py = str(venv_python())

    # 2) 升级 pip
    r = subprocess.run(
        [py, "-m", "pip", "install", "--upgrade", "pip", "-q"],
        capture_output=True, text=True, errors="replace",
    )
    steps.append({"step": "pip-upgrade", "ok": r.returncode == 0, "output": (r.stdout + r.stderr).strip()[-1000:]})

    # 3) 安装 backend（可编辑）
    backend = project / "backend" / "heiman"
    info(f"安装后端依赖: {backend}")
    r = subprocess.run(
        [py, "-m", "pip", "install", "-e", str(backend)],
        capture_output=True, text=True, errors="replace", cwd=str(project),
    )
    steps.append({
        "step": "install-backend",
        "ok": r.returncode == 0,
        "output": (r.stdout + r.stderr).strip()[-3000:],
    })
    backend_ok = r.returncode == 0

    # 4) 安装 CLI（可编辑）
    cli_dir = project / "cli"
    cli_ok = False
    if cli_dir.is_dir():
        info(f"安装 CLI: {cli_dir}")
        r = subprocess.run(
            [py, "-m", "pip", "install", "-e", str(cli_dir)],
            capture_output=True, text=True, errors="replace", cwd=str(project),
        )
        cli_ok = r.returncode == 0
        steps.append({"step": "install-cli", "ok": cli_ok, "output": (r.stdout + r.stderr).strip()[-3000:]})

    # 5) 生成 .env
    env_file = backend / ".env"
    example = backend / ".env.example"
    if not env_file.exists():
        content = example.read_text(encoding="utf-8", errors="replace") if example.exists() else ""
        if not content:
            content = (
                "HEIMAN_API_URL=https://spapi.heiman.cn\n"
                "HEIMAN_APP_ID=11\n"
                "HEIMAN_EMAIL=\n"
                "HEIMAN_PASSWORD=\n"
            )
        if "SERVER_HOST=" not in content:
            content += f"\nSERVER_HOST={host}\nSERVER_PORT={port}\nSERVER_RELOAD=false\n"
        env_file.write_text(content, encoding="utf-8")
        steps.append({"step": "dotenv", "ok": True, "output": f"已生成 {env_file}，请填写 HEIMAN_EMAIL / HEIMAN_PASSWORD"})
    else:
        steps.append({"step": "dotenv", "ok": True, "output": f"已存在 {env_file}，保留原内容"})

    # 6) CLI 配置
    cfg = CONF_DIR / "config.json"
    if not cfg.exists():
        cfg.write_text(
            json.dumps(
                {
                    "debug": False,
                    "server": {
                        "url": f"http://{host}:{port}",
                        "token": server_token(project),
                        "tls_verify": False,
                        "python_bin": py,
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        steps.append({"step": "cli-config", "ok": True, "output": str(cfg)})

    write_state({"project_root": str(project), "host": host, "port": port, "venv_python": py})

    return emit(
        {
            "ok": backend_ok,
            "project_root": str(project),
            "venv": str(VENV_DIR),
            "steps": steps,
            "next": [
                "填写 backend/heiman/.env 中的 HEIMAN_EMAIL / HEIMAN_PASSWORD",
                "运行: python scripts/heiman_ctl.py start",
            ],
        },
        0 if backend_ok else 1,
    )


def cmd_start(args) -> int:
    project = resolve_project(args.project)
    if not project:
        return fail("未找到 heiman-agent 项目根目录，请先运行 install 或指定 --project。")

    host, port = runtime_settings(project)
    if args.port:
        port = int(args.port)
        write_state({"port": port})
    if args.host:
        host = args.host
        write_state({"host": host})

    pid = read_pid()
    if pid and pid_alive(pid):
        h = health(host, port)
        return emit({"ok": True, "already_running": True, "pid": pid, "health": h})

    # 端口上已有健康的 heiman-agent（可能是外部启动的），直接复用
    existing = health(host, port, timeout=3)
    if existing.get("reachable"):
        return emit(
            {
                "ok": True,
                "already_running": True,
                "managed_by_skill": False,
                "url": f"http://{host}:{port}",
                "health": existing,
                "hint": "服务已在运行（非本技能启动），直接使用即可。",
            }
        )

    if port_open(host, port):
        return fail(
            f"端口 {host}:{port} 已被其他进程占用且 /health 不通。可用 --port 指定其它端口，"
            "或先停止占用该端口的进程。",
            2,
        )

    if not venv_python().is_file():
        return fail("虚拟环境不存在，请先运行: python scripts/heiman_ctl.py install")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    env = build_env(project, host, port)
    cmd = [
        str(venv_python()),
        "-m",
        "uvicorn",
        "heiman.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    info(f"启动: {' '.join(cmd)}")

    logf = open(BACKEND_LOG, "a", encoding="utf-8", errors="replace")
    logf.write(f"\n===== start {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
    logf.flush()

    kwargs: dict = {
        "cwd": str(project / "backend" / "heiman"),
        "env": env,
        "stdout": logf,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
    }
    if IS_WINDOWS:
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        )
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **kwargs)
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")

    # 等待健康检查
    deadline = time.time() + (args.wait or 45)
    last: dict = {}
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = tail_file(BACKEND_LOG, 40)
            PID_FILE.unlink(missing_ok=True)
            return emit(
                {
                    "ok": False,
                    "error": "后端进程启动后立即退出，请检查日志与 .env 配置。",
                    "exit_code": proc.returncode,
                    "log_tail": tail,
                    "log_file": str(BACKEND_LOG),
                },
                1,
            )
        last = health(host, port, timeout=2)
        if last.get("reachable"):
            break
        time.sleep(1.5)

    ok = bool(last.get("reachable"))
    return emit(
        {
            "ok": ok,
            "pid": proc.pid,
            "url": f"http://{host}:{port}",
            "health": last,
            "log_file": str(BACKEND_LOG),
            "hint": None if ok else "启动超时，服务可能仍在初始化（首次启动需拉取海曼云端数据）。查看日志确认。",
        },
        0 if ok else 2,
    )


def cmd_stop(args) -> int:
    pid = read_pid()
    if not pid:
        return emit({"ok": True, "stopped": False, "reason": "没有记录到运行中的进程"})

    if not pid_alive(pid):
        PID_FILE.unlink(missing_ok=True)
        return emit({"ok": True, "stopped": False, "reason": "进程已不存在，已清理 PID 文件"})

    if IS_WINDOWS:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)
    else:
        import signal as _signal

        try:
            os.kill(pid, _signal.SIGTERM)
            for _ in range(20):
                if not pid_alive(pid):
                    break
                time.sleep(0.3)
            else:
                os.kill(pid, _signal.SIGKILL)
        except ProcessLookupError:
            pass

    PID_FILE.unlink(missing_ok=True)
    return emit({"ok": True, "stopped": True, "pid": pid})


def cmd_restart(args) -> int:
    cmd_stop(args)
    time.sleep(1.5)
    return cmd_start(args)


def cmd_status(args) -> int:
    project = resolve_project(args.project)
    host, port = runtime_settings(project)
    pid = read_pid()
    managed = bool(pid and pid_alive(pid))
    listening = port_open(host, port)
    h = health(host, port, timeout=3) if (managed or listening) else {"reachable": False}
    service_up = bool(h.get("reachable"))

    if service_up:
        hint = None if managed else "服务由外部进程启动（非本技能管理），可直接取数；如需由技能接管请先 stop 再 start。"
    elif listening:
        hint = f"{host}:{port} 端口有监听但 /health 不通过，服务可能仍在初始化，请稍候或查看日志。"
    else:
        hint = "服务未运行，请执行: python scripts/heiman_ctl.py start"

    return emit(
        {
            "ok": service_up,
            "service_up": service_up,
            "managed_by_skill": managed,
            "installed": venv_python().is_file(),
            "project_root": str(project) if project else None,
            "pid": pid if managed else None,
            "url": f"http://{host}:{port}",
            "health": h,
            "log_file": str(BACKEND_LOG),
            "hint": hint,
        }
    )


def cmd_health(args) -> int:
    project = resolve_project(args.project)
    host, port = runtime_settings(project)
    h = health(host, port)
    return emit({"ok": bool(h.get("reachable")), "url": f"http://{host}:{port}", "health": h},
                0 if h.get("reachable") else 2)


def cmd_logs(args) -> int:
    if not BACKEND_LOG.exists():
        return fail(f"日志文件不存在: {BACKEND_LOG}", 1)
    if args.follow:
        try:
            with BACKEND_LOG.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if line:
                        sys.stdout.write(line)
                        sys.stdout.flush()
                    else:
                        time.sleep(0.5)
        except KeyboardInterrupt:
            return 0
    print(tail_file(BACKEND_LOG, args.lines))
    return 0


def cmd_api(args) -> int:
    project = resolve_project(args.project)
    host, port = runtime_settings(project)
    token = server_token(project)
    method = args.method.upper()
    path = args.path if args.path.startswith("/") else "/" + args.path
    url = f"http://{host}:{port}{path}"

    data = None
    if args.data:
        data = args.data.encode("utf-8")

    req = urllib.request.Request(url, method=method, data=data)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    lang = normalize_lang(getattr(args, "lang", None))
    if lang:
        # 后端若支持内容协商，会按此返回对应语言文案；不支持时该头被忽略，
        # 调用方仍需按提问语言转述（见 SKILL.md「执行总原则」第 6 条）。
        req.add_header("Accept-Language", lang)
    if data:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                return emit({"ok": True, "lang": lang, "status_code": resp.status, "data": body[:20000]})
            if isinstance(payload, dict):
                out = {"ok": True, "lang": lang, "status_code": resp.status, **payload}
            else:
                out = {"ok": True, "lang": lang, "status_code": resp.status, "data": payload}
            return emit(out)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return emit({"ok": False, "status_code": e.code, "error": body[:2000]}, 3)
    except Exception as e:  # noqa: BLE001
        return fail(f"请求失败: {type(e).__name__}: {e}", 2, url=url)


def cmd_cli(args) -> int:
    project = resolve_project(args.project)
    if not project:
        return fail("未找到 heiman-agent 项目根目录。")
    if not venv_python().is_file():
        return fail("虚拟环境不存在，请先运行 install。")

    exe = venv_script("heiman-cli")
    host, port = runtime_settings(project)
    env = build_env(project, host, port)
    if exe.is_file():
        cmd = [str(exe), *args.rest]
    else:
        cmd = [str(venv_python()), "-c", "from heiman_cli.main import main; main()", *args.rest]

    r = subprocess.run(cmd, cwd=str(project), env=env, capture_output=True, text=True, errors="replace")
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0 and "No module named 'heiman_cli'" in err:
        return fail(
            "heiman-cli 未安装到当前虚拟环境（缺少 heiman_cli 模块）。"
            "如需纯查询，请改用 api 子命令，例如 `heiman_ctl.py api GET /api/sensors`；"
            "如需完整 CLI 能力，先运行 `heiman_ctl.py install --force` 重建虚拟环境。",
            code=3,
            hint="heiman-cli missing",
        )
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return r.returncode


def tail_file(path: Path, lines: int) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return f"<读取失败: {e}>"
    return "\n".join(content[-lines:])


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="heiman_ctl.py",
        description="Heiman Agent 本地服务管理器（WorkBuddy 技能脚本）",
    )
    p.add_argument("--project", help="heiman-agent 项目根目录（默认自动探测）")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("where", help="输出探测到的路径信息").set_defaults(func=cmd_where)
    sub.add_parser("doctor", help="环境自检").set_defaults(func=cmd_doctor)

    sp = sub.add_parser("install", help="创建 venv 并安装依赖")
    sp.add_argument("--force", action="store_true", help="强制重建虚拟环境")
    sp.set_defaults(func=cmd_install)

    sp = sub.add_parser("start", help="后台启动后端服务")
    sp.add_argument("--port", type=int, help="监听端口（默认 1912）")
    sp.add_argument("--host", help="监听地址（默认 127.0.0.1）")
    sp.add_argument("--wait", type=int, default=45, help="等待健康检查的秒数")
    sp.set_defaults(func=cmd_start)

    sub.add_parser("stop", help="停止后端服务").set_defaults(func=cmd_stop)

    sp = sub.add_parser("restart", help="重启后端服务")
    sp.add_argument("--port", type=int, help="监听端口（默认 1912）")
    sp.add_argument("--host", help="监听地址（默认 127.0.0.1）")
    sp.add_argument("--wait", type=int, default=45, help="等待健康检查的秒数")
    sp.set_defaults(func=cmd_restart)

    sub.add_parser("status", help="输出运行状态 JSON").set_defaults(func=cmd_status)
    sub.add_parser("health", help="调用 /health").set_defaults(func=cmd_health)

    sp = sub.add_parser("logs", help="查看后端日志")
    sp.add_argument("-n", "--lines", type=int, default=80, help="输出末尾行数")
    sp.add_argument("-f", "--follow", action="store_true", help="持续跟踪（Ctrl+C 退出）")
    sp.set_defaults(func=cmd_logs)

    sp = sub.add_parser("api", help="带鉴权调用本地后端 REST API")
    sp.add_argument("method", help="HTTP 方法，如 GET / POST")
    sp.add_argument("path", help="路径，如 /api/sensors")
    sp.add_argument("--data", help="请求体（JSON 字符串）")
    sp.add_argument("--timeout", type=float, default=30.0)
    sp.add_argument(
        "--lang",
        default=None,
        help="期望的返回文案语言 zh-CN / en-US，作为 Accept-Language 发送；"
             "后端不支持时仅作回带标记，调用方仍需按提问语言转述",
    )
    sp.set_defaults(func=cmd_api)

    sp = sub.add_parser("cli", help="透传调用 heiman-cli")
    sp.add_argument("rest", nargs=argparse.REMAINDER, help="heiman-cli 参数")
    sp.set_defaults(func=cmd_cli)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
