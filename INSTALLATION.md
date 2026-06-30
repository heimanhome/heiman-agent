# Heiman-Agent 安装指南

## 0. 概述

Heiman-Agent 是一个本地部署的智能传感器监控平台。本文档说明其完整安装、配置与运行流程，与 `xiaomi-miloco` 的安装脚本保持一致结构。

## 1. 系统要求

| 组件 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Python | 3.10 | 3.12+ |
| Node.js | 18 | 20+ |
| pnpm | 8 | 9+ |
| 操作系统 | macOS 12+ / Linux (Ubuntu 20.04+) | - |
| 内存 | 2 GB | 4 GB+ |
| 磁盘 | 1 GB | 5 GB+ |

## 2. 自动化安装（推荐）

### 2.1 macOS / Linux

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

脚本自动完成：
- 环境检测（OS、架构、Python 版本）
- 创建 `~/.heiman/{bin,data,logs,config}` 目录
- 安装 Python 依赖
- 生成 `settings.yaml` 配置文件
- 创建 `heiman-agent` 启动命令
- 配置 PATH 环境变量

### 2.2 远程安装

```bash
curl -fsSL https://example.com/install.sh | bash
```

## 3. 手动安装

### 3.1 后端

```bash
cd backend/heiman
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3.2 CLI

```bash
cd cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3.3 前端

```bash
cd web
pnpm install
pnpm build
```

构建产物会输出到 `web/dist/`，包含 `index.html`、`assets/`、`locales/`。

## 4. 配置

### 4.1 配置文件位置

| 文件 | 位置 | 说明 |
|------|------|------|
| 主配置 | `~/.heiman/config/settings.yaml` | 全局配置 |
| 数据库 | `~/.heiman/data/heiman.db` | SQLite 数据 |
| 日志 | `~/.heiman/logs/heiman-agent.log` | 运行日志 |

### 4.2 环境变量覆盖

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HEIMAN_STATIC_DIR` | `<backend>/static` | 静态资源目录 |
| `HEIMAN_DATA_DIR` | `~/.heiman/data` | 数据目录 |
| `HEIMAN_LOG_DIR` | `/tmp/heiman/logs` | 日志目录 |
| `HEIMAN_CONFIG_DIR` | `~/.heiman/config` | 配置目录 |
| `SERVER_HOST` | `127.0.0.1` | 监听地址 |
| `SERVER_PORT` | `1912` | 监听端口 |
| `SERVER_TOKEN` | `heiman_test_token_123` | API 鉴权 token |
| `HEIMAN_API_URL` | `https://spapi.heiman.cn` | 海曼 API 地址 |
| `HEIMAN_EMAIL` | - | 海曼账号 |
| `HEIMAN_PASSWORD` | - | 海曼密码 |

### 4.3 settings.yaml 示例

```yaml
server:
  host: "0.0.0.0"
  port: 1912
  token: "${random_token}"

heiman:
  api_url: "https://spapi.heiman.cn"
  app_id: "11"
  email: "${your_email}"
  password: "${your_password}"

sensor:
  sync_interval_seconds: 30

logging:
  level: "INFO"
  log_ttl_days: 30
```

## 5. 启动与停止

### 5.1 启动

```bash
# 后端（监听 1912）
heiman-agent

# 或开发模式（带 reload）
cd backend/heiman
uvicorn heiman.main:app --host 0.0.0.0 --port 1912 --reload
```

### 5.2 健康检查

```bash
curl http://127.0.0.1:1912/health
# {"status":"healthy","service":"heiman-agent"}
```

### 5.3 停止

```bash
# 查找进程
ps aux | grep heiman
# 终止
kill <PID>
```

## 6. CLI 快速开始

```bash
# 健康检查
heiman-cli health check

# 列出传感器
heiman-cli device list

# 列出事件
heiman-cli event list

# 列出规则
heiman-cli rule list

# 列出人员（v2.1 新增）
heiman-cli person list

# 创建人员
heiman-cli person create --name "Alice" --role "mother"

# 列出任务（v2.1 新增）
heiman-cli task list

# 创建任务
heiman-cli task create --description "Daily 10k steps" \
  --kind progress --target 10000 --unit steps --window day
```

## 7. 访问 Web 界面

启动服务后访问 <http://127.0.0.1:1912/>。

| 页面 | URL | 说明 |
|------|-----|------|
| 仪表盘 | `/` | 总览 |
| 设备 | `/devices` | 设备管理 |
| 传感器 | `/sensors` | 传感器列表 |
| 事件 | `/events` | 事件日志 |
| **任务** | `/tasks` | **任务管理（v2.1 新增）** |
| **家庭成员** | `/persons` | **人员管理（v2.1 新增）** |
| 规则 | `/rules` | 规则管理 |
| 日志 | `/logs` | 操作日志 |
| 模型 | `/models` | 模型管理 |
| **可观测性** | `/observability` | **系统监控（v2.1 新增）** |

## 8. 故障排除

### 8.1 HTTP 404 on `/`

**原因**：`static_dir` 路径计算错误。**修复**（v2.1.0）：
- 升级到 v2.1+ 后已修复
- 验证：`python3 -c "from heiman.config import get_settings; print(get_settings().directories.static_dir)"`
- 应输出 `.../backend/heiman/static` 而非 `.../backend/heiman/src/static`

### 8.2 数据库 `no such table`

**原因**：旧版本数据库升级时未补齐缺失表。**修复**（v2.1.0）：
- 启动时会自动检测并补齐缺失表
- 或手动删除 `~/.heiman/data/heiman.db` 重新初始化

### 8.3 启动阻塞

**原因**（v2.1 已修复）：API 登录无超时。重启服务即可，3 次重试 + 离线模式会兜底。

## 9. 卸载

```bash
# 停止服务
pkill -f "heiman.main"

# 删除文件
rm -rf ~/.heiman
pip uninstall heiman heiman-cli -y
```
