#!/usr/bin/env bash
# workflow.sh — 海曼智能家居管家 · 标准工作流模式
# 用途：一条命令完成「探活 -> 取数 -> 输出归一化快照 JSON」，
#       供智能体工作流或 CI 定时任务直接调用。
# 依赖：python 3.10+（无第三方依赖）
# 用法：
#   ./workflow.sh                   # 默认取实时快照（中文文案）
#   ./workflow.sh --hours 168       # 附带 7 天历史趋势
#   ./workflow.sh --lang en-US      # 英文文案（英文提问时必带）
#   ./workflow.sh --port 1913       # 服务需启动在非默认端口时（仅影响 start）
#   ./workflow.sh --auto-install    # 源码缺失时自动查找 git 地址并克隆安装
#   ./workflow.sh --source <url> --branch <b>   # 指定安装源（默认自动查找）
#
# 说明：--port 只会传给 start。start 会把端口写入 ~/.heiman/agent.json，
#       status 与 snapshot 都从该状态文件读取端口，因此它们不接受 --port。
#       --lang 会透传给 snapshot，取值 zh-CN / en-US。
#       --auto-install / --source / --branch 只在需要安装时生效。
#
# 兼容性：在 Windows 的 Git Bash / MSYS2 下，`pwd` 返回 /c/... 形式，直接交给
#         原生 python.exe 会被 MSYS 改写成 C:\c\... 而报「找不到文件」。
#         因此优先用 `pwd -W`（MSYS 扩展，输出 C:/... 形式），失败再回退 `pwd`。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && { pwd -W 2>/dev/null || pwd; })"
CTL="$SCRIPT_DIR/../scripts/heiman_ctl.py"
SNAPSHOT="$SCRIPT_DIR/../scripts/heiman_snapshot.py"

SNAPSHOT_ARGS=()
PORT_ARGS=()
INSTALL_ARGS=()
AUTO_INSTALL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --auto-install)
      AUTO_INSTALL=1
      shift
      ;;
    --source)
      if [[ $# -lt 2 ]]; then
        echo "--source 缺少参数值" >&2
        exit 64
      fi
      INSTALL_ARGS+=(--source "$2")
      shift 2
      ;;
    --branch)
      if [[ $# -lt 2 ]]; then
        echo "--branch 缺少参数值" >&2
        exit 64
      fi
      INSTALL_ARGS+=(--branch "$2")
      shift 2
      ;;
    --hours)
      if [[ $# -lt 2 ]]; then
        echo "--hours 缺少参数值" >&2
        exit 64
      fi
      SNAPSHOT_ARGS+=(--hours "$2")
      shift 2
      ;;
    --port)
      if [[ $# -lt 2 ]]; then
        echo "--port 缺少参数值" >&2
        exit 64
      fi
      PORT_ARGS+=(--port "$2")
      shift 2
      ;;
    --lang)
      if [[ $# -lt 2 ]]; then
        echo "--lang 缺少参数值（取值 zh-CN / en-US）" >&2
        exit 64
      fi
      SNAPSHOT_ARGS+=(--lang "$2")
      shift 2
      ;;
    *)
      echo "未知参数: $1 (支持 --hours N / --lang zh-CN|en-US / --port N / --auto-install / --source URL / --branch B)" >&2
      exit 64
      ;;
  esac
done

# 第 0 步：未安装且开启 --auto-install 时，自动查找 git 地址并克隆安装
if [[ $AUTO_INSTALL -eq 1 ]]; then
  if ! python "$CTL" status | grep -q '"installed": true'; then
    echo "[0/2] 未安装，自动定位安装源并克隆…" >&2
    if [[ ${#INSTALL_ARGS[@]} -gt 0 ]]; then
      python "$CTL" install "${INSTALL_ARGS[@]}" >&2
    else
      python "$CTL" install >&2
    fi
  fi
fi

# 第 1 步：探活，未运行则自动启动
# 注意：status 不接受 --port，端口由状态文件决定。
echo "[1/2] 检查 heiman-agent 服务状态..." >&2
if ! python "$CTL" status | grep -q '"service_up": true'; then
  echo "[1/2] 服务未运行，正在启动..." >&2
  if [[ ${#PORT_ARGS[@]} -gt 0 ]]; then
    python "$CTL" start "${PORT_ARGS[@]}" >&2
  else
    python "$CTL" start >&2
  fi
fi

# 第 2 步：取数，输出归一化快照 JSON（安全评分 / 告警 / 舒适度 / 设备列表）
echo "[2/2] 获取设备快照..." >&2
if [[ ${#SNAPSHOT_ARGS[@]} -gt 0 ]]; then
  exec python "$SNAPSHOT" "${SNAPSHOT_ARGS[@]}"
else
  exec python "$SNAPSHOT"
fi
