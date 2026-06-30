# Heiman-Agent 全面整改升级计划

## 文档信息

| 项目 | 内容 |
|------|------|
| 项目名称 | Heiman-Agent 智能传感器平台 |
| 基准版本 | v1.0.0 |
| 目标版本 | v2.0.0 |
| 制定日期 | 2026-06-25 |
| 基准文档 | ANALYSIS_REPORT.md |

---

## 1. 执行摘要

### 1.1 升级目标

本计划旨在将 Heiman-Agent 从基础版本升级为符合生产环境标准的智能家居平台，解决已发现的**4个严重问题**、**4个中等问题**和**3个轻微问题**，并补齐**12个缺失功能模块**。

### 1.2 升级范围

| 类别 | 数量 | 说明 |
|------|------|------|
| 严重问题修复 | 4 | 事件循环冲突、启动阻塞、路径问题、数据清理 |
| 中等问题修复 | 4 | 字段验证、幂等性、错误恢复、API客户端 |
| 轻微问题修复 | 3 | 异常类型、配置重置、路由前缀 |
| 缺失功能 | 12 | 任务管理、人员管理、可观测性等 |
| 性能优化 | 5 | 数据库、缓存、并发、API调用 |
| 安全加固 | 4 | 认证、授权、审计、加密 |

### 1.3 资源需求

| 资源类型 | 需求 |
|----------|------|
| 开发人力 | 2人 × 8周 |
| 测试环境 | 1套 staging 环境 |
| 文档工时 | 1人 × 2周 |

---

## 2. 问题分级与修复计划

### 2.1 P0 - 严重问题（必须立即修复）

#### 问题 2.1.1: 事件循环冲突

| 属性 | 内容 |
|------|------|
| 文件 | [rule_engine.py:131](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/rule/rule_engine.py#L131) |
| 问题 | `asyncio.run()` 在 FastAPI 事件循环中创建新循环 |
| 影响 | 可能导致事件循环死锁或资源耗尽 |

**修复方案**:
```python
# 修改前 (问题代码)
def _execute_webhook_action(self, action: RuleAction) -> bool:
    async def send_webhook():
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, timeout=10)
            return response.status_code == 200
    import asyncio
    return asyncio.run(send_webhook())  # ❌ 错误：创建新事件循环

# 修改后 (正确实现)
async def _execute_webhook_action_async(self, action: RuleAction) -> bool:
    """异步执行 Webhook，需要由调用方传入事件循环"""
    url = action.payload.get("url")
    if not url:
        logger.error("Webhook URL not specified")
        return False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=action.payload.get("data", {}),
                timeout=10,
            )
            return response.status_code == 200
    except Exception as e:
        logger.error("Webhook failed: %s", e)
        return False

def execute_action(self, action, sensor_data=None):
    """同步执行器，接收 action 并执行"""
    if action.action_type == RuleActionType.WEBHOOK:
        # Webhook 需要异步执行，暂记录为待处理
        # 实际执行由 run_rules 中的事件循环处理
        logger.info("Webhook action queued: %s", url)
        return True  # 标记为待处理
    # ... 其他同步动作
```

**修复责任人**: 后端开发
**预计工时**: 2小时
**风险等级**: 低

---

#### 问题 2.1.2: 启动阻塞

| 属性 | 内容 |
|------|------|
| 文件 | [manager.py:43](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/manager.py#L43) |
| 问题 | `await self._api_client.login()` 无超时处理 |
| 影响 | 网络不可用时服务启动失败 |

**修复方案**:
```python
# 修改 manager.py
async def initialize(self):
    # ... 前置代码 ...

    # 添加超时和重试机制
    max_retries = 3
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            # 添加 10 秒超时
            self._api_client = HeimanApiClient()
            await asyncio.wait_for(
                self._api_client.login(),
                timeout=10.0
            )
            break  # 登录成功，跳出重试循环
        except asyncio.TimeoutError:
            logger.warning("Login attempt %d timed out", attempt + 1)
            if attempt == max_retries - 1:
                logger.error("All login attempts failed, using offline mode")
                self._api_client = HeimanApiClient(offline=True)
        except Exception as e:
            logger.warning("Login attempt %d failed: %s", attempt + 1, e)
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                logger.error("All login attempts failed, using offline mode")
                self._api_client = HeimanApiClient(offline=True)
```

**修复责任人**: 后端开发
**预计工时**: 4小时
**风险等级**: 中

---

#### 问题 2.1.3: 静态资源路径

| 属性 | 内容 |
|------|------|
| 文件 | [settings.py:49](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/config/settings.py#L49) |
| 问题 | 相对路径硬编码 `Path(__file__).parent.parent.parent.parent / "static"` |
| 影响 | 部署路径变化时静态资源无法加载 |

**修复方案**:
```python
# 修改 settings.py
class DirectorySettings(BaseSettings):
    # 使用计算属性自动推导
    @computed_field
    @property
    def static_dir(self) -> Path:
        """静态资源目录，自动基于项目根目录解析"""
        # 优先使用环境变量
        if env_path := os.getenv("HEIMAN_STATIC_DIR"):
            return Path(env_path)
        # 基于 __file__ 位置计算
        backend_root = Path(__file__).parent.parent.parent  # backend/heiman/src/heiman -> backend/heiman
        default_path = backend_root / "static"
        # 确保目录存在
        default_path.mkdir(parents=True, exist_ok=True)
        return default_path

    @computed_field
    @property
    def log_dir(self) -> Path:
        """日志目录"""
        if env_path := os.getenv("HEIMAN_LOG_DIR"):
            return Path(env_path)
        # 优先使用 ~/.heiman/logs
        home_log = Path.home() / ".heiman" / "logs"
        home_log.mkdir(parents=True, exist_ok=True)
        return home_log

    @computed_field
    @property
    def db_dir(self) -> Path:
        """数据库目录"""
        if env_path := os.getenv("HEIMAN_DB_DIR"):
            return Path(env_path)
        home_db = Path.home() / ".heiman" / "data"
        home_db.mkdir(parents=True, exist_ok=True)
        return home_db
```

**修复责任人**: 后端开发
**预计工时**: 2小时
**风险等级**: 低

---

#### 问题 2.1.4: 缺少数据清理机制

| 属性 | 内容 |
|------|------|
| 文件 | [main.py](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/main.py) |
| 问题 | 无日志 TTL 清理和数据库 vacuum |
| 影响 | 数据库无限增长，磁盘空间耗尽 |

**修复方案**:
```python
# 在 main.py 中添加后台清理任务
async def _cleanup_loop() -> None:
    """后台清理任务：日志 TTL 清理 + 数据库增量 vacuum"""
    await asyncio.sleep(3600)  # 启动后 1 小时开始首次清理

    while True:
        try:
            # 1. 清理过期日志 (默认 30 天)
            from heiman.database.connector import get_db_connector
            connector = get_db_connector()

            settings = get_settings()
            max_days = getattr(settings, 'log_ttl_days', 30)

            deleted = connector.cleanup_old_logs(max_days)
            logger.info("Cleanup: deleted %d old records", deleted)

            # 2. 触发增量 vacuum (回收已删除页面)
            connector.incremental_vacuum()
            logger.info("Cleanup: incremental vacuum completed")

        except Exception as e:
            logger.error("Cleanup loop error: %s", e)

        # 每 24 小时执行一次
        await asyncio.sleep(86400)

# 在 lifespan 中启动清理任务
_cleanup_task = asyncio.create_task(_cleanup_loop())
_BG_TASKS.add(_cleanup_task)
_cleanup_task.add_done_callback(_BG_TASKS.discard)

# 在 connector.py 中添加增量 vacuum 方法
def incremental_vacuum(self, pages: int = 1000) -> None:
    """增量 vacuum，回收最多 N 个页面"""
    try:
        with self.get_connection() as conn:
            conn.execute(f"PRAGMA incremental_vacuum({pages})")
            conn.commit()
        logger.debug("Incremental vacuum completed: %d pages", pages)
    except Exception as e:
        logger.warning("Incremental vacuum failed: %s", e)
```

**修复责任人**: 后端开发
**预计工时**: 4小时
**风险等级**: 中

---

### 2.2 P1 - 中等问题

#### 问题 2.2.1: 规则条件评估缺少类型校验

**修复方案**: 添加字段类型验证和操作符兼容性检查

#### 问题 2.2.2: 动作执行无幂等性保护

**修复方案**: 实现动作幂等性检查和冷却机制

#### 问题 2.2.3: API 客户端无错误恢复

**修复方案**: 实现指数退避重试机制

#### 问题 2.2.4: 缺少配置重置机制

**修复方案**: 参考 Miloco 实现 `reset_settings()` 钩子

---

## 3. 缺失功能补齐计划

### 3.1 功能模块优先级

| 优先级 | 模块 | 工作量 | 依赖关系 |
|--------|------|--------|----------|
| P0 | 日志清理机制 | 8h | 无 |
| P0 | API 客户端重试 | 4h | 无 |
| P1 | 任务管理模块 | 40h | P0 |
| P1 | 人员管理模块 | 32h | P0 |
| P1 | 可观测性模块 | 48h | P0 |
| P1 | 自动化安装脚本 | 24h | 无 |
| P2 | 家庭档案模块 | 40h | P1 |
| P2 | Agent 调度器 | 32h | P1 |
| P2 | CLI 命令补全 | 16h | 无 |
| P2 | 配置系统增强 | 24h | P0 |

---

### 3.2 P1-1: 任务管理模块

#### 3.2.1 模块设计

```
task/
├── __init__.py
├── router.py          # API 路由
├── schema.py          # Pydantic 模型
├── service.py         # 业务逻辑
├── repo.py            # 数据访问
└── task_record/
    ├── __init__.py
    ├── repo.py        # 进度记录
    ├── rollover.py    # 每日 rollover
    └── schema.py
```

#### 3.2.2 数据库表设计

```sql
-- task 表
CREATE TABLE task (
    task_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',  -- active, paused, completed
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- task_record 表
CREATE TABLE task_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    kind TEXT NOT NULL,  -- progress, duration, event
    data TEXT NOT NULL,  -- JSON 存储具体数据
    created_at INTEGER NOT NULL,
    archived_at INTEGER,
    FOREIGN KEY (task_id) REFERENCES task(task_id) ON DELETE CASCADE
);
```

#### 3.2.3 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/tasks | 获取任务列表 |
| POST | /api/tasks | 创建任务 |
| GET | /api/tasks/{id} | 获取任务详情 |
| PUT | /api/tasks/{id} | 更新任务 |
| DELETE | /api/tasks/{id} | 删除任务 |
| POST | /api/tasks/{id}/pause | 暂停任务 |
| POST | /api/tasks/{id}/resume | 恢复任务 |
| GET | /api/tasks/{id}/records | 获取任务记录 |
| POST | /api/tasks/{id}/records | 添加任务记录 |

#### 3.2.4 实施步骤

1. 创建数据库迁移脚本
2. 实现 `TaskRepo` 数据访问层
3. 实现 `TaskService` 业务逻辑层
4. 实现 API 路由
5. 添加 rollover 定时任务
6. 编写单元测试
7. 更新 CLI 命令

---

### 3.3 P1-2: 人员管理模块

#### 3.3.1 模块设计

```
person/
├── __init__.py
├── router.py
├── schema.py
└── service.py
```

#### 3.3.2 数据库表设计

```sql
CREATE TABLE person (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    role TEXT,
    phone TEXT,
    email TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
```

#### 3.3.3 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/persons | 获取成员列表 |
| POST | /api/persons | 添加成员 |
| GET | /api/persons/{id} | 获取成员详情 |
| PUT | /api/persons/{id} | 更新成员 |
| DELETE | /api/persons/{id} | 删除成员 |

---

### 3.4 P1-3: 可观测性模块

#### 3.4.1 模块设计

```
observability/
├── __init__.py
├── metrics_client.py    # 指标采集客户端
├── metrics_db.py       # 指标存储
├── router.py           # 监控 API
├── stats.py            # 统计计算
└── types.py            # 类型定义
```

#### 3.4.2 监控指标

| 指标类型 | 指标名称 | 说明 |
|----------|----------|------|
| 系统 | cpu_usage | CPU 使用率 |
| 系统 | memory_usage | 内存使用率 |
| 系统 | disk_usage | 磁盘使用率 |
| 应用 | api_requests_total | API 请求总数 |
| 应用 | api_latency_ms | API 延迟 |
| 应用 | sensor_data_count | 传感器数据量 |
| 应用 | events_triggered | 触发事件数 |
| 应用 | rules_executed | 执行规则数 |

#### 3.4.3 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/monitor/stats | 获取统计信息 |
| GET | /api/monitor/metrics | 获取性能指标 |
| GET | /api/monitor/health | 详细健康检查 |

---

### 3.5 P2-1: 自动化安装脚本

#### 3.5.1 安装流程设计

参考 Miloco `install.sh`，设计三阶段安装流程：

```bash
# 阶段 1: 环境准备
curl -LsSf https://example.com/install.sh | bash -s -- --agent-prepare

# 阶段 2: 配置收集 (Agent 交互)
# 收集: OAuth 授权码、API Key 等

# 阶段 3: 完成安装
curl -LsSf https://example.com/install.sh | bash -s -- --agent-finish \
  --oauth-code "<code>" \
  --api-key "<key>"
```

#### 3.5.2 脚本功能

- [ ] 环境检测 (Python 版本、依赖)
- [ ] 依赖安装 (uv/pip)
- [ ] 配置文件生成
- [ ] OAuth 授权流程
- [ ] 数据库初始化
- [ ] 服务启动验证
- [ ] OpenClaw 插件安装

---

## 4. 性能优化计划

### 4.1 数据库优化

| 优化项 | 当前状态 | 目标 | 实施方式 |
|--------|----------|------|----------|
| 索引优化 | 部分索引 | 完整索引覆盖 | 添加复合索引 |
| 连接池 | 无 | 连接复用 | 添加连接池 |
| 查询优化 | N+1 查询 | 批量查询 | 重写查询逻辑 |
| Vacuum | 手动 | 定时增量 | 添加后台任务 |

### 4.2 API 优化

| 优化项 | 当前状态 | 目标 | 实施方式 |
|--------|----------|------|----------|
| 缓存 | 无 | 热点数据缓存 | 添加 LRU 缓存 |
| 分页 | 全量返回 | cursor 分页 | 优化查询 |
| 并发 | 串行处理 | 并行处理 | asyncio.gather |

### 4.3 配置优化

```python
# 添加性能配置项
class PerfSettings(BaseSettings):
    enabled: bool = True
    cache_ttl_seconds: int = 300
    max_cache_size: int = 1000
    request_timeout: float = 10.0
    connection_pool_size: int = 10
```

---

## 5. 安全加固计划

### 5.1 认证安全

| 问题 | 现状 | 加固措施 |
|------|------|----------|
| Token 存储 | 明文 | 加密存储 |
| Token 刷新 | 无 | 实现自动刷新 |
| 会话管理 | 无 | 添加会话超时 |

### 5.2 授权安全

| 问题 | 现状 | 加固措施 |
|------|------|----------|
| API 权限 | 无 | 添加权限控制 |
| 资源隔离 | 无 | home_id 隔离 |

### 5.3 审计日志

```python
# 添加审计日志表
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    action TEXT NOT NULL,
    resource TEXT,
    resource_id TEXT,
    ip_address TEXT,
    user_agent TEXT,
    timestamp INTEGER NOT NULL
);
```

---

## 6. 分阶段实施计划

### Phase 1: 稳定性修复 (Week 1-2)

| 任务 | 负责人 | 工时 | 产出 |
|------|--------|------|------|
| 修复事件循环冲突 | 后端 | 4h | PR |
| 修复启动阻塞 | 后端 | 8h | PR |
| 修复静态路径 | 后端 | 4h | PR |
| 实现日志清理 | 后端 | 8h | PR |
| 实现配置重置 | 后端 | 8h | PR |
| 单元测试 | 测试 | 16h | 测试报告 |

**里程碑**: 所有 P0 问题修复完成

---

### Phase 2: 核心功能补齐 (Week 3-5)

| 任务 | 负责人 | 工时 | 产出 |
|------|--------|------|------|
| 任务管理模块 - 后端 | 后端 | 24h | API + Service |
| 任务管理模块 - 前端 | 前端 | 16h | 页面 |
| 任务管理模块 - CLI | 后端 | 8h | CLI 命令 |
| 人员管理模块 - 后端 | 后端 | 16h | API + Service |
| 人员管理模块 - 前端 | 前端 | 12h | 页面 |
| CLI 命令补全 | 后端 | 16h | CLI 命令 |
| 单元测试 | 测试 | 24h | 测试报告 |

**里程碑**: 任务管理和人员管理模块上线

---

### Phase 3: 可观测性 (Week 6-7)

| 任务 | 负责人 | 工时 | 产出 |
|------|--------|------|------|
| 可观测性 - 指标采集 | 后端 | 24h | 指标服务 |
| 可观测性 - 监控 API | 后端 | 16h | API |
| 可观测性 - 前端面板 | 前端 | 16h | 页面 |
| CLI doctor 命令 | 后端 | 8h | CLI |
| 性能测试 | 测试 | 16h | 报告 |

**里程碑**: 监控系统上线

---

### Phase 4: 部署与文档 (Week 8)

| 任务 | 负责人 | 工时 | 产出 |
|------|--------|------|------|
| 安装脚本 | 后端 | 24h | install.sh |
| API 文档 | 后端 | 16h | OpenAPI |
| 配置 schema | 后端 | 8h | schema.json |
| 用户手册 | 文档 | 16h | 手册 |
| 集成测试 | 测试 | 16h | 报告 |

**里程碑**: v2.0.0 发布

---

## 7. 风险评估与应对

### 7.1 技术风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| 事件循环冲突修复后引入新问题 | 高 | 中 | 充分单元测试 |
| 数据库迁移丢失数据 | 高 | 低 | 备份+灰度发布 |
| 安装脚本兼容性问题 | 中 | 中 | 多环境测试 |

### 7.2 进度风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| 人力不足 | 高 | 中 | 优先完成 P0 |
| 需求变更 | 中 | 低 | 敏捷迭代 |

### 7.3 质量风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| 测试覆盖不足 | 高 | 中 | TDD 开发 |
| 回归问题 | 中 | 低 | 自动化测试 |

---

## 8. 测试计划

### 8.1 单元测试

| 模块 | 测试用例数 | 覆盖率目标 |
|------|-----------|------------|
| rule_engine | 20 | 90% |
| manager | 15 | 85% |
| api_client | 10 | 80% |
| connector | 15 | 85% |

### 8.2 集成测试

| 场景 | 说明 |
|------|------|
| API 认证流程 | OAuth2 完整流程 |
| 传感器数据采集 | 数据采集 → 存储 → 查询 |
| 规则触发 | 条件满足 → 动作执行 |
| 任务管理 | CRUD + 状态转换 |

### 8.3 性能测试

| 指标 | 目标值 |
|------|--------|
| API 响应时间 | P95 < 200ms |
| 并发连接数 | > 100 |
| 数据库查询 | < 50ms |

---

## 9. 部署计划

### 9.1 部署策略

| 环境 | 策略 | 回滚时间 |
|------|------|----------|
| 开发 | 直接部署 | - |
| 测试 | 自动化部署 | 5min |
| 生产 | 蓝绿部署 | 1min |

### 9.2 部署步骤

```bash
# 1. 备份当前版本
cp -r backend/heiman backend/heiman.bak

# 2. 执行数据库迁移
python -m heiman.migrate --target=v2

# 3. 安装新版本
pip install -e .

# 4. 启动服务
heiman-backend

# 5. 验证
curl http://localhost:1912/health
```

### 9.3 回滚步骤

```bash
# 1. 停止服务
pkill -f heiman-backend

# 2. 恢复备份
rm -rf backend/heiman
mv backend/heiman.bak backend/heiman

# 3. 恢复数据库
# (如需要，执行数据库回滚)

# 4. 重启服务
heiman-backend
```

---

## 10. 升级前后对比

### 10.1 功能对比

| 功能 | 升级前 | 升级后 |
|------|--------|--------|
| 传感器数据采集 | ✅ | ✅ |
| 事件分类告警 | ✅ | ✅ |
| 基础规则引擎 | ⚠️ | ✅ |
| 高级规则引擎 | ❌ | ✅ |
| 任务管理 | ❌ | ✅ |
| 人员管理 | ❌ | ✅ |
| 可观测性 | ❌ | ✅ |
| 自动化安装 | ❌ | ✅ |

### 10.2 质量对比

| 指标 | 升级前 | 升级后 |
|------|--------|--------|
| P0 问题数 | 4 | 0 |
| P1 问题数 | 4 | 0 |
| 测试覆盖率 | ~40% | >80% |
| API 响应时间 | 不稳定 | <200ms |

### 10.3 安全性对比

| 指标 | 升级前 | 升级后 |
|------|--------|--------|
| Token 管理 | 基础 | 加密存储+自动刷新 |
| 权限控制 | 无 | home_id 隔离 |
| 审计日志 | 部分 | 完整 |

---

## 11. 后续维护建议

### 11.1 持续集成

- [ ] 每次 PR 自动运行单元测试
- [ ] 每次合并自动运行集成测试
- [ ] 每次发布自动执行性能测试

### 11.2 监控告警

- [ ] 服务异常告警
- [ ] 磁盘空间告警
- [ ] API 延迟告警
- [ ] 错误率告警

### 11.3 版本规划

| 版本 | 目标 | 时间 |
|------|------|------|
| v2.0.0 | 稳定版发布 | Week 8 |
| v2.1.0 | Agent 调度器 | Week 12 |
| v2.2.0 | 家庭档案模块 | Week 16 |

---

## 12. 附录

### A. 参考文档

- [ANALYSIS_REPORT.md](file:///Users/haiman/Documents/trae_projects/heiman-agent/ANALYSIS_REPORT.md) - 对比分析报告
- [Miloco install-guide.md](https://raw.githubusercontent.com/XiaoMi/xiaomi-miloco/main/scripts/install-guide.md) - 安装指南参考

### B. 关键文件清单

| 文件 | 修改类型 |
|------|----------|
| rule_engine.py | 重构 |
| manager.py | 重构 |
| main.py | 扩展 |
| settings.py | 重构 |
| connector.py | 扩展 |
| 新增 task/ | 新增 |
| 新增 person/ | 新增 |
| 新增 observability/ | 新增 |
| 新增 install.sh | 新增 |

### C. 术语表

| 术语 | 说明 |
|------|------|
| rollover | 每日任务记录滚动更新 |
| idempotent | 幂等性，动作重复执行结果一致 |
| vacuum | SQLite 数据库空间回收 |
| TTL | Time To Live，生存时间 |

---

**文档结束**
