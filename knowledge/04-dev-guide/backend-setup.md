# 开发指南

## 环境准备

- **Python** >= 3.10（推荐 3.12+），由 `uv` 管理虚拟环境
- **Node.js**（LTS），由 pnpm 管理 TypeScript 包
- **uv**：Python 包和 workspace 管理，缺失时自动安装
- **pnpm**：TypeScript 包管理（前端）

---

## 一键安装（推荐）

```bash
# 开发者：从源码构建后本地安装
bash scripts/install.sh --dev

# 终端用户：从 Release 下载对应平台归档后本地安装
bash scripts/install.sh

# 非交互模式（CI / 自动化）
bash scripts/install.sh --agent-prepare   # 输出 JSON，供脚本解析后分步调用
```

`install.sh` 先确保 uv + Python >= 3.10 就位，再依次完成：环境检查 → 包安装 → 服务预热 → 海曼账号绑定引导 → 配置初始化。

---

## 手动安装（逐步）

```bash
# Server（Python）
cd backend && uv sync --all-packages

# CLI
cd cli && uv sync && uv tool install . --force --reinstall

# 前端（React）
cd web && pnpm install && pnpm build
```

---

## 启动

```bash
# CLI 管理服务（推荐，后台守护进程）
heiman-cli service start
heiman-cli service status
heiman-cli service logs -f
heiman-cli service stop

# 开发模式（前台直跑，进程异常立即可见）
cd backend && uv run task dev
```

服务启动后监听 `127.0.0.1:1912`（默认）。健康检查：`curl http://127.0.0.1:1912/health` 应返回 `{"code":0,"message":"success","data":{"status":"healthy"}}`。

**单进程约束**：Server 不支持多 worker（`workers != 1` 直接抛 `NotImplementedError`）。传感器采集、规则引擎、资源监控均为单实例 daemon，多 worker 会导致资源锁竞争和监控状态分裂。需要横向扩展请在反代层做（nginx 多上游 / haproxy）。

---

## 配置体系

### 配置来源与优先级

配置统一由 `HeimanSettings`（`backend/heiman/src/heiman/config/settings.py`）管理，加载优先级从高到低：

1. **环境变量**（`HEIMAN_*`，嵌套用 `__` 分隔，如 `HEIMAN_SERVER__PORT`）
2. **用户配置文件**（`$HEIMAN_HOME/config.json`）— 三端（backend / CLI / 前端）共享，用户日常调整的入口
3. **后端默认值**（`settings.py` 的 pydantic 模型默认值）
4. **代码默认值**

### 配置分段与用途

| 配置段 | 控制什么 |
|--------|---------|
| `server` | 后端监听 host/port、访问 bearer token、日志级别 |
| `auth` | OAuth2 client_id/client_secret、API URL、redirect_uri |
| `database` | SQLite 连接参数 |
| `sensor` | 传感器同步间隔、数据保留天数 |
| `rule` | 规则日志保留天数、触发条件配置 |
| `logging` | 日志级别、日志目录 |
| `directories` | 工作目录（storage）、日志目录、数据目录 |

### 用户最常修改的配置项

- `auth.client_id` / `auth.client_secret`：海曼云 OAuth2 凭证，启动前必填
- `server.host`：默认 `127.0.0.1`，仅本机可达；开放局域网访问改为 `0.0.0.0`（需自行评估网络安全）
- `server.port`：服务监听端口，默认 `1912`；与其他服务端口冲突时修改此项
- `sensor.sync_interval_seconds`：传感器同步间隔，默认 30 秒
- `logging.level`：日志级别，调试时改为 `DEBUG`

### 配置修改后是否需要重启

大多数配置在服务启动时一次性读取，修改后需重启才能生效。包括：`server.*`（host/port/log_level）、`auth.*`、`directories.*` 等。

`heiman-cli config set` 写入 `config.json` 后，下次 `get_settings()` 调用即读到新值——但如果对应的 Service/Runner 在初始化时已缓存了该配置，运行期不会自动重读，仍需重启服务。

### 验证配置生效

