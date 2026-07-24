#!/usr/bin/env bash
set -euo pipefail

HEIMAN_AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="${HEIMAN_AGENT_DIR}/web"
BACKEND_DIR="${HEIMAN_AGENT_DIR}/backend/heiman"
STATIC_DIR="${BACKEND_DIR}/static"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

setup_node() {
    local node_paths=(
        "/Users/haiman/.local/node-v22/bin"
        "$HOME/.nvm/versions/node/v22/bin"
        "/usr/local/bin"
        "/opt/homebrew/bin"
    )

    for np in "${node_paths[@]}"; do
        if [ -x "$np/node" ]; then
            export PATH="$np:$PATH"
            log_info "使用 Node.js: $np/node"
            return 0
        fi
    done

    log_warn "未找到 Node.js，尝试使用系统默认"
    return 1
}

clean_old_builds() {
    log_info "清理旧构建内容..."

    local dist_dir="${WEB_DIR}/dist"
    if [ -d "$dist_dir" ]; then
        rm -rf "$dist_dir"
        log_info "已清理前端构建目录: $dist_dir"
    fi

    local assets_dir="${STATIC_DIR}/assets"
    if [ -d "$assets_dir" ]; then
        rm -rf "$assets_dir"
        log_info "已清理后端静态资源目录: $assets_dir"
    fi

    log_success "清理完成"
}

build_frontend() {
    log_info "构建前端..."

    if [ ! -d "$WEB_DIR" ]; then
        log_error "前端目录不存在: $WEB_DIR"
        return 1
    fi

    cd "$WEB_DIR"

    if [ ! -f "package.json" ]; then
        log_error "package.json 不存在"
        return 1
    fi

    if ! command -v npm &> /dev/null; then
        log_warn "npm 命令未找到，尝试设置 Node.js 路径..."
        setup_node
    fi

    if ! command -v npm &> /dev/null; then
        log_error "npm 不可用，请安装 Node.js"
        return 1
    fi

    log_info "安装前端依赖..."
    npm install --quiet

    log_info "执行前端构建..."
    npm run build

    log_success "前端构建完成"
}

copy_frontend_to_backend() {
    log_info "复制前端资源到后端..."

    local dist_dir="${WEB_DIR}/dist"
    if [ ! -d "$dist_dir" ]; then
        log_error "前端构建产物目录不存在: $dist_dir"
        return 1
    fi

    mkdir -p "$STATIC_DIR"

    cp -f "${dist_dir}/index.html" "$STATIC_DIR/"
    cp -f "${dist_dir}/favicon.svg" "$STATIC_DIR/" 2>/dev/null || true

    if [ -d "${dist_dir}/assets" ]; then
        mkdir -p "${STATIC_DIR}/assets"
        cp -f "${dist_dir}/assets/"* "${STATIC_DIR}/assets/"
    fi

    if [ -d "${dist_dir}/locales" ]; then
        mkdir -p "${STATIC_DIR}/locales"
        cp -rf "${dist_dir}/locales/"* "${STATIC_DIR}/locales/"
    fi

    log_success "前端资源已复制到: $STATIC_DIR"
}

setup_python() {
    local python_paths=(
        "/usr/local/bin/python3.14"
        "/usr/local/bin/python3"
        "/opt/homebrew/bin/python3"
        "/usr/bin/python3"
    )

    for pp in "${python_paths[@]}"; do
        if [ -x "$pp" ]; then
            export PYTHON="$pp"
            export PIP="$pp"
            log_info "使用 Python: $pp"
            return 0
        fi
    done

    log_warn "未找到 Python，尝试使用系统默认"
    export PYTHON="python3"
    export PIP="pip3"
    return 1
}

start_backend() {
    log_info "启动后端服务..."

    if [ ! -d "$BACKEND_DIR" ]; then
        log_error "后端目录不存在: $BACKEND_DIR"
        return 1
    fi

    cd "$BACKEND_DIR"

    if [ ! -f "pyproject.toml" ]; then
        log_error "pyproject.toml 不存在"
        return 1
    fi

    setup_python

    log_info "安装后端依赖..."
    $PYTHON -m pip install -e . --quiet 2>/dev/null || $PYTHON -m pip install fastapi uvicorn httpx pydantic python-dotenv --quiet

    log_success "后端服务启动中..."
    echo ""
    echo "============================================"
    echo "  Heiman Agent 服务已启动"
    echo "============================================"
    echo ""
    echo "访问地址: http://localhost:1912"
    echo ""

    exec $PYTHON -m uvicorn heiman.main:app --host 0.0.0.0 --port 1912 --reload
}

main() {
    echo ""
    echo "============================================"
    echo "  Heiman Agent 一键启动脚本"
    echo "============================================"
    echo ""

    log_info "项目目录: $HEIMAN_AGENT_DIR"
    echo ""

    clean_old_builds
    build_frontend || exit 1
    copy_frontend_to_backend || exit 1
    start_backend || exit 1
}

main "$@"