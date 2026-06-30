# Heiman Agent Knowledge Base

Heiman Agent 是一个智能家居传感器监控和管理平台，集成海曼IoT设备，提供实时传感器数据采集、事件分类、规则自动化和全面的Web界面。

## 目录结构

```
knowledge/
├── 01-overview/          # 项目概述和架构文档
│   └── overview.md       # 项目概述、架构设计
├── 02-features/          # 详细功能说明
│   ├── sensor-monitoring.md   # 传感器监控
│   ├── event-management.md    # 事件管理
│   └── rule-automation.md     # 规则自动化
├── 03-api/               # API文档
│   └── api-reference.md  # API参考手册
├── 04-dev-guide/         # 开发指南和故障排除
│   ├── backend-setup.md  # 后端环境配置
│   ├── cli-setup.md      # CLI工具使用指南
│   ├── plugin-development.md  # 插件开发指南
│   └── troubleshooting.md     # 故障排除指南
├── 05-external-deps/     # 外部依赖文档
│   ├── sdk-heiman-connect.md  # Heiman Connect SDK
│   └── sdk-oauth2.md           # OAuth2认证
└── 06-design/            # 设计文档
    ├── architecture.md   # 系统架构设计
    ├── data-flow.md      # 数据流设计
    └── plugin-system.md  # 插件系统设计
```

## 快速入门

1. **后端**：查看 `04-dev-guide/backend-setup.md` 获取安装配置说明
2. **Web界面**：查看 `04-dev-guide/web-setup.md` 获取前端配置说明
3. **CLI**：查看 `04-dev-guide/cli-setup.md` 获取命令行工具安装说明

## 核心功能

- 实时传感器数据采集（烟雾、温湿度、一氧化碳、水浸）
- 事件分类和告警通知
- 规则引擎自动化
- OAuth2认证
- RESTful API接口
- Web仪表盘实时监控
- CLI管理工具
- 插件扩展系统

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18, TypeScript, TailwindCSS 3, Zustand |
| 后端 | FastAPI, Python 3.10+ |
| 数据库 | SQLite |
| API客户端 | httpx, heiman-connect |
| 认证 | OAuth2 |
| CLI | Click |

## 开发流程

1. Fork 仓库并克隆到本地
2. 安装后端依赖：`pip install -e backend/`
3. 安装前端依赖：`cd web && pnpm install`
4. 启动后端：`heiman-cli service start`
5. 启动前端：`cd web && pnpm dev`
6. 访问 Web 界面：`http://localhost:5173`