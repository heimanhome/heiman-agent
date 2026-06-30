#!/usr/bin/env bash
set -euo pipefail

# Heiman Agent 自动化安装脚本
# 用法: curl -fsSL https://example.com/install.sh | bash

HEIMAN_VERSION="latest"
HEIMAN_HOME="${HOME}/.heiman"
HEIMAN_BIN_DIR="${HEIMAN_HOME}/bin"
HEIMAN_DATA_DIR="${HEIMAN_HOME}/data"
HEIMAN_LOG_DIR="${HEIMAN_HOME}/logs"
HEIMAN_CONFIG_DIR="${HEIMAN_HOME}/config"

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

detect_os() {
    local os=""
    case "$(uname -s)" in
        Linux*)     os="linux";;
        Darwin*)    os="macos";;
        CYGWIN*)    os="windows";;
        MINGW*)     os="windows";;
        *)          os="unknown";;
    esac
    echo "$os"
}

detect_arch() {
    local arch=""
    case "$(uname -m)" in
        x86_64|amd64)   arch="x86_64";;
        arm64|aarch64)  arch="arm64";;
        *)              arch="unknown";;
    esac
    echo "$arch"
}

check_dependencies() {
    log_info "检查系统依赖..."

    local missing_deps=()

    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3 (>=3.10)")
    else
        local py_version
        py_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        log_info "检测到 Python 版本: $py_version"
    fi

    if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
        missing_deps+=("pip3")
    fi

    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_warn "缺少以下依赖:"
        for dep in "${missing_deps[@]}"; do
            echo "  - $dep"
        done
        log_warn "请先安装这些依赖后再运行此脚本"
        return 1
    fi

    log_success "依赖检查通过"
    return 0
}

create_directories() {
    log_info "创建目录结构..."

    mkdir -p "$HEIMAN_HOME"
    mkdir -p "$HEIMAN_BIN_DIR"
    mkdir -p "$HEIMAN_DATA_DIR"
    mkdir -p "$HEIMAN_LOG_DIR"
    mkdir -p "$HEIMAN_CONFIG_DIR"

    log_success "目录创建完成: $HEIMAN_HOME"
}

install_backend() {
    log_info "安装 Heiman Agent 后端..."

    local backend_dir="${HEIMAN_HOME}/backend"
    mkdir -p "$backend_dir"

    if [ -d "/Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman" ]; then
        log_info "从本地源码安装..."
        cp -r /Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/* "$backend_dir/"
    else
        log_warn "未找到本地源码，跳过后端安装"
        return 0
    fi

    log_info "安装 Python 依赖..."
    cd "$backend_dir"
    if [ -f "requirements.txt" ]; then
        pip3 install -r requirements.txt --quiet
    elif [ -f "pyproject.toml" ]; then
        pip3 install -e . --quiet 2>/dev/null || pip3 install fastapi uvicorn httpx pydantic python-dotenv --quiet
    else
        pip3 install fastapi uvicorn httpx pydantic python-dotenv --quiet
    fi

    log_success "后端安装完成"
}

generate_config() {
    log_info "生成默认配置文件..."

    local config_file="${HEIMAN_CONFIG_DIR}/settings.yaml"

    if [ -f "$config_file" ]; then
        log_warn "配置文件已存在，跳过生成: $config_file"
        return 0
    fi

    local token
    token=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

    cat > "$config_file" << EOF
# Heiman Agent 配置文件
# 生成时间: $(date -Iseconds)

server:
  host: "0.0.0.0"
  port: 8000
  token: "${token}"

heiman:
  api_url: "https://spapi.heiman.cn"
  app_id: "11"
  email: ""
  password: ""

sensor:
  sync_interval_seconds: 30

logging:
  level: "INFO"
  log_ttl_days: 30

directories:
  data_dir: "${HEIMAN_DATA_DIR}"
  log_dir: "${HEIMAN_LOG_DIR}"
  config_dir: "${HEIMAN_CONFIG_DIR}"
EOF

    log_success "配置文件已生成: $config_file"
    log_info "请编辑配置文件填写海曼 API 凭据"
}

create_startup_script() {
    log_info "创建启动脚本..."

    local startup_script="${HEIMAN_BIN_DIR}/heiman-agent"

    cat > "$startup_script" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

HEIMAN_HOME="${HOME}/.heiman"
BACKEND_DIR="${HEIMAN_HOME}/backend"
CONFIG_FILE="${HEIMAN_HOME}/config/settings.yaml"

export HEIMAN_CONFIG="${CONFIG_FILE}"

cd "${BACKEND_DIR}"
exec python3 -m heiman.main "$@"
EOF

    chmod +x "$startup_script"

    log_success "启动脚本已创建: $startup_script"
}

setup_path() {
    log_info "配置环境变量..."

    local shell_rc=""
    case "$SHELL" in
        */zsh)  shell_rc="$HOME/.zshrc";;
        */bash) shell_rc="$HOME/.bashrc";;
        *)      shell_rc="$HOME/.profile";;
    esac

    local path_entry="export PATH=\"${HEIMAN_BIN_DIR}:\$PATH\""

    if ! grep -qF "$HEIMAN_BIN_DIR" "$shell_rc" 2>/dev/null; then
        echo "" >> "$shell_rc"
        echo "# Heiman Agent" >> "$shell_rc"
        echo "$path_entry" >> "$shell_rc"
        log_success "已将 Heiman 添加到 PATH ($shell_rc)"
        log_info "请运行 'source $shell_rc' 或重启终端使更改生效"
    else
        log_info "PATH 已配置"
    fi
}

print_summary() {
    echo ""
    echo "============================================"
    echo -e "${GREEN}  Heiman Agent 安装完成！${NC}"
    echo "============================================"
    echo ""
    echo "安装目录: $HEIMAN_HOME"
    echo "配置文件: ${HEIMAN_CONFIG_DIR}/settings.yaml"
    echo "启动命令: heiman-agent"
    echo ""
    echo "下一步操作:"
    echo "  1. 编辑配置文件: vi ${HEIMAN_CONFIG_DIR}/settings.yaml"
    echo "  2. 启动服务: heiman-agent"
    echo "  3. 访问 Web 界面: http://localhost:8000"
    echo ""
}

main() {
    echo ""
    echo "============================================"
    echo "  Heiman Agent 安装程序"
    echo "============================================"
    echo ""

    local os
    os=$(detect_os)
    local arch
    arch=$(detect_arch)

    log_info "操作系统: $os"
    log_info "系统架构: $arch"
    log_info "安装目录: $HEIMAN_HOME"
    echo ""

    check_dependencies || exit 1
    create_directories
    install_backend
    generate_config
    create_startup_script
    setup_path
    print_summary
}

main "$@"