```bash
# 查看所有当前生效配置（含派生路径）
heiman-cli config show

# 查看具体字段
heiman-cli config get server.port

# 重启后确认服务正常
heiman-cli service stop && heiman-cli service start
heiman-cli admin status
```

---

## 常用操作

```bash
# 绑定海曼账号
heiman-cli account bind       # 交互式：等待粘贴授权码
heiman-cli account status     # 查看绑定状态

# 查看已接入设备
heiman-cli device list [--online]

# 查看服务状态和节点健康
heiman-cli admin status
```

配置文件路径：`$HEIMAN_HOME/config.json`（默认 `~/.heiman/config.json`），字段定义以 `settings.py` 的 pydantic 模型为准。

---

## 开发工作流

```bash
# Server 开发
cd backend
uv sync --all-groups           # 安装包含 dev 依赖
uv run task dev                # 前台直跑开发服务器（进程异常立即可见）
uv run task test               # 运行测试
uv run task lint               # lint + format 检查
uv run task check              # 类型检查

# CLI 修改后需重装才生效
cd cli
uv run heiman-cli device list  # 直接用 uv run 跑本地版本（不需重装）

# 前端（web/）
cd web
pnpm install                   # 安装依赖
pnpm build                     # 构建到 web/dist/（生产包）
pnpm dev                       # Vite dev server，自动代理 /api 到 backend
pnpm test                      # 单元测试（vitest）
pnpm typecheck                 # 类型检查
```

---

## 常见开发场景

### 场景一：修改传感器同步参数

传感器同步参数集中在 `$HEIMAN_HOME/config.json` 的 `sensor` 段，字段定义见 `settings.py` 的 `SensorSettings`。

```bash
# 查看当前传感器配置
heiman-cli config show | grep sensor

# 修改同步间隔后重启服务使配置生效
heiman-cli service stop && heiman-cli service start

# 确认传感器状态
curl -H "Authorization: bearer $(heiman-cli config get server.token)" \
  http://127.0.0.1:1912/api/sensors
```

相关代码入口：
- 传感器采集调度：`collector/__init__.py`（SensorCollector）
- 设备适配器：`adapter/adapter_base.py`（SensorDeviceAdapter）
- 传感器数据存储：`database/sensor_repo.py`

### 场景二：添加/调试规则

```bash
# 查看当前规则列表
heiman-cli rule list --pretty

# 查看规则触发日志（最近 1 小时）
heiman-cli event list --since 1h --pretty

# 手动触发规则测试（debug 用）
heiman-cli rule trigger <rule_id>
```

规则 schema 定义在 `backend/heiman/src/heiman/schema/rule.py`，规则执行逻辑在 `rule/rule_engine.py`（RuleEngine）。

### 场景三：直接调用 API 进行调试

```bash
# 获取 token
TOKEN=$(heiman-cli config get server.token)

# 查询设备列表
curl -H "Authorization: bearer $TOKEN" http://127.0.0.1:1912/api/sensors

# 查询事件列表
curl -H "Authorization: bearer $TOKEN" http://127.0.0.1:1912/api/events

# 查询规则列表
curl -H "Authorization: bearer $TOKEN" http://127.0.0.1:1912/api/rules

# 查询系统状态
curl -H "Authorization: bearer $TOKEN" http://127.0.0.1:1912/api/admin/status

# 查询系统资源
curl -H "Authorization: bearer $TOKEN" http://127.0.0.1:1912/api/monitor/resources
```

---

## 数据落盘约定

| 路径 | 用途 |
|------|------|
| `~/.heiman/` | `$HEIMAN_HOME` 默认根 |
| `config.json` | 三端共享配置 |
| `heiman.db` | SQLite 业务数据库 |
| `logs/` | 各组件日志（`heiman-backend.log` / `supervisord.log` 等） |
| `supervisord.*` | supervisor 配置和 socket（service start 首次生成） |

---

## 日志位置速查

日志位置速查见 [故障排查 · 日志位置](troubleshooting.md#日志位置)。

---

## 代码规范

- **Python**：Ruff（lint + format），配置在 `backend/pyproject.toml`
- **TypeScript**：ESLint，配置在 `web/eslint.config.js`
- **测试**：pytest / vitest
- **Commit**：遵循项目 git log 中的提交风格