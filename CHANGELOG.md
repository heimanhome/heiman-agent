# Changelog

所有对 Heiman-Agent 的重要变更都记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [2.1.0] - 2026-06-25

### 紧急修复 (Critical)

- **HTTP 404 on `/`** - 修复 `settings.py` 中 `static_dir` 路径深度错误（`parent.parent.parent` → `parent.parent.parent.parent`），导致服务启动后访问根路径返回 404。回归测试已加入。
- **数据库升级逻辑** - 修复 `connector.py`：当 `user_version` 已是目标值但实际表缺失时（如手动写入场景），会自动补齐缺失的 person/task 表，不再返回 500。

### 新增 (Added)

#### 后端

- **任务管理模块**（`/api/tasks`）- 支持进度型（progress）、时长型（duration）、事件型（event）三种任务
  - 15 个 REST 端点（CRUD、暂停/恢复、进度递增、会话起止、事件追加、任务关联）
  - 数据库表：`task`、`task_link`、`task_record_progress`、`task_record_duration`、`task_record_event`、`task_duration_session`、`task_event_entry`
  - 任务链接全局唯一约束：`(link_kind, link_ref)`

- **人员管理模块**（`/api/persons`）
  - 5 个 REST 端点（CRUD）
  - 数据库表：`person`
  - 姓名唯一约束、PATCH 语义归一化

- **可观测性模块**（`/api/observability/*`）
  - 6 个 REST 端点（overview、system、sensor、rule、event、database）
  - 实时系统指标（CPU/内存/磁盘/uptime）
  - 业务数据统计（传感器/规则/事件/数据库）

#### CLI

- `heiman-cli person` - 5 个子命令（list/get/create/update/delete）
- `heiman-cli task` - 10 个子命令（list/get/create/delete/pause/resume/progress/session/event/link）
- `heiman-cli health` - 注册到主 CLI（之前存在但未注册）

#### 前端

- 页面 `/persons` - 家庭成员管理
- 页面 `/tasks` - 任务管理（支持三种任务类型的可视化）
- 页面 `/observability` - 系统监控面板（5s 自动刷新）
- Sidebar 菜单添加新入口
- API 客户端扩展 `personApi`、`taskApi`、`observabilityApi`
- i18n 翻译键（zh）

#### 工具

- `scripts/install.sh` - 自动化安装脚本

### 测试

- 后端测试 91 个用例（新增 HTTP 集成测试 11 个、回归测试 1 个）
- CLI 测试 10 个用例（新增命令注册与执行测试）
- 全部 101 个测试通过

### 文档

- `DEVELOPMENT_SUMMARY.md` - 添加 Phase 5
- `INSTALLATION.md` - 安装指南
- `API_REFERENCE.md` - API 参考

---

## [2.0.0] - 2026-06-24

### 重大修复 (Critical)

- **事件循环冲突** - `rule_engine.py` 重构 webhook 执行为异步方法 `_execute_webhook_action_async`，使用 `httpx.AsyncClient` 在 FastAPI 事件循环内执行，避免 `asyncio.run()` 创建新循环导致死锁
- **启动阻塞** - `manager.py` API 登录添加 10s 超时 + 3 次重试 + 离线模式 fallback
- **静态资源路径** - `settings.py` 改用 `computed_field` + 环境变量覆盖，自动创建目录
- **数据清理** - `main.py` 新增 `_cleanup_loop` 后台任务，每日清理过期日志并执行 `incremental_vacuum`

### 中等问题 (Medium)

- 规则条件字段验证（必填字段、操作符合法性、in/not_in 要求 list 阈值）
- 动作执行幂等性（60s TTL 缓存 + 定期清理）
- 配置重置机制（`reset_settings()`、`reload_settings()`）
- API 路由前缀统一为 `/api`

### 轻微问题 (Minor)

- 业务异常类型补充（9 个新异常类型）

### 新增 (Added)

- 后端测试 79 个用例（rule_engine、settings、exceptions、connector）

---

## [1.0.0] - 2026-06-23

### 初始版本

- 海曼 HTTP 协议传感器数据采集
- 事件分类与告警
- 基础规则引擎
- RESTful API
- OAuth2 认证
- Web 前端（基础）
- OpenClaw 插件（基础）
- 多语言国际化
