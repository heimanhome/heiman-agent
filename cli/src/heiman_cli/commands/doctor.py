"""doctor 命令：环境诊断，检测防火墙、WSL 网络配置和后端连接状态。"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import click

from heiman_cli.client import api_get
from heiman_cli.output import print_result


class Status(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CheckResult:
    name: str
    status: Status
    message: str
    fix_hint: str | None = None


def _is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except (FileNotFoundError, PermissionError):
        return False


def _detect_platform() -> str:
    if platform.system() == "Darwin":
        return "macos"
    if _is_wsl():
        return "wsl"
    if platform.system() == "Linux":
        return "linux"
    return "unknown"


@dataclass
class CmdResult:
    found: bool
    rc: int
    stdout: str
    stderr: str


_NOT_FOUND = CmdResult(found=False, rc=-1, stdout="", stderr="")


def _run_cmd(cmd: list[str], timeout: int = 5) -> CmdResult:
    if not shutil.which(cmd[0]):
        return _NOT_FOUND
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
        return CmdResult(found=True, rc=r.returncode, stdout=r.stdout, stderr=r.stderr)
    except (subprocess.TimeoutExpired, OSError):
        return CmdResult(found=True, rc=-1, stdout="", stderr="")


def check_firewall() -> list[CheckResult]:
    plat = _detect_platform()
    results: list[CheckResult] = []

    if plat == "macos":
        results.append(CheckResult(
            name="防火墙 (macOS)",
            status=Status.PASS,
            message="macOS 默认不阻断 UDP 入站回包，通常无需配置",
        ))
        return results

    ufw_result = _run_cmd(["ufw", "status"])
    if not ufw_result.found:
        pass
    elif ufw_result.rc != 0:
        results.append(CheckResult(
            name="ufw 状态",
            status=Status.WARN,
            message="ufw 已安装但无法读取状态（权限不足），请用 sudo 重试",
            fix_hint="sudo ufw status verbose",
        ))
        return results
    elif ufw_result.rc == 0:
        out = ufw_result.stdout
        if "inactive" in out.lower():
            results.append(CheckResult(
                name="ufw 状态",
                status=Status.PASS,
                message="ufw 未激活，不阻断流量",
            ))
        elif "status: active" in out.lower():
            verbose = _run_cmd(["ufw", "status", "verbose"])
            out2 = verbose.stdout if verbose.found and verbose.rc == 0 else ""
            if "deny (incoming)" in out2.lower() or "reject (incoming)" in out2.lower():
                results.append(CheckResult(
                    name="ufw UDP 入站",
                    status=Status.FAIL,
                    message="ufw 默认拒绝入站流量，传感器 UDP 包会被丢弃",
                    fix_hint=(
                        "允许局域网 UDP 入站（推荐，限定子网）:\n"
                        "  sudo ufw allow from 192.168.0.0/16 proto udp\n"
                        "\n"
                        "或允许所有 UDP 入站（宽松）:\n"
                        "  sudo ufw allow proto udp from any"
                    ),
                ))
            else:
                results.append(CheckResult(
                    name="ufw UDP 入站",
                    status=Status.PASS,
                    message="ufw 默认允许入站流量",
                ))
        else:
            results.append(CheckResult(
                name="ufw 状态",
                status=Status.WARN,
                message="ufw 输出格式无法识别，请手动检查: sudo ufw status verbose",
            ))
        return results

    fwd_result = _run_cmd(["firewall-cmd", "--state"])
    if not fwd_result.found:
        pass
    elif fwd_result.rc != 0 and "not running" in (fwd_result.stdout + fwd_result.stderr).lower():
        pass
    elif fwd_result.rc != 0:
        results.append(CheckResult(
            name="firewalld 状态",
            status=Status.WARN,
            message="firewalld 已安装但无法读取状态（权限不足），请用 sudo 重试",
            fix_hint="sudo firewall-cmd --state",
        ))
        return results
    elif fwd_result.rc == 0 and "running" in fwd_result.stdout.lower():
        zone_result = _run_cmd(["firewall-cmd", "--get-default-zone"])
        zone = zone_result.stdout.strip()
        if zone_result.rc != 0 or not zone:
            results.append(CheckResult(
                name="firewalld UDP 入站",
                status=Status.WARN,
                message="无法获取 firewalld 默认 zone（权限不足或命令异常），请手动检查",
                fix_hint="sudo firewall-cmd --get-default-zone\nsudo firewall-cmd --list-all",
            ))
            return results
        info_result = _run_cmd(["firewall-cmd", f"--zone={zone}", "--list-all"])
        info = info_result.stdout
        info_lower = info.lower()
        lines = info_lower.splitlines()
        target_line = next((ln for ln in lines if "target:" in ln), "")
        if "drop" in target_line or "reject" in target_line:
            results.append(CheckResult(
                name="firewalld UDP 入站",
                status=Status.FAIL,
                message=f"firewalld zone '{zone}' 目标为 DROP/REJECT，UDP 入站被丢弃",
                fix_hint=(
                    f"允许局域网 UDP（推荐）:\n"
                    f"  sudo firewall-cmd --zone={zone} --add-rich-rule="
                    f"'rule family=ipv4 source address=192.168.0.0/16 protocol value=udp accept' --permanent\n"
                    f"  sudo firewall-cmd --reload"
                ),
            ))
        elif "accept" in target_line:
            results.append(CheckResult(
                name="firewalld UDP 入站",
                status=Status.PASS,
                message=f"firewalld zone '{zone}' 允许 UDP 流量",
            ))
        else:
            results.append(CheckResult(
                name="firewalld UDP 入站",
                status=Status.WARN,
                message=f"firewalld zone '{zone}' target 为 default，未找到显式 UDP 放行规则",
                fix_hint=(
                    f"确认 UDP 是否放行:\n"
                    f"  sudo firewall-cmd --zone={zone} --list-all"
                ),
            ))
        return results

    ipt_result = _run_cmd(["iptables", "-L", "INPUT", "-n"])
    if not ipt_result.found:
        pass
    elif ipt_result.rc != 0:
        results.append(CheckResult(
            name="iptables 状态",
            status=Status.WARN,
            message="iptables 已安装但无法读取规则（权限不足），请用 sudo 重试",
            fix_hint="sudo iptables -L INPUT -n",
        ))
        return results
    elif ipt_result.rc == 0:
        out = ipt_result.stdout
        lines = out.splitlines()
        policy_drop = bool(
            lines and ("policy drop" in lines[0].lower() or "policy reject" in lines[0].lower())
        )
        has_udp_block = any(
            "udp" in line.lower() and ("drop" in line.lower() or "reject" in line.lower())
            for line in lines
        )
        has_blanket_accept = any(
            "accept" in line.lower()
            and "all" in line.lower().split()
            and "established" not in line.lower()
            for line in lines[1:]
        )
        if has_udp_block or (policy_drop and not has_blanket_accept):
            msg = (
                "iptables INPUT 链默认策略为 DROP 且无 ACCEPT 规则" if policy_drop and not has_udp_block
                else "iptables INPUT 链存在 DROP/REJECT UDP 规则"
            )
            results.append(CheckResult(
                name="iptables UDP 入站",
                status=Status.FAIL,
                message=f"{msg}，传感器 UDP 包会被丢弃",
                fix_hint=(
                    "允许局域网 UDP 入站:\n"
                    "  sudo iptables -I INPUT -p udp -s 192.168.0.0/16 -j ACCEPT\n"
                    "\n"
                    "持久化（Ubuntu/Debian）:\n"
                    "  sudo apt install iptables-persistent && sudo netfilter-persistent save"
                ),
            ))
        else:
            results.append(CheckResult(
                name="iptables UDP 入站",
                status=Status.PASS,
                message="iptables INPUT 链未阻断 UDP 入站",
            ))
        return results

    results.append(CheckResult(
        name="防火墙",
        status=Status.PASS,
        message="未检测到 ufw、firewalld 或 iptables，UDP 入站不受防火墙限制",
    ))
    return results


def check_wsl() -> list[CheckResult]:
    if not _is_wsl():
        return []

    results: list[CheckResult] = []

    wslconfig = _get_wslconfig_path()
    if wslconfig and wslconfig.exists():
        content = wslconfig.read_text(errors="ignore")
        mirrored = False
        in_wsl2 = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("["):
                in_wsl2 = stripped.lower() == "[wsl2]"
                continue
            if stripped.startswith("#") or stripped.startswith(";"):
                continue
            if in_wsl2 and "networkingmode" in stripped.replace(" ", "").lower():
                if "=mirrored" in stripped.replace(" ", "").lower():
                    mirrored = True
                    break
        if mirrored:
            results.append(CheckResult(
                name="WSL 网络模式",
                status=Status.PASS,
                message="已启用镜像网络模式 (networkingMode=mirrored)",
            ))
        else:
            results.append(CheckResult(
                name="WSL 网络模式",
                status=Status.FAIL,
                message="未启用镜像网络模式，WSL 无法接收宿主机局域网 UDP 包",
                fix_hint=(
                    "在 Windows 侧编辑 %USERPROFILE%\\.wslconfig:\n"
                    "  [wsl2]\n"
                    "  networkingMode=mirrored\n"
                    "\n"
                    "保存后执行: wsl --shutdown && wsl"
                ),
            ))
    elif wslconfig:
        results.append(CheckResult(
            name="WSL 网络模式",
            status=Status.FAIL,
            message=f".wslconfig 不存在 ({wslconfig})，默认 NAT 模式无法接收局域网 UDP",
            fix_hint=(
                "创建 %USERPROFILE%\\.wslconfig:\n"
                "  [wsl2]\n"
                "  networkingMode=mirrored\n"
                "\n"
                "保存后执行: wsl --shutdown && wsl"
            ),
        ))
    else:
        results.append(CheckResult(
            name="WSL 网络模式",
            status=Status.WARN,
            message="无法定位 .wslconfig（Windows 用户目录检测失败）",
            fix_hint=(
                "请手动确认 %USERPROFILE%\\.wslconfig 中有:\n"
                "  [wsl2]\n"
                "  networkingMode=mirrored"
            ),
        ))

    return results


def _get_wslconfig_path() -> Path | None:
    ps_result = _run_cmd(
        [
            "powershell.exe", "-NoProfile", "-Command",
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $env:USERPROFILE",
        ],
        timeout=15,
    )
    if ps_result.found and ps_result.rc == 0:
        profile = ps_result.stdout.strip().lstrip("\ufeff")
        if profile:
            wsl_result = _run_cmd(["wslpath", "-u", profile])
            if wsl_result.found and wsl_result.rc == 0 and wsl_result.stdout.strip():
                return Path(wsl_result.stdout.strip()) / ".wslconfig"

    users_dir = Path("/mnt/c/Users")
    skip = {"Public", "Default", "Default User", "All Users"}
    try:
        if not users_dir.exists():
            return None

        def _safe_mtime(p: Path) -> float:
            try:
                return p.stat().st_mtime
            except OSError:
                return 0

        dirs = sorted(
            (d for d in users_dir.iterdir() if d.is_dir() and d.name not in skip),
            key=_safe_mtime,
            reverse=True,
        )
        for d in dirs:
            p = d / ".wslconfig"
            if p.exists():
                return p
        if dirs:
            return dirs[0] / ".wslconfig"
    except OSError:
        pass
    return None


def check_backend() -> list[CheckResult]:
    results: list[CheckResult] = []

    try:
        health = api_get("/health")
        results.append(CheckResult(
            name="后端健康检查",
            status=Status.PASS,
            message=f"Heiman Agent 运行正常，状态: {health.get('status', 'healthy')}",
        ))
    except Exception as e:
        results.append(CheckResult(
            name="后端健康检查",
            status=Status.FAIL,
            message=f"无法连接到 Heiman Agent 后端: {e}",
            fix_hint="请确认后端服务已启动: heiman-cli service start",
        ))
        return results

    try:
        sensors = api_get("/api/sensors")
        online_count = sum(1 for s in sensors if s.get("status") != "OFFLINE")
        results.append(CheckResult(
            name="传感器连接",
            status=Status.PASS if online_count > 0 else Status.WARN,
            message=f"已发现 {len(sensors)} 个传感器，{online_count} 个在线",
            fix_hint=None if online_count > 0 else "请检查传感器设备是否在线",
        ))
    except Exception as e:
        results.append(CheckResult(
            name="传感器连接",
            status=Status.WARN,
            message=f"无法获取传感器列表: {e}",
        ))

    try:
        events = api_get("/api/events")
        results.append(CheckResult(
            name="事件服务",
            status=Status.PASS,
            message=f"事件服务正常，共 {len(events)} 条事件记录",
        ))
    except Exception as e:
        results.append(CheckResult(
            name="事件服务",
            status=Status.WARN,
            message=f"无法获取事件列表: {e}",
        ))

    try:
        rules = api_get("/api/rules")
        results.append(CheckResult(
            name="规则引擎",
            status=Status.PASS,
            message=f"规则引擎正常，共 {len(rules)} 条规则",
        ))
    except Exception as e:
        results.append(CheckResult(
            name="规则引擎",
            status=Status.WARN,
            message=f"无法获取规则列表: {e}",
        ))

    return results


_STATUS_ICON = {
    Status.PASS: "✅",
    Status.WARN: "⚠️ ",
    Status.FAIL: "❌",
}


def _render_result(r: CheckResult) -> None:
    icon = _STATUS_ICON[r.status]
    click.echo(f"  {icon} {r.name}")
    click.echo(f"     {r.message}")
    if r.fix_hint:
        click.echo()
        click.echo("     \U0001f4a1 修复建议:")
        for line in r.fix_hint.split("\n"):
            click.echo(f"        {line}")
    click.echo()


def _render_summary(results: list[CheckResult]) -> None:
    click.echo("─" * 50)
    counts = {s: 0 for s in Status}
    for r in results:
        counts[r.status] += 1
    parts = []
    if counts[Status.PASS]:
        parts.append(f"✅ {counts[Status.PASS]} pass")
    if counts[Status.WARN]:
        parts.append(f"⚠️  {counts[Status.WARN]} warn")
    if counts[Status.FAIL]:
        parts.append(f"❌ {counts[Status.FAIL]} fail")
    click.echo(f"  {' / '.join(parts)}")
    click.echo()


@click.command("doctor")
@click.option("--json", is_flag=True, help="JSON 格式输出（用于脚本）")
def doctor_cmd(json):
    """环境诊断：检测防火墙、WSL 网络和后端连接状态。"""
    all_results: list[CheckResult] = []

    for r in check_firewall():
        all_results.append(r)

    for r in check_wsl():
        all_results.append(r)

    for r in check_backend():
        all_results.append(r)

    if json:
        output = {
            "status": "healthy" if all(r.status == Status.PASS for r in all_results) else "unhealthy",
            "checks": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "fix_hint": r.fix_hint,
                }
                for r in all_results
            ],
        }
        print_result(output, pretty=True)
    else:
        click.echo()
        click.echo("\U0001fa7a Heiman Agent 环境诊断")
        click.echo("─" * 50)

        for r in all_results:
            _render_result(r)

        _render_summary(all_results)

    if any(r.status == Status.FAIL for r in all_results):
        raise SystemExit(1)