#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""heiman_ctl.py — Heiman Agent 本地服务管理器（WorkBuddy 技能脚本）。

只用 Python 标准库，Windows / macOS / Linux 通用。

子命令
------
  doctor                     环境自检（Python、项目目录、venv、端口、依赖、git 源）
  install  [--force]         自动定位安装源（必要时 git clone），创建 venv 并安装依赖
          [--source URL] [--branch B] [--dest DIR] [--no-update] [--no-probe]
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
  source   show              显示自动查找到的安装源（地址、来源层级、本地路径）
  source   probe             逐个探测候选 git 地址的可达性
  source   scan              扫描本地已存在的 heiman-agent 克隆
  source   sync              只拉取/更新源码，不装依赖
  source   set <URL>         把地址写入 ~/.heiman/config/install-sources.json（可选层，覆盖内置默认值）
  source   clear             清除用户级安装源配置

自动查找安装源
--------------
本地没有源码时，`install` 会按固定优先级自动定位 git 地址并克隆到
`~/.heiman/src/heiman-agent`，无需手动指定来源：

  1. `--source <git-url>`   命令行显式指定
  2. `--project <path>`     命令行显式指定本地已有源码（不克隆）
  3. `HEIMAN_GIT_URL`       环境变量（可选 `HEIMAN_GIT_BRANCH`）
  4. 本地已存在副本         有界扫描（深度/时间预算，结果缓存 24h），命中即复用
  5. `~/.heiman/agent.json` 状态文件里的 `git_url` / `project_root`
  6. `~/.heiman/config/install-sources.json`  用户级配置（可选）
  7. `<SKILL>/config/install-sources.json`    技能级配置（可选）
  8. 脚本内置默认值                            heiman_ctl.py 的 DEFAULTS，无需任何配置文件
  9. generated 候选                            hosts × orgs × repo_name 逐个探测（兜底，最慢）

换仓库时用 `source set <新地址>` 即可，不改脚本、也不需要配置文件。

详见 `SKILL.md 的「安装源自动查找」章节`。

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

# ===== 以下原为 scripts/heiman_source.py，已内联到本文件 =====
# （实现「安装源自动定位」，使技能包无需新增独立文件；如需改默认 git 地址，
#  仍可用 `source set <url>` 写入用户级配置，或改下方 DEFAULTS）

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

# --------------------------------------------------------------------------
# 路径与常量
# --------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent

HOME_DIR = Path(os.environ.get("HEIMAN_HOME") or (Path.home() / ".heiman"))
CONF_DIR = HOME_DIR / "config"
STATE_FILE = HOME_DIR / "agent.json"

# 可选配置文件：都不存在也能正常工作（内置默认值兜底）
#   技能级 <SKILL>/config/install-sources.json —— 团队分发时用，可选
#   用户级 ~/.heiman/config/install-sources.json —— 个人覆盖，由 `source set` 生成
SKILL_CONFIG = SKILL_DIR / "config" / "install-sources.json"
USER_CONFIG = CONF_DIR / "install-sources.json"

DEFAULT_REPO = "heiman-agent"
DEFAULT_DEST = HOME_DIR / "src" / DEFAULT_REPO

# 项目根目录自动探测候选（按顺序，跳过不存在的）
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

ENV_URL = "HEIMAN_GIT_URL"
ENV_BRANCH = "HEIMAN_GIT_BRANCH"
ENV_SCAN_ROOTS = "HEIMAN_SCAN_ROOTS"
ENV_NO_SCAN = "HEIMAN_NO_SCAN"

# 允许的 URL scheme：https / ssh / git / file（本地镜像）；http 允许但会告警
ALLOWED_SCHEMES = ("https", "http", "ssh", "git", "file")
INSECURE_SCHEMES = ("http",)

# 来源优先级（数字越小越优先）
PRIORITY = {
    "cli": 10,
    "project": 20,
    "env": 30,
    "local-clone": 40,
    "state": 50,
    "user-config": 60,
    "skill-config": 70,
    "skill-default": 75,
    "generated": 80,
}

# 扫描时的默认跳过目录（大小写不敏感）
DEFAULT_SKIP_DIRS = [
    ".git", "node_modules", "AppData", "Application Data",
    "$Recycle.Bin", "System Volume Information", "Recovery",
    "Windows", "Program Files", "Program Files (x86)", "ProgramData",
    "venv", ".venv", "__pycache__", "dist", "build", ".cache",
    ".npm", ".gradle", ".m2", ".mypy_cache", ".pytest_cache",
    "Library", "Applications", ".Trash", ".local",
]

DEFAULTS: dict[str, Any] = {
    "repo_name": DEFAULT_REPO,

    # —— 技能内置默认安装源（不需要任何配置文件即生效）——
    # 想换仓库，任选其一：source set <url>（写用户级配置） / 环境变量 HEIMAN_GIT_URL /
    # 放一个可选的 <SKILL>/config/install-sources.json 覆盖。
    "primary": "https://github.com/heimanhome/heiman-agent.git",
    "primary_branch": "master",
    "candidates": [
        {"url": "http://192.168.1.14:10082/xiaoli/heiman-agent.git", "branch": "master",
         "origin": "skill-default"},
    ],

    "generated": {
        "hosts": ["github.com", "gitlab.com", "gitee.com"],
        "orgs": ["Heiman", "HeimanSmart", "heiman", "heiman-tech"],
        "with_git_suffix": True,
    },
    "scan": {
        "roots": ["~", "~/Documents", "~/Desktop", "~/Projects", "~/workspace", "~/code", "~/git"],
        "extra_roots": ["D:/", "C:/"],
        "max_depth": 3,
        "extra_root_depth": 2,
        "budget_seconds": 10.0,
        "cache_hours": 24,
        "skip_dirs": DEFAULT_SKIP_DIRS,
    },
    "probe": {"timeout_seconds": 6.0, "total_budget_seconds": 40.0},
    "clone": {"dest": "src/heiman-agent", "depth": 1, "timeout_seconds": 600},
}

IS_WINDOWS = os.name == "nt"


# --------------------------------------------------------------------------
# 输出 helpers
# --------------------------------------------------------------------------


def emit(payload: dict, code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


def info(msg: str) -> None:
    print(f"[heiman] {msg}", file=sys.stderr)


def redact_url(url: str | None) -> str | None:
    """把 URL 里的 user:pass@ / token@ 脱敏，避免凭据落进日志与输出。

    `https://u:p@host/a.git` -> `https://***:***@host/a.git`
    `https://token@host/a.git` -> `https://***@host/a.git`
    """
    if not url:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if not parts.netloc or "@" not in parts.netloc:
        return url
    creds, _, host = parts.netloc.rpartition("@")
    masked = "***:***" if ":" in creds else "***"
    return urlunsplit((parts.scheme, f"{masked}@{host}", parts.path, parts.query, parts.fragment))


def _scrub(text: str | None, *urls: str | None) -> str:
    """把文本中出现的所有 URL 凭据替换成脱敏形式。"""
    if not text:
        return ""
    out = text
    for u in urls:
        if not u:
            continue
        try:
            parts = urlsplit(u)
        except ValueError:
            continue
        if parts.netloc and "@" in parts.netloc:
            creds, _, host = parts.netloc.rpartition("@")
            out = out.replace(f"{creds}@", "***:***@" if ":" in creds else "***@")
    return out


# --------------------------------------------------------------------------
# 状态文件（与 heiman_ctl.py 共用同一个 ~/.heiman/agent.json）
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# 仓库识别
# --------------------------------------------------------------------------


def looks_like_project(path: Path) -> bool:
    """判断是否 heiman-agent 仓库根目录。"""
    try:
        return (path / "backend" / "heiman" / "pyproject.toml").is_file()
    except OSError:
        return False


def git_bin() -> str | None:
    return shutil.which("git")


def git_env() -> dict:
    """非交互 git 环境：禁止任何凭据交互，避免自动化流程卡死。"""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    env["GIT_CONFIG_NOSYSTEM"] = "0"
    if not env.get("GIT_SSH_COMMAND"):
        env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
    env["GIT_LFS_SKIP_SMUDGE"] = "1"
    return env


def _run_git(args: list[str], timeout: float | None = None, cwd: str | None = None):
    exe = git_bin()
    if not exe:
        return 127, "", "git 未安装或不在 PATH 中"
    try:
        r = subprocess.run(
            [exe, *args],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            env=git_env(),
            cwd=cwd,
        )
        return r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", f"git {' '.join(args)} 超时（{timeout}s）"
    except OSError as e:  # noqa: BLE001
        return 1, "", f"{type(e).__name__}: {e}"


# --------------------------------------------------------------------------
# URL 处理
# --------------------------------------------------------------------------

_SCP_RE = re.compile(r"^(?P<user>[^@/]+)@(?P<host>[^:/]+):(?P<path>.+)$")


def normalize_url(url: str) -> str:
    """归一到 https 形式，用于比较与去重（不含凭据）。

    - 去掉末尾 `/` 与 `.git`
    - `git@github.com:org/repo.git` -> `https://github.com/org/repo`
    - host 转小写
    """
    if not url:
        return ""
    u = url.strip()
    m = _SCP_RE.match(u)
    if m:
        u = f"ssh://{m.group('user')}@{m.group('host')}/{m.group('path').lstrip('/')}"
    parts = urlsplit(u)
    scheme = parts.scheme.lower() or "https"
    host = (parts.hostname or "").lower()
    port = f":{parts.port}" if parts.port else ""
    path = parts.path.rstrip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]
    return f"{scheme}://{host}{port}{path}"


def _identity(url: str) -> str:
    """仓库身份：与传输协议、凭据无关的「同一仓库」判据。"""
    return normalize_url(url).split("://", 1)[-1]


def urls_equal(a: str | None, b: str | None) -> bool:
    """判断两个地址是否指向同一仓库。

    忽略 scheme 与凭据：`git@host:o/r.git` 与 `https://host/o/r.git` 视为同一仓库，
    避免同一仓库换个传输方式就被判定为"另一来源"。
    """
    return bool(a) and bool(b) and _identity(a) == _identity(b)


def validate_url(url: str) -> tuple[bool, str | None, str | None]:
    """校验 URL。返回 (是否可用, 错误信息, 安全告警)。"""
    if not url or not url.strip():
        return False, "空的 git 地址", None
    u = url.strip()
    m = _SCP_RE.match(u)
    scheme = urlsplit(u).scheme.lower()
    if m:
        return True, None, None
    if scheme not in ALLOWED_SCHEMES:
        return (
            False,
            f"不支持的 git 地址协议: {scheme or '<无>'}"
            f"（允许 {' / '.join(ALLOWED_SCHEMES)}，或使用 git@host:org/repo.git 形式）",
            None,
        )
    warn = None
    if scheme in INSECURE_SCHEMES:
        warn = f"git 地址使用明文 {scheme}://，凭据可能被窃听，建议改用 https 或 ssh"
    return True, None, warn


# --------------------------------------------------------------------------
# 配置加载
# --------------------------------------------------------------------------


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_registry() -> tuple[dict, list[dict]]:
    """合并「脚本内置默认值 → 可选技能配置 → 可选用户配置」。

    三层都是可选的：技能包**不需要**携带 `config/install-sources.json`，
    内置默认值即可让自动安装跑通；若存在配置文件则按需覆盖。

    返回 (合并后的配置, 各层来源说明)。
    """
    cfg = json.loads(json.dumps(DEFAULTS))  # 深拷贝，避免污染默认常量
    layers = [
        {
            "layer": "skill-default",
            "path": "heiman_ctl.py:DEFAULTS",
            "loaded": True,
            "primary": bool((cfg.get("primary") or "").strip()),
        }
    ]

    skill = _load_json(SKILL_CONFIG)
    layers.append({"layer": "skill-config", "path": str(SKILL_CONFIG),
                   "loaded": bool(skill), "optional": True})
    if skill:
        cfg = _deep_merge(cfg, skill)

    user = _load_json(USER_CONFIG)
    layers.append({"layer": "user-config", "path": str(USER_CONFIG),
                   "loaded": bool(user), "optional": True})
    if user:
        cfg = _deep_merge(cfg, user)

    # 环境变量覆盖
    if os.environ.get(ENV_BRANCH):
        cfg["primary_branch"] = os.environ[ENV_BRANCH].strip()

    return cfg, layers


def _origin_of(url: str) -> str:
    """判断某个地址来自哪一层配置（用户级 > 技能配置 > 脚本内置默认值）。"""
    for path, origin in ((USER_CONFIG, "user-config"), (SKILL_CONFIG, "skill-config")):
        data = _load_json(path)
        if str(data.get("primary") or "").strip() == url:
            return origin
        for c in data.get("candidates") or []:
            cu = c if isinstance(c, str) else (c.get("url") if isinstance(c, dict) else None)
            if cu and str(cu).strip() == url:
                return origin
    # 来自脚本内置默认值
    return "skill-default"


def configured_urls(cfg: dict | None = None) -> list[tuple[str, str]]:
    """收集配置里写明的地址，返回 [(url, origin)]。

    cfg 已是「默认 → 技能 → 用户」合并后的结果，因此这里只需按
    primary → candidates 顺序展开；来源层级再回查两个配置文件确定，
    以便 `source show` 能如实标注地址来自用户配置还是技能内置配置。
    """
    if cfg is None:
        cfg, _ = load_registry()
    out: list[tuple[str, str]] = []
    primary = str(cfg.get("primary") or "").strip()
    if primary:
        out.append((primary, _origin_of(primary)))
    for c in cfg.get("candidates") or []:
        if isinstance(c, str) and c.strip():
            out.append((c.strip(), _origin_of(c.strip())))
        elif isinstance(c, dict) and c.get("url"):
            u = str(c["url"]).strip()
            out.append((u, str(c.get("origin") or _origin_of(u))))
    return out


def generated_urls(cfg: dict) -> list[str]:
    """按 hosts × orgs × 仓库名 生成候选地址（配置里没写明时才用这招）。"""
    gen = cfg.get("generated") or {}
    repo = (cfg.get("repo_name") or DEFAULT_REPO).strip().strip("/")
    hosts = [h for h in (gen.get("hosts") or []) if h]
    orgs = [o for o in (gen.get("orgs") or []) if o]
    urls: list[str] = []
    for host in hosts:
        for org in orgs:
            if "/" in repo:                       # repo_name 可能是 org/repo
                path = repo
                urls.append(f"https://{host}/{path}.git")
                break
            urls.append(f"https://{host}/{org}/{repo}.git")
        if "/" in repo:
            continue
        urls.append(f"https://{host}/{repo}.git")
    # 去重保序
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


# --------------------------------------------------------------------------
# 本地已存在副本扫描（自动查找的第 4 级）
# --------------------------------------------------------------------------


def scan_disabled() -> bool:
    """HEIMAN_NO_SCAN=1 时全局关闭本地扫描（所有扫描入口统一遵守）。"""
    return os.environ.get(ENV_NO_SCAN, "").strip().lower() in ("1", "true", "yes")


def scan_local_clones(
    roots: Iterable[str] | None = None,
    max_depth: int | None = None,
    budget: float | None = None,
    cfg: dict | None = None,
) -> dict:
    """有界 BFS 扫描已存在的 heiman-agent 克隆。返回 {found, timed_out, scanned}。

    只认 `backend/heiman/pyproject.toml` 这一个特征文件，命中即停止下潜。
    受三重约束：根目录白名单、深度上限、时间预算，任何一条触顶即结束。
    """
    if cfg is None:
        cfg, _ = load_registry()
    scfg = cfg.get("scan") or {}

    skip = {str(s).lower() for s in (scfg.get("skip_dirs") or DEFAULT_SKIP_DIRS)}
    default_depth = int(max_depth if max_depth is not None else scfg.get("max_depth", 3))
    extra_depth = int(scfg.get("extra_root_depth", 2))
    budget = float(budget if budget is not None else scfg.get("budget_seconds", 10.0))

    if roots is None:
        env_roots = os.environ.get(ENV_SCAN_ROOTS)
        if env_roots and env_roots.strip():
            roots = [r.strip() for r in re.split(r"[;,]", env_roots) if r.strip()]
        else:
            roots = list(scfg.get("roots") or []) + list(scfg.get("extra_roots") or [])
    extra_set = {str(Path(r).expanduser()).rstrip("/").lower() for r in (scfg.get("extra_roots") or [])}

    deadline = time.monotonic() + budget
    found: list[dict] = []
    seen: set[str] = set()
    queue: deque[tuple[Path, int]] = deque()

    for r in roots:
        p = Path(str(r)).expanduser()
        key = str(p).rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        queue.append((p, extra_depth if key in extra_set else default_depth))

    timed_out = False
    while queue:
        if time.monotonic() > deadline:
            timed_out = True
            break
        d, depth = queue.popleft()
        if not d.is_dir():
            continue
        if looks_like_project(d):
            found.append(
                {
                    "path": str(d),
                    "origin": git_origin_url(d),
                    "branch": git_current_branch(d),
                    "kind": "local-clone",
                }
            )
            continue
        if depth <= 0:
            continue
        try:
            children = sorted(d.iterdir())
        except (OSError, PermissionError):
            continue
        for c in children:
            if not c.is_dir() or c.name.startswith("."):
                continue
            if c.name.lower() in skip:
                continue
            key = str(c).rstrip("/").lower()
            if key in seen:
                continue
            seen.add(key)
            queue.append((c, depth - 1))

    return {"found": found, "timed_out": timed_out, "scanned": len(seen)}


def cached_clones(cfg: dict) -> list[dict]:
    """读取状态文件里缓存的扫描结果（未过期才返回）。"""
    cache = read_state().get("scan_cache") or {}
    if not cache.get("found"):
        return []
    hours = float((cfg.get("scan") or {}).get("cache_hours", 24))
    at = float(cache.get("at") or 0)
    if hours > 0 and time.time() - at > hours * 3600:
        return []
    return [f for f in cache["found"] if looks_like_project(Path(str(f.get("path") or "")))]


def remember_clones(found: list[dict]) -> None:
    write_state({"scan_cache": {"at": time.time(), "found": found}})


def git_origin_url(repo: Path) -> str | None:
    """读仓库的 origin 地址。优先直接解析 .git/config（不 spawn 进程）。"""
    try:
        cfg = repo / ".git" / "config"
        if not cfg.is_file():
            gitdir_txt = repo / ".git"
            if gitdir_txt.is_file():                      # worktree / submodule
                m = re.search(r"gitdir:\s*(.+)", gitdir_txt.read_text(encoding="utf-8", errors="replace"))
                if m:
                    p = Path(m.group(1).strip())
                    cfg = (p / "config") if p.is_dir() else (p.parent / "config")
        if cfg.is_file():
            text = cfg.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"\[remote\s+\"origin\"\][^\[]*?url\s*=\s*(\S+)", text, re.S)
            if m:
                return m.group(1).strip()
    except OSError:
        pass
    code, out, _ = _run_git(["-C", str(repo), "remote", "get-url", "origin"], timeout=5)
    if code == 0 and out.strip():
        return out.strip().splitlines()[0].strip()
    return None


def git_current_branch(repo: Path) -> str | None:
    code, out, _ = _run_git(["-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
    out = out.strip()
    return out if code == 0 and out and out != "HEAD" else None


# --------------------------------------------------------------------------
# 远端探测（自动查找的判定手段）
# --------------------------------------------------------------------------


def probe(url: str, branch: str | None = None, timeout: float | None = None, cfg: dict | None = None) -> dict:
    """用 `git ls-remote --heads` 探测远端是否可达，可选校验分支是否存在。"""
    if cfg is None:
        cfg, _ = load_registry()
    timeout = float(timeout if timeout is not None else (cfg.get("probe") or {}).get("timeout_seconds", 6.0))

    ok, err, warn = validate_url(url)
    if not ok:
        return {"url": redact_url(url), "ok": False, "error": err, "warning": warn, "reachable": False}

    code, out, err_out = _run_git(["ls-remote", "--heads", url], timeout=timeout)
    result = {
        "url_display": redact_url(url),   # 与 SourceResult / tried 里其它条目保持同一键名
        "ok": code == 0,
        "reachable": code == 0,
        "warning": warn,
    }
    if code != 0:
        result["error"] = _scrub((err_out or out).strip()[-500:], url) or f"git ls-remote 退出码 {code}"
        return result

    heads = [
        line.split("\t")[-1].replace("refs/heads/", "").strip()
        for line in out.splitlines()
        if "\t" in line
    ]
    result["branches"] = heads[:50]
    if branch:
        result["branch"] = branch
        result["branch_exists"] = branch in heads
        result["ok"] = branch in heads
        if branch not in heads:
            result["error"] = f"远端不存在分支 {branch}（可选分支: {', '.join(heads[:20]) or '无'}）"
    return result


# --------------------------------------------------------------------------
# 源码获取：clone / 更新
# --------------------------------------------------------------------------


@dataclass
class SourceResult:
    ok: bool
    origin: str | None = None          # 来源层级：cli / env / local-clone / state / ...
    url: str | None = None             # 原始 git 地址（含凭据，仅供内部使用）
    url_display: str | None = None     # 脱敏后的地址，可安全输出
    branch: str | None = None
    local_path: str | None = None
    action: str | None = None          # cloned / updated / reused / scanned
    code: int = 0
    error: str | None = None
    hint: str | None = None
    tried: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("url", None)              # 原始地址（可能含凭据）绝不外泄
        tried = []
        for t in self.tried:
            item = dict(t)
            if item.get("url"):         # 二次脱敏，确保任何路径下都不泄漏凭据
                item["url"] = redact_url(str(item["url"]))
            tried.append(item)
        d["tried"] = tried
        return d


def resolve_dest(dest: str | Path | None = None, cfg: dict | None = None) -> Path:
    """解析克隆目标目录。

    支持三种写法：绝对路径 / `~` 开头的家目录 / **相对路径（相对 HOME_DIR）**。
    配置里推荐写相对路径（如 `src/heiman-agent`），这样 `HEIMAN_HOME` 一改，
    venv、数据、日志、源码会整体跟着走，不会出现"venv 在 A、源码在 B"的错位。
    """
    if cfg is None:
        cfg, _ = load_registry()
    raw = dest or (cfg.get("clone") or {}).get("dest") or "src/heiman-agent"
    p = Path(str(raw)).expanduser()
    return p if p.is_absolute() else (HOME_DIR / p)


def ensure_source(
    url: str,
    branch: str | None = None,
    dest: str | Path | None = None,
    update: bool = True,
    depth: int | None = None,
    timeout: float | None = None,
    cfg: dict | None = None,
) -> SourceResult:
    """保证 dest 处有一份 heiman-agent 源码：存在则更新，不存在则克隆。"""
    if cfg is None:
        cfg, _ = load_registry()
    ccfg = cfg.get("clone") or {}
    depth = int(depth if depth is not None else ccfg.get("depth", 1))
    timeout = float(timeout if timeout is not None else ccfg.get("timeout_seconds", 600))

    dest = resolve_dest(dest, cfg)

    ok, err, warn = validate_url(url)
    if not ok:
        return SourceResult(ok=False, error=err, hint=warn, code=1, url=url)

    git = git_bin()
    if not git:
        return SourceResult(
            ok=False,
            url=url,
            error="未检测到 git，无法自动获取源码。",
            hint="请先安装 git 并加入 PATH，或用 --project 指定本地已有的 heiman-agent 源码目录。",
            code=1,
        )

    res = SourceResult(ok=False, url=url, url_display=redact_url(url), branch=branch)

    if (dest / ".git").exists() or looks_like_project(dest):
        origin = git_origin_url(dest) if (dest / ".git").exists() else None
        res.local_path = str(dest)
        if origin and not urls_equal(origin, url):
            res.ok = True
            res.origin = "local-clone"
            res.action = "reused"
            res.url = origin
            res.url_display = redact_url(origin)
            res.hint = (
                f"目标目录已存在另一来源的副本（origin={redact_url(origin)}），已直接复用，未覆盖；"
                f"如需改用 {redact_url(url)}，请手动删除 {dest} 后重试。"
            )
            return res
        res.origin = "local-clone"
        if update and branch:
            code, _, err = _run_git(["-C", str(dest), "fetch", "--depth", str(depth), "origin", branch], timeout=timeout)
            if code == 0:
                code, _, err = _run_git(["-C", str(dest), "checkout", branch], timeout=60)
            res.action = "updated" if code == 0 else "reused"
            if code != 0:
                res.hint = f"更新失败，已保留现有副本：{_scrub(err.strip()[-300:], url)}"
        elif update:
            code, _, err = _run_git(["-C", str(dest), "fetch", "--depth", str(depth), "origin"], timeout=timeout)
            res.action = "updated" if code == 0 else "reused"
        else:
            res.action = "reused"
        res.ok = looks_like_project(dest)
        if not res.ok:
            res.error = f"目录中存在副本，但未找到 backend/heiman/pyproject.toml：{dest}"
            res.code = 3
        return res

    if dest.exists() and any(dest.iterdir()):
        return SourceResult(
            ok=False,
            url=url,
            url_display=redact_url(url),
            error=f"克隆目标目录非空且不是 git 仓库：{dest}",
            hint="请换用 --dest 指定空目录，或清理该目录后重试。",
            code=1,
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    info(f"克隆源码: {redact_url(url)}{f' ({branch})' if branch else ''} -> {dest}")

    attempts: list[list[str]] = []
    base = [git, "clone"]
    if branch:
        attempts.append([*base, "--depth", str(depth), "--branch", branch, url, str(dest)])
        attempts.append([*base, "--branch", branch, url, str(dest)])
    attempts.append([*base, "--depth", str(depth), url, str(dest)])
    attempts.append([*base, url, str(dest)])

    last_err = ""
    for cmd in attempts:
        code, out, err = _run_git(cmd[1:], timeout=timeout)
        last_err = _scrub((err or out).strip()[-800:], url)
        if code == 0:
            res.ok = looks_like_project(dest)
            res.local_path = str(dest)
            res.action = "cloned"
            if not res.ok:
                res.error = (
                    f"克隆成功但目录结构不含 backend/heiman/pyproject.toml：{dest}。"
                    f"请确认这是 heiman-agent 仓库，或用 --project 指定正确的本地源码目录。"
                )
                res.code = 3
            return res
        # 目标目录可能残留半成品，下一次尝试前清掉
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)

    res.error = f"克隆失败：{last_err}"
    res.hint = (
        "检查网络/代理、仓库权限与 git 凭据；"
        f"内网私有仓库建议先 `heiman_ctl.py source set <url>`，或设置环境变量 {ENV_URL}。"
    )
    res.code = 2
    return res


# --------------------------------------------------------------------------
# 统一入口：解析安装源
# --------------------------------------------------------------------------


def resolve_project(explicit: str | None = None, scan: bool | str = "cache") -> Path | None:
    """按优先级定位本地已有的项目根目录。

    顺序：--project > HEIMAN_AGENT_HOME > 状态文件 project_root >
    内置常见安装路径 > 本地克隆扫描（有界）。
    """
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

    if scan and not scan_disabled():
        for f in cached_clones(load_registry()[0]):
            p = Path(str(f.get("path") or ""))
            if p and looks_like_project(p):
                return p
        if scan is True:
            result = scan_local_clones()
            if result["found"]:
                remember_clones(result["found"])
                p = Path(str(result["found"][0].get("path") or ""))
                if looks_like_project(p):
                    return p

    return None


def resolve_source(
    explicit_url: str | None = None,
    branch: str | None = None,
    project: str | Path | None = None,
    dest: str | Path | None = None,
    fetch: bool = True,
    update: bool = True,
    scan: bool | str = True,
    probe_candidates: bool = True,
    cfg: dict | None = None,
) -> SourceResult:
    """按优先级自动查找安装源，并（可选）把源码落到本地。

    scan: True 执行扫描 / "cache" 只用缓存结果 / False 完全不扫描。
    返回 SourceResult；`local_path` 为空表示只解析未落地（fetch=False 的远端源）。
    """
    if cfg is None:
        cfg, _ = load_registry()
    branch = branch or (cfg.get("primary_branch") or "").strip() or None
    dest = resolve_dest(dest, cfg)

    # 1) 命令行 --project：本地已有源码，无需任何远端
    if project:
        p = Path(str(project)).expanduser().resolve()
        if looks_like_project(p):
            return SourceResult(
                ok=True, origin="project", url=git_origin_url(p), url_display=redact_url(git_origin_url(p)),
                branch=git_current_branch(p), local_path=str(p), action="reused",
            )

    candidates: list[dict] = []

    # 2) 命令行 --source：最高优先级
    if explicit_url and explicit_url.strip():
        candidates.append({"url": explicit_url.strip(), "origin": "cli", "branch": branch})

    # 3) 环境变量 HEIMAN_GIT_URL
    env_url = (os.environ.get(ENV_URL) or "").strip()
    if env_url:
        candidates.append({"url": env_url, "origin": "env", "branch": branch})

    # 4) 本地已存在的固定位置（HEIMAN_AGENT_HOME / 内置常见安装路径），免扫描
    if root := resolve_project(None, scan=False):
        candidates.append(
            {
                "url": git_origin_url(root) or "",
                "origin": "local-clone",
                "branch": git_current_branch(root),
                "path": str(root),
            }
        )

    # 5) 本地已存在副本（有界扫描 + 24h 缓存）
    scan_mode = "cache" if scan is None else scan
    if scan_mode and not scan_disabled():
        found = cached_clones(cfg)
        if found:
            for f in found:
                candidates.append({"url": f.get("origin") or "", "origin": "local-clone",
                                   "branch": f.get("branch"), "path": f.get("path")})
        elif scan_mode is True:
            result = scan_local_clones(cfg=cfg)
            if result["found"]:
                remember_clones(result["found"])
                for f in result["found"]:
                    candidates.append({"url": f.get("origin") or "", "origin": "local-clone",
                                       "branch": f.get("branch"), "path": f.get("path")})

    # 6) 状态文件
    state = read_state()
    if state.get("git_url"):
        candidates.append({"url": str(state["git_url"]), "origin": "state", "branch": state.get("git_branch")})
    if state.get("project_root") and looks_like_project(Path(str(state["project_root"]))):
        root = Path(str(state["project_root"]))
        candidates.append({"url": git_origin_url(root) or "", "origin": "state",
                           "branch": git_current_branch(root), "path": str(root)})

    # 7/8) 用户配置与技能内置配置
    for u, origin in configured_urls(cfg):
        candidates.append({"url": u, "origin": origin, "branch": branch})

    # 9) 规则生成候选（兜底，最慢）
    if probe_candidates:
        for u in generated_urls(cfg):
            candidates.append({"url": u, "origin": "generated", "branch": branch})

    tried: list[dict] = []
    seen_norm: set[str] = set()
    probe_timeout = float((cfg.get("probe") or {}).get("timeout_seconds", 6.0))
    budget = float((cfg.get("probe") or {}).get("total_budget_seconds", 40.0))
    deadline = time.monotonic() + budget

    for cand in candidates:
        url = (cand.get("url") or "").strip()
        path = cand.get("path")

        # 本地副本：不需要联网，命中即用
        if path:
            pp = Path(str(path))
            if looks_like_project(pp):
                tried.append(
                    {
                        "origin": cand["origin"],
                        "url_display": redact_url(url) or "(本地副本，未配置 origin)",
                        "path": str(pp),
                        "ok": True,
                        "kind": "local",
                    }
                )
                if fetch and url:
                    res = ensure_source(url, branch=cand.get("branch"), dest=pp, update=update)
                    res.origin = cand["origin"]
                    res.tried = tried
                    return res
                return SourceResult(
                    ok=True, origin=cand["origin"], url=url, url_display=redact_url(url),
                    branch=cand.get("branch"), local_path=str(pp), action="reused", tried=tried,
                )
            continue

        if not url:
            continue
        key = normalize_url(url)
        if key in seen_norm:
            continue
        seen_norm.add(key)

        if not probe_candidates:
            # 不探测 = 信任配置，直接拿来用（离线/内网环境下常用）
            tried.append(
                {
                    "origin": cand["origin"],
                    "url_display": redact_url(url),
                    "ok": True,
                    "reachable": None,
                    "kind": "remote",
                    "note": "未探测（--no-probe），直接使用该地址",
                }
            )
            if fetch:
                res = ensure_source(url, branch=cand.get("branch"), dest=dest, update=update)
                res.origin = cand["origin"]
                res.tried = tried
                return res
            return SourceResult(ok=True, origin=cand["origin"], url=url, url_display=redact_url(url),
                                branch=cand.get("branch"), action="resolved", tried=tried)
        if time.monotonic() > deadline:
            tried.append({"origin": cand["origin"], "url_display": redact_url(url), "ok": False,
                          "error": "探测总预算耗尽，已跳过"})
            continue

        p = probe(url, branch=cand.get("branch"), timeout=probe_timeout, cfg=cfg)
        p["origin"] = cand["origin"]
        p["kind"] = "remote"
        tried.append(p)
        if p.get("ok"):
            if fetch:
                res = ensure_source(url, branch=cand.get("branch"), dest=dest, update=update)
                res.origin = cand["origin"]
                res.tried = tried
                return res
            return SourceResult(ok=True, origin=cand["origin"], url=url, url_display=redact_url(url),
                                branch=cand.get("branch"), action="resolved", tried=tried)

    return SourceResult(
        ok=False,
        code=2,
        error="未能自动定位到可用的 heiman-agent 安装源。",
        hint=(
            "任选其一后重试：\n"
            "  1. `heiman_ctl.py source set <git-url>`（写入用户级配置，推荐）\n"
            f"  2. 设置环境变量 {ENV_URL}（可选 {ENV_BRANCH}）\n"
            "  3. 用 --source <git-url> 显式指定\n"
            "  4. 用 --project <path> 指向本地已有的源码目录"
        ),
        tried=tried,
    )


# --------------------------------------------------------------------------
# 命令行（供调试；正式入口是 heiman_ctl.py 的 install / source 子命令）
# --------------------------------------------------------------------------


import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------
# 安装源模块（同目录；兼容被 heiman_snapshot.py 以文件路径方式 import 的场景）
# --------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


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

# 项目根目录自动探测候选（已内联到本文件（原 heiman_source 的同一份定义））

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


# 说明：`looks_like_project` / `read_state` / `write_state` 已内联（原 heiman_source），
# 两个脚本共用同一份实现与同一个 ~/.heiman/agent.json。


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


def _is_loopback(url: str) -> bool:
    """URL 是否指向本机。"""

    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host in {"127.0.0.1", "localhost", "::1", "[::1]"}


def urlopen_local(req, timeout: float):
    """打开请求；访问本机时强制绕过 http_proxy。

    很多开发机设置了全局 http_proxy（含大写 HTTP_PROXY），代理会把
    `http://127.0.0.1:1912` 一并转发并返回 502，导致健康检查把"被代理拒绝"
    误判成"服务已在运行"。本机地址一律直连，避免这类误判。
    """

    if _is_loopback(req.full_url):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def http_get(url: str, token: str | None = None, timeout: float = 5.0):
    req = urllib.request.Request(url, method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urlopen_local(req, timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        try:
            return resp.status, json.loads(body)
        except json.JSONDecodeError:
            return resp.status, body


def health(host: str, port: int, timeout: float = 5.0) -> dict:
    try:
        status, body = http_get(f"http://{host}:{port}/health", timeout=timeout)
        # 只有 2xx 才算健康响应；4xx/5xx（含代理返回的 502）不算服务在运行。
        ok = 200 <= int(status) < 300
        return {"reachable": ok, "status_code": status, "body": body}
    except urllib.error.HTTPError as e:
        code = e.code
        return {
            "reachable": 200 <= int(code) < 300,
            "status_code": code,
            "body": e.read().decode("utf-8", "replace"),
        }
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
    project = resolve_project(args.project, scan=True)
    cfg, layers = load_registry()
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
            "source": {
                "git_url": redact_url(
                    str(cfg.get("primary") or "")
                    or str(read_state().get("git_url") or "")
                )
                or None,
                "branch": cfg.get("primary_branch") or None,
                "clone_dest": cfg.get("clone", {}).get("dest") or str(DEFAULT_DEST),
                "config_layers": layers,
            },
        },
        0 if project else 1,
    )


def cmd_doctor(args) -> int:
    project = resolve_project(args.project, scan=True)
    host, port = runtime_settings(project)
    cfg, _ = load_registry()
    checks = {
        "python": {"ok": sys.version_info >= (3, 10), "value": sys.version.split()[0]},
        "project_root": {"ok": project is not None, "value": str(project) if project else None},
        "venv_ready": {"ok": venv_python().is_file(), "value": str(venv_python())},
        "port_free": {
            "ok": not port_open(host, port),
            "value": f"{host}:{port}",
            "note": "占用中说明服务可能已在运行",
        },
        "git": {
            "ok": shutil.which("git") is not None,
            "value": shutil.which("git"),
            "note": "自动安装（git clone）需要 git",
        },
        "git_source": {
            "ok": bool((cfg.get("primary") or "").strip())
            or bool(read_state().get("git_url"))
            or project is not None,
            "value": redact_url(
                str(cfg.get("primary") or "")
                or str(read_state().get("git_url") or "")
                or (str(project) if project else "")
            )
            or None,
            "note": "为空时自动安装会退化为本地扫描/规则探测，见 SKILL.md 的「安装源自动查找」章节",
        },
    }
    ok = checks["python"]["ok"] and checks["project_root"]["ok"]
    return emit({"ok": ok, "checks": checks}, 0 if ok else 1)


def cmd_install(args) -> int:
    project = resolve_project(args.project, scan=True)
    source_info: dict | None = None

    if not project:
        # 本地没有源码 —— 自动查找 git 地址并克隆，无需手动指定安装来源
        info("本地未发现 heiman-agent 源码，开始自动定位安装源…")
        res = resolve_source(
            explicit_url=getattr(args, "source", None),
            branch=getattr(args, "branch", None),
            dest=getattr(args, "dest", None),
            fetch=True,
            update=not getattr(args, "no_update", False),
            scan=True,
            probe_candidates=not getattr(args, "no_probe", False),
        )
        source_info = res.to_dict()
        if not res.ok or not res.local_path:
            return fail(
                res.error or "自动定位安装源失败。",
                res.code or 2,
                hint=res.hint,
                source=source_info,
                probed=[str(p) for p in PROJECT_CANDIDATES],
            )
        project = Path(res.local_path).resolve()
        info(f"已获取源码: {project}")

    host, port = runtime_settings(project)
    steps: list[dict] = []
    if source_info:
        steps.append(
            {
                "step": "resolve-source",
                "ok": True,
                "output": f"{source_info.get('origin')} -> "
                          f"{source_info.get('url_display')} ({source_info.get('action')})",
            }
        )

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
        # 关键：模板里的 HEIMAN_APP_ID=your_app_id 是占位符，会覆盖源码内置默认值 11，
        # 导致查不到账号。生成 .env 时先把这行注释掉，让用户「不动 .env 也不会踩坑」。
        sanitized, dropped_placeholder = [], False
        for line in content.splitlines():
            s = line.strip()
            if s.startswith("HEIMAN_APP_ID=") and not s.partition("=")[2].strip().isdigit():
                sanitized.append(
                    "# HEIMAN_APP_ID 已注释：模板占位符会覆盖内置默认值 11。"
                    "确认自己的 appId 不为 11 时再取消注释并填真实数值"
                )
                dropped_placeholder = True
                continue
            sanitized.append(line)
        if dropped_placeholder:
            content = "\n".join(sanitized)
        if "SERVER_HOST=" not in content:
            content += f"\nSERVER_HOST={host}\nSERVER_PORT={port}\nSERVER_RELOAD=false\n"
        env_file.write_text(content, encoding="utf-8")
        steps.append({
            "step": "dotenv",
            "ok": True,
            "output": f"已生成 {env_file}"
                      + ("（已注释 HEIMAN_APP_ID 占位符）" if dropped_placeholder else "")
                      + "；绑定账号二选一：A 打开 http://127.0.0.1:1912 在 Web 界面登录，"
                        "B 把账号密码交给 Agent 执行 env set",
        })
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

    state_extra: dict = {"project_root": str(project), "host": host, "port": port, "venv_python": py}
    if source_info:
        state_extra["git_url"] = source_info.get("url_display")
        state_extra["git_branch"] = source_info.get("branch")
        state_extra["source_origin"] = source_info.get("origin")
    elif project:
        state_extra["git_url"] = redact_url(git_origin_url(project))
        state_extra["git_branch"] = git_current_branch(project)
    write_state(state_extra)

    return emit(
        {
            "ok": backend_ok,
            "project_root": str(project),
            "venv": str(VENV_DIR),
            "steps": steps,
            "source": source_info,
            "next": [
                "启动服务: python scripts/heiman_ctl.py start",
                "绑定账号（用 AskUserQuestion 让用户二选一）: "
                "A 打开 http://127.0.0.1:1912 在 Web 界面登录；"
                "B 用户提供账号密码，Agent 执行 env set --email <账号> [--password <密码>]",
                "两条路径最后都需一次 OAuth 浏览器授权（token 唯一来源）",
            ],
        },
        0 if backend_ok else 1,
    )


def cmd_start(args) -> int:
    project = resolve_project(args.project, scan="cache")
    if not project:
        return fail(
            "未找到 heiman-agent 项目根目录。",
            hint="先运行 `python scripts/heiman_ctl.py install` —— 它会自动查找 git 地址并克隆源码；"
                 "若源码已在本地，可用 --project <路径> 指定。",
        )

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
        with urlopen_local(req, timeout=args.timeout) as resp:
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


def cmd_source(args) -> int:
    """安装源自动查找 / 探测 / 同步 / 配置。"""
    cfg, layers = load_registry()
    action = args.action

    if action == "show":
        project = resolve_project(None, scan=True)
        res = resolve_source(fetch=False, scan=True, probe_candidates=True, cfg=cfg)
        return emit(
            {
                "ok": True,
                "project_root": str(project) if project else None,
                "resolved": res.to_dict(),
                "clone_dest": (cfg.get("clone") or {}).get("dest") or str(DEFAULT_DEST),
                "config_layers": layers,
                "env": {
                    ENV_URL: bool(os.environ.get(ENV_URL)),
                    ENV_BRANCH: os.environ.get(ENV_BRANCH) or None,
                },
            }
        )

    if action == "probe":
        if args.url:
            r = probe(args.url, args.branch, args.timeout, cfg)
            return emit(r, 0 if r.get("ok") else 2)
        urls = [u for u, _ in configured_urls(cfg)]
        if not urls:
            urls = generated_urls(cfg)
        if not urls:
            return emit(
                {
                    "ok": False,
                    "error": "没有可探测的地址。",
                    "hint": f"用 `source set <git-url>` 指定仓库，或设置环境变量 {ENV_URL}。",
                },
                1,
            )
        results = [probe(u, args.branch, args.timeout, cfg) for u in urls]
        return emit({"ok": any(r.get("ok") for r in results), "results": results},
                    0 if any(r.get("ok") for r in results) else 2)

    if action == "scan":
        out = scan_local_clones(roots=args.root, max_depth=args.max_depth,
                                       budget=args.budget, cfg=cfg)
        if out["found"]:
            remember_clones(out["found"])
        return emit({"ok": bool(out["found"]), **out}, 0 if out["found"] else 1)

    if action == "sync":
        res = resolve_source(
            explicit_url=args.url, branch=args.branch, dest=args.dest,
            fetch=True, update=not args.no_update, scan=True,
            probe_candidates=not args.no_probe, cfg=cfg,
        )
        return emit(res.to_dict(), res.code)

    if action == "set":
        ok, err, warn = validate_url(args.url)
        if not ok:
            return fail(err, 1, warning=warn)
        data = _load_json(USER_CONFIG)
        data["primary"] = args.url.strip()
        if args.branch:
            data["primary_branch"] = args.branch.strip()
        USER_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        USER_CONFIG.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return emit(
            {
                "ok": True,
                "path": str(USER_CONFIG),
                "primary": redact_url(data["primary"]),
                "primary_branch": data.get("primary_branch") or "",
                "warning": warn,
            }
        )

    if action == "clear":
        if USER_CONFIG.is_file():
            USER_CONFIG.unlink()
            return emit({"ok": True, "removed": str(USER_CONFIG)})
        return emit({"ok": True, "removed": None, "note": "用户级安装源配置不存在，无需清理"})

    return fail(f"未知的 source 子命令: {action}", 1)


# --------------------------------------------------------------------------
# .env 凭据（路径 B：用户把账号密码交给 Agent，由脚本代写）
# --------------------------------------------------------------------------

ENV_CRED_KEYS = ("HEIMAN_EMAIL", "HEIMAN_PASSWORD")
ENV_TRAP_KEY = "HEIMAN_APP_ID"
ENV_TRAP_PLACEHOLDER = "your_app_id"

_ENV_HINT = (
    "注意：写 .env 不会免除浏览器授权。海曼云端取数的 token 只能由 OAuth2 换取，"
    "下一步仍需用户在浏览器登录一次（Web 界面点登录，或 env auth-url 取授权地址）。"
)


def _env_file(project: Path | None) -> Path | None:
    if not project:
        return None
    return project / "backend" / "heiman" / ".env"


def _mask(value: str) -> str:
    """凭据脱敏：邮箱保留首字母与域名，普通串保留首尾各一位。"""
    if not value:
        return ""
    if "@" in value:
        name, _, domain = value.partition("@")
        return f"{name[:1]}{'*' * max(len(name) - 1, 1)}@{domain}"
    if len(value) <= 2:
        return "*" * len(value)
    return f"{value[:1]}{'*' * (len(value) - 2)}{value[-1:]}"


def _is_placeholder(value: str) -> bool:
    v = (value or "").strip()
    return (not v) or v.startswith("your_") or v in ("changeme", "xxx")


def _read_env(env_file: Path) -> tuple[list[str], dict[str, str]]:
    """返回 (原始行, {key: value})；文件不存在时返回空。"""
    if not env_file.is_file():
        return [], {}
    lines = env_file.read_text(encoding="utf-8", errors="replace").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        values[k.strip()] = v.strip().strip('"').strip("'")
    return lines, values


def _write_env(env_file: Path, lines: list[str]) -> None:
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def _upsert(lines: list[str], key: str, value: str) -> list[str]:
    """设置 key=value：已存在则原地替换（保留注释与顺序），不存在则追加。"""
    out, hit = [], False
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s and s.partition("=")[0].strip() == key:
            out.append(f"{key}={value}")
            hit = True
        else:
            out.append(line)
    if not hit:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")
    return out


def _drop(lines: list[str], key: str) -> tuple[list[str], str | None]:
    """删除指定 key 整行，返回 (新行, 被删掉的旧值)。"""
    out, removed = [], None
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s and s.partition("=")[0].strip() == key:
            removed = s.partition("=")[2].strip()
            continue
        out.append(line)
    return out, removed


def cmd_env(args) -> int:
    action = args.action
    project = resolve_project(args.project, scan=True)
    if not project:
        return fail("未找到 heiman-agent 项目根目录，请先执行 install。", 1)
    env_file = _env_file(project)
    lines, values = _read_env(env_file)

    if action == "show":
        trap = values.get(ENV_TRAP_KEY)
        return emit(
            {
                "ok": True,
                "env_file": str(env_file),
                "exists": env_file.is_file(),
                "credentials": {
                    "HEIMAN_EMAIL": _mask(values.get("HEIMAN_EMAIL", "")),
                    "HEIMAN_PASSWORD": "******" if values.get("HEIMAN_PASSWORD") else "",
                    "configured": bool(values.get("HEIMAN_EMAIL")) and not _is_placeholder(values.get("HEIMAN_EMAIL", "")),
                },
                "app_id": {
                    "value": trap if (trap and trap.isdigit()) else (trap or None),
                    "is_placeholder": bool(trap) and not str(trap).isdigit(),
                    "note": "占位符会覆盖源码内置默认值 11，导致查不到账号；env set 会自动删掉它",
                },
                "hint": _ENV_HINT,
            }
        )

    if action == "set":
        email = (args.email or "").strip()
        password = (args.password or "").strip()
        if not email:
            return fail("缺少 --email；不确定账号时改用路径 A（Web 界面绑定，无需凭据）。", 1)
        changed: list[str] = []

        old_email = values.get("HEIMAN_EMAIL", "")
        if email != old_email:
            lines = _upsert(lines, "HEIMAN_EMAIL", email)
            changed.append(f"HEIMAN_EMAIL: {_mask(old_email) or '(空)'} -> {_mask(email)}")

        if password:
            changed.append("HEIMAN_PASSWORD: ****** （已写入，后端当前不使用密码）")
            lines = _upsert(lines, "HEIMAN_PASSWORD", password)

        # 关键：删掉 HEIMAN_APP_ID 占位符，让源码内置默认值 11 生效
        app_id = values.get(ENV_TRAP_KEY)
        removed_app_id = None
        if app_id is not None and not str(app_id).strip().isdigit():
            lines, removed_app_id = _drop(lines, ENV_TRAP_KEY)
            changed.append(f"已删除 HEIMAN_APP_ID={removed_app_id}（占位符，改回内置默认值 11）")
        elif app_id is not None:
            changed.append(f"保留 HEIMAN_APP_ID={app_id}（已是真实数值）")

        _write_env(env_file, lines)
        return emit(
            {
                "ok": True,
                "env_file": str(env_file),
                "changed": changed,
                "app_id_effective": app_id if (app_id and str(app_id).strip().isdigit()) else "11 (源码内置默认值)",
                "next": [
                    "python scripts/heiman_ctl.py restart",
                    "然后仍需一次 OAuth 浏览器授权（token 唯一来源）",
                ],
                "hint": _ENV_HINT,
            }
        )

    if action == "clear":
        lines = _upsert(lines, "HEIMAN_EMAIL", "your_email@example.com")
        lines = _upsert(lines, "HEIMAN_PASSWORD", "your_password")
        _write_env(env_file, lines)
        return emit({"ok": True, "env_file": str(env_file), "changed": ["凭据已重置为模板占位符"]})

    if action == "auth-url":
        host, port = runtime_settings(project)
        url = f"http://127.0.0.1:{port}/api/auth/login"
        payload: dict[str, object] = {"ok": False, "login_endpoint": url}
        try:
            import urllib.error
            import urllib.request

            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            req = urllib.request.Request(url, method="POST", data=b"{}")
            req.add_header("Content-Type", "application/json")
            with opener.open(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            authorize = data.get("authorize_url") or data.get("url")
            payload["ok"] = bool(authorize)
            payload["authorize_url"] = authorize
            if not authorize:
                payload["raw"] = data
        except Exception as e:  # noqa: BLE001 - 排障需要原始异常
            payload["error"] = f"{type(e).__name__}: {e}"
            payload["hint"] = "服务未运行时先执行: python scripts/heiman_ctl.py start"
        payload["hint_next"] = "把 authorize_url 发给用户，浏览器打开 → 海曼账号登录 → 自动回调换取 token"
        return emit(payload, 0 if payload.get("ok") else 1)

    return fail(f"未知的 env 子命令: {action}", 1)


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

    sp = sub.add_parser(
        "install",
        help="自动定位安装源（必要时 git clone）并创建 venv 安装依赖",
        description="本地已有源码则直接安装；没有则按优先级自动查找 git 地址、克隆后再安装。",
    )
    sp.add_argument("--force", action="store_true", help="强制重建虚拟环境")
    sp.add_argument("--source", help="显式指定 git 地址（默认自动查找）")
    sp.add_argument("--branch", help="指定分支 / 标签（默认仓库默认分支）")
    sp.add_argument("--dest", help=f"克隆目标目录（默认 {DEFAULT_DEST}）")
    sp.add_argument("--no-update", action="store_true", help="已有副本时不拉取更新")
    sp.add_argument("--no-probe", action="store_true", help="只取配置地址，不做远端可达性探测")
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

    sp = sub.add_parser(
        "env",
        help="查看 / 代写 backend/heiman/.env 凭据（路径 B）与生成 OAuth 授权地址",
        description="用户把海曼账号密码交给 Agent 时走这里：脚本自动写入并删掉 HEIMAN_APP_ID 占位符。"
                    "注意写 .env 不等于完成绑定，token 仍只能由 OAuth2 换取。",
    )
    esub = sp.add_subparsers(dest="action", required=True)
    esub.add_parser("show", help="显示 .env 凭据状态（脱敏）").set_defaults(func=cmd_env)
    sp_set = esub.add_parser("set", help="写入 HEIMAN_EMAIL / HEIMAN_PASSWORD")
    sp_set.add_argument("--email", required=True, help="海曼账号邮箱")
    sp_set.add_argument("--password", help="海曼账号密码（后端当前不使用，可选）")
    sp_set.set_defaults(func=cmd_env)
    esub.add_parser("clear", help="把凭据重置回模板占位符").set_defaults(func=cmd_env)
    esub.add_parser("auth-url", help="生成 OAuth2 授权地址（服务需已启动）").set_defaults(func=cmd_env)

    sp = sub.add_parser(
        "source",
        help="安装源自动查找 / 探测 / 同步 / 配置",
        description="查看与调试「git 地址从哪来」，见 SKILL.md 的「安装源自动查找」章节。",
    )
    ssub = sp.add_subparsers(dest="action", required=True)

    ssub.add_parser("show", help="显示当前自动查找到的安装源").set_defaults(func=cmd_source)
    sp_probe = ssub.add_parser("probe", help="探测候选 git 地址的可达性")
    sp_probe.add_argument("--url", help="只探测指定地址")
    sp_probe.add_argument("--branch")
    sp_probe.add_argument("--timeout", type=float)
    sp_probe.set_defaults(func=cmd_source)
    sp_scan = ssub.add_parser("scan", help="扫描本地已存在的 heiman-agent 克隆")
    sp_scan.add_argument("--root", action="append", help="额外扫描根目录，可重复")
    sp_scan.add_argument("--max-depth", type=int)
    sp_scan.add_argument("--budget", type=float, help="扫描时间预算（秒）")
    sp_scan.set_defaults(func=cmd_source)
    sp_sync = ssub.add_parser("sync", help="只拉取/更新源码，不装依赖")
    sp_sync.add_argument("--url")
    sp_sync.add_argument("--branch")
    sp_sync.add_argument("--dest")
    sp_sync.add_argument("--no-update", action="store_true")
    sp_sync.add_argument("--no-probe", action="store_true")
    sp_sync.set_defaults(func=cmd_source)
    sp_set = ssub.add_parser("set", help="把地址写入 ~/.heiman/config/install-sources.json")
    sp_set.add_argument("url")
    sp_set.add_argument("--branch")
    sp_set.set_defaults(func=cmd_source)
    ssub.add_parser("clear", help="清除用户级安装源配置").set_defaults(func=cmd_source)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
