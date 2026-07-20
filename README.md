# Heiman Agent

海曼传感器智能Agent，用于智能家居安全监控与自动化。

## 功能特性

### 传感器集成
- 支持烟雾传感器、温湿度传感器、一氧化碳传感器、水浸传感器、门磁探测器等多种传感器类型
- 基于海曼HTTP协议和MQTT协议实时采集传感器数据
- 支持设备在线状态监测与事件触发

### 智能分析
- AI异常检测引擎，自动识别异常行为模式
- 舒适度评估，基于环境数据提供健康建议
- 行为识别与学习，理解用户日常活动规律

### 规则引擎
- 支持自定义规则，实现自动化场景
- 灵活的条件与动作配置
- 规则冷却机制，避免重复触发

### 实时通信
- MQTT协议实时数据推送
- Server-Sent Events (SSE) 前端实时更新
- 设备状态变化事件通知

### 可视化管理
- 响应式Web管理界面
- 多语言支持（中文、英文、日文、韩文）
- 设备状态仪表盘、事件日志、传感器历史数据图表

### 命令行工具
- 完整的CLI命令集，支持设备管理、规则配置、事件查询等操作
- 支持API调试与健康检查

## 技术栈

### 后端
- Python 3.10+
- FastAPI
- SQLite（数据库）
- Paho MQTT
- HTTPX
- Pydantic 2

### 前端
- React 18
- TypeScript
- Vite 6
- TailwindCSS 3
- Zustand（状态管理）
- Chart.js（图表）
- React Router DOM

### CLI
- Click
- Rich
- HTTPX

## 项目结构

```
heiman-agent/
├── backend/
│   └── heiman/              # FastAPI后端服务
│       ├── src/heiman/
│       │   ├── adapter/     # 设备适配器
│       │   ├── ai/          # AI模块（异常检测、行为识别等）
│       │   ├── classifier/  # 事件分类器
│       │   ├── client/      # 海曼API客户端
│       │   ├── collector/   # 数据收集器
│       │   ├── config/      # 配置管理
│       │   ├── database/    # 数据库模块
│       │   ├── home_profile/# 家庭画像
│       │   ├── middleware/  # 中间件
│       │   ├── node_monitor/# 节点监控
│       │   ├── observability/# 可观测性
│       │   ├── perception/  # 感知引擎
│       │   ├── router/      # API路由
│       │   ├── rule/        # 规则引擎
│       │   ├── schema/      # 数据模型
│       │   ├── service/     # 业务服务
│       │   ├── main.py      # 应用入口
│       │   ├── manager.py   # 服务管理器
│       │   └── mqtt_service.py # MQTT服务
│       ├── tests/           # 测试用例
│       ├── .env             # 环境配置
│       ├── .env.example     # 环境配置示例
│       └── pyproject.toml   # Python项目配置
├── cli/                     # 命令行工具
│   ├── src/heiman_cli/
│   │   ├── commands/        # CLI命令
│   │   └── main.py          # CLI入口
│   ├── tests/               # CLI测试
│   └── pyproject.toml
├── web/                     # 前端Web应用
│   ├── src/
│   │   ├── api/             # API客户端
│   │   ├── components/      # UI组件
│   │   ├── hooks/           # 自定义Hooks
│   │   ├── i18n/            # 国际化
│   │   ├── pages/           # 页面组件
│   │   ├── store/           # 状态管理
│   │   └── types/           # TypeScript类型定义
│   ├── tests/               # 前端测试
│   └── package.json
├── plugins/                 # 插件目录
│   └── openclaw/
├── .github/workflows/       # CI/CD工作流程
├── Dockerfile               # Docker镜像构建
├── docker-compose.yml       # Docker Compose配置
├── README.md                # 项目文档（本文件）
├── CHANGELOG.md             # 变更日志
└── API_REFERENCE.md         # API参考文档
```

## 安装指南

### 前置依赖

- Python 3.10+
- Node.js 20+
- pnpm（前端包管理）

### 后端安装

```bash
# 进入后端目录
cd backend/heiman

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# macOS/Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

# 安装依赖
pip install -e .

# 安装测试依赖
pip install pytest pytest-asyncio httpx
```

### CLI安装

```bash
cd cli
pip install -e .
```

### 前端安装

```bash
cd web
pnpm install
```

## 使用方法

### 配置环境变量

复制并修改后端环境配置：

```bash
cd backend/heiman
cp .env.example .env
```

编辑 `.env` 文件，配置以下关键参数：

```env
# 海曼API配置
HEIMAN_API_URL=https://spapi.heiman.cn
HEIMAN_APP_ID=your_app_id
HEIMAN_EMAIL=your_email@example.com
HEIMAN_PASSWORD=your_password

# 服务器配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# 传感器刷新间隔（秒）
SENSOR_REFRESH_INTERVAL_SECONDS=30

# 规则引擎配置
RULE_ENGINE_ENABLED=true
RULE_DEFAULT_COOLDOWN_MINUTES=5

# 日志配置
LOGGING_LEVEL=INFO
LOGGING_LOG_DIR=/tmp/heiman/logs
```

### 启动后端服务

```bash
cd backend/heiman
heiman-backend
```

或使用Uvicorn直接启动：

```bash
uvicorn heiman.main:create_app --host 0.0.0.0 --port 8000 --reload
```

### 启动前端开发服务器

```bash
cd web
pnpm dev
```

### 使用CLI工具

```bash
# 查看帮助
heiman --help

# 查看子命令帮助
heiman devices --help

# 获取设备列表
heiman devices list

# 获取事件列表
heiman events list

# 健康检查
heiman health
```

## API接口

### 认证接口
- `GET /api/auth/profile` - 获取用户信息
- `POST /api/auth/login` - 用户登录
- `POST /api/auth/refresh` - 刷新令牌

### 设备接口
- `GET /api/devices` - 获取设备列表
- `GET /api/devices/{device_id}` - 获取单个设备
- `GET /api/devices/{device_id}/properties` - 获取设备属性

### 传感器接口
- `GET /api/sensors` - 获取传感器列表
- `GET /api/sensors/{sensor_id}` - 获取单个传感器
- `GET /api/sensors/{sensor_id}/history` - 获取传感器历史数据

### 事件接口
- `GET /api/events` - 获取事件列表
- `GET /api/events/{event_id}` - 获取单个事件
- `POST /api/events/{event_id}/acknowledge` - 确认事件

### 规则接口
- `GET /api/rules` - 获取规则列表
- `POST /api/rules` - 创建规则
- `PUT /api/rules/{rule_id}` - 更新规则
- `DELETE /api/rules/{rule_id}` - 删除规则

### 可观测性接口
- `GET /api/observability/overview` - 获取系统概览
- `GET /api/health` - 健康检查

### 实时事件流
- `GET /api/events/stream` - SSE实时事件流

## 测试

### 运行后端测试

```bash
cd backend/heiman
pytest
```

### 运行前端测试

```bash
cd web
pnpm test
```

### 运行CLI测试

```bash
cd cli
pytest
```

## Docker部署

### 构建镜像

```bash
docker build -t heiman-agent .
```

### 运行容器

```bash
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/backend/heiman/.env:/app/.env \
  --name heiman-agent \
  heiman-agent
```

### 使用Docker Compose

```bash
docker-compose up -d
```

## CI/CD

项目使用GitHub Actions实现自动化CI/CD流程，包含以下环节：

1. **代码检查** - 运行flake8、mypy进行代码质量检查
2. **单元测试** - 运行pytest测试套件
3. **构建验证** - 验证Python包和前端构建
4. **镜像构建** - 构建Docker镜像
5. **部署** - 部署到目标环境

## 贡献指南

欢迎贡献代码！请遵循以下流程：

1. Fork项目
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交代码：`git commit -m "feat: add your feature"`
4. 推送到分支：`git push origin feature/your-feature`
5. 创建Pull Request

### 代码规范

- Python代码遵循PEP 8规范
- 使用flake8进行代码检查
- 使用mypy进行类型检查
- 提交信息遵循约定式提交规范：
  - `feat:` 新功能
  - `fix:` 修复bug
  - `docs:` 文档更新
  - `refactor:` 代码重构
  - `test:` 测试相关
  - `chore:` 构建/工具更新

### 测试要求

- 新增功能需添加相应的单元测试
- 确保所有测试通过后提交
- 测试覆盖率目标：≥80%

## 许可证

本项目采用MIT许可证，详见[LICENSE](LICENSE)文件。

## 联系方式

如有问题或建议，请通过以下方式联系：

- 提交Issue到GitHub仓库
- 发送邮件至：help@heimanhome.com

