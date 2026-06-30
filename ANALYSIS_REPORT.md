# Heiman-Agent vs Xiaomi-Miloco 系统性对比分析报告

## 1. 项目概述

| 项目 | Heiman-Agent | Xiaomi-Miloco |
|------|-------------|---------------|
| 定位 | 海曼传感器智能Agent | 小米智能家居感知平台 |
| 核心数据源 | 烟雾、温湿度、一氧化碳、水浸传感器 | 摄像头视频流 |
| 技术栈 | Python + FastAPI + SQLite | Python + FastAPI + SQLite |
| 部署模式 | 单实例本地服务 | 单实例本地服务(workers=1强制约束) |

---

## 2. 后端核心模块对比

### 2.1 模块完整性对比

| 模块 | Miloco | Heiman-Agent | 状态 |
|------|--------|-------------|------|
| **config/** | 完整(多层配置+重置钩子) | 基础(.env) | ⚠️ 简化 |
| **database/** | 完整(18张表) | 基础(7张表) | ⚠️ 缺少核心表 |
| **middleware/** | 完整 | 完整 | ✅ |
| **node_monitor/** | 完整(资源监控+看门狗) | 基础 | ⚠️ 简化 |
| **router/** | 完整 | 基础 | ⚠️ 缺少路由 |
| **rule/** | 完整(V3引擎) | 基础 | ⚠️ 简化 |
| **dispatch/** | ✅ | ❌ | ❌ 缺失 |
| **home_profile/** | ✅ | ❌ | ❌ 缺失 |
| **miot/** | ✅ | ❌ | ❌ 缺失(替换为heiman client) |
| **observability/** | ✅ | ❌ | ❌ 缺失 |
| **perception/** | ✅(复杂) | ❌(简化为collector) | ⚠️ 架构差异 |
| **person/** | ✅ | ❌ | ❌ 缺失 |
| **task/** | ✅ | ❌ | ❌ 缺失 |
| **task_record/** | ✅ | ❌ | ❌ 缺失 |

### 2.2 配置管理对比

**Miloco配置系统** ([settings.py](file:///Users/haiman/Documents/trae_projects/xiaomi-miloco/backend/miloco/src/miloco/config/settings.py)):
- 四层优先级: 环境变量 > config.json > settings.yaml > 代码默认值
- 支持 `reset_settings()` 动态重载
- 派生路径自动计算(computed_field)
- 时区配置、性能指标配置、感知管线配置等

**Heiman配置系统** ([settings.py](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/config/settings.py)):
- 仅支持 `.env` 文件
- 无动态重载机制
- 派生路径硬编码
- 缺少: 时区配置、性能开关、日志TTL等

**问题**: `static_dir` 计算路径依赖相对路径，在不同工作目录运行时可能出错。

### 2.3 数据库对比

**Miloco数据库表结构** ([connector.py](file:///Users/haiman/Documents/trae_projects/xiaomi-miloco/backend/miloco/src/miloco/database/connector.py)):
```
核心表: person, biometric, perception_log, meaningful_events
规则表: rule, rule_log
任务表: task, task_link, task_record_progress, task_record_duration, 
        task_record_duration_session, task_record_event, task_record_event_entry
其他: device_lru, token_usage, token_usage_daily, task_terminate_log
```

**Heiman数据库表结构** ([connector.py](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/database/connector.py)):
```
sensor_logs, events, rules, kv, device_lru, system_logs, models
```

**缺失表**: person, task, task_record_*, token_usage, meaningful_events

### 2.4 Rule引擎对比

**Miloco Rule Engine** ([service.py](file:///Users/haiman/Documents/trae_projects/xiaomi-miloco/backend/miloco/src/miloco/rule/service.py)):
- V3验证矩阵(措辞校验、模式矩阵、生命周期、幂等性/冷却配对)
- 支持event/state两种模式
- on_enter/on_exit动作
- 任务关联(task_link)
- terminate_when临时规则
- duration_ratio滑窗评估
- 日志查询与清理

**Heiman Rule Engine** ([rule_engine.py](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/rule/rule_engine.py)):
- 仅支持基础条件判断(比较运算符)
- 仅支持ALERT/LOG/WEBHOOK/MESSAGE动作
- 冷却机制仅基于规则级别
- 无任务关联
- 无状态模式

**逻辑错误**: 
1. `execute_action()` 中使用 `asyncio.run()` 创建新事件循环，与FastAPI事件循环冲突
2. 缺少规则模式验证(如event/state模式互斥字段校验)
3. 缺少action幂等性校验

### 2.5 Manager对比

**Miloco Manager** ([manager.py](file:///Users/haiman/Documents/trae_projects/xiaomi-miloco/backend/miloco/src/miloco/manager.py)):
```python
# 初始化链:
MIoT Proxy → MIoT Service → Person Service → Home Profile Service
→ Rule Service → Terminate Evaluator → Perception Service → Task Service
```

**Heiman Manager** ([manager.py](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/manager.py)):
```python
# 初始化链:
HeimanApiClient → SensorDeviceAdapter → SensorCollector
→ EventClassifier → RuleEngine → Repos
```

**问题**: 
1. `await self._api_client.login()` 在初始化时阻塞，若网络不可用会导致启动失败
2. 缺少设备UUID初始化
3. 缺少感知服务管理

### 2.6 后台任务对比

**Miloco后台任务** ([main.py](file:///Users/haiman/Documents/trae_projects/xiaomi-miloco/backend/miloco/src/miloco/main.py)):
- `_log_cleanup_loop()` - 日志清理(感知日志、规则日志、observability表、事件截图)
- `_rollover_daily_loop()` - 每日任务记录rollover(0:05触发)
- `_backfill_tier_a_reid_embeddings()` - ReID嵌入补全

**Heiman后台任务** ([main.py](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/main.py)):
- `_periodic_refresh()` - 传感器数据定时刷新

**缺失**: 日志TTL清理、每日rollover、数据库增量vacuum

### 2.7 缺失核心模块详细分析

#### 2.7.1 dispatch/ (Agent调度器)
- **功能**: 管理agent turn调度，同步等待agent响应，队列管理
- **缺失影响**: 无法与智能Agent平台集成进行事件推送和交互

#### 2.7.2 home_profile/ (家庭档案)
- **功能**: 家庭画像管理，成员关系，场景配置
- **缺失影响**: 无法实现个性化服务和家庭场景识别

#### 2.7.3 observability/ (可观测性)
- **功能**: 性能指标采集、trace记录、agent运行监控、token使用统计
- **缺失影响**: 无法监控系统性能、定位问题、优化资源使用

#### 2.7.4 person/ (人员管理)
- **功能**: 家庭成员管理、身份注册、生物特征存储
- **缺失影响**: 无法区分不同用户、无法实现个性化通知

#### 2.7.5 task/ & task_record/ (任务管理)
- **功能**: 任务创建/删除、进度追踪、时长记录、事件记录、每日rollover
- **缺失影响**: 无法实现习惯养成、健康目标等长期追踪功能

---

## 3. 前端模块对比

### 3.1 页面完整性

| 页面 | Miloco | Heiman-Agent |
|------|--------|-------------|
| Dashboard | ✅ | ✅ |
| Devices | ✅ | ✅ |
| Events | ✅ | ✅ |
| Homes | ✅ | ✅ |
| Rules | ✅ | ✅ |
| Login | ✅ | ✅ |
| Profile | ✅ | ✅ |
| **Person/Family** | ✅ | ❌ |
| **Task Management** | ✅ | ❌ |
| **Perception Logs** | ✅ | ⚠️ (简化) |
| **Observability/Metrics** | ✅ | ❌ |
| **Model Configuration** | ✅ | ⚠️ (简化) |

### 3.2 功能缺失

1. **人员管理界面** - 无法添加/管理家庭成员
2. **任务管理界面** - 无法创建和追踪任务进度
3. **性能指标面板** - 无系统监控和性能数据展示
4. **感知日志详情** - 缺少摄像头帧级日志(传感器场景下需适配)

---

## 4. CLI模块对比

### 4.1 命令完整性

| 命令 | Miloco | Heiman-Agent |
|------|--------|-------------|
| auth | ✅ | ✅ |
| device | ✅ | ✅ |
| event | ✅ | ✅ |
| rule | ✅ | ✅ |
| health | ✅ | ✅ |
| **person** | ✅ | ❌ |
| **task** | ✅ | ❌ |
| **config** | ✅ | ⚠️ |
| **admin** | ✅ | ⚠️ |
| **monitor** | ✅ | ⚠️ |
| **doctor** | ✅ | ❌ |
| **account** | ✅ | ❌ |
| **service** | ✅ | ⚠️ |

**问题**: Heiman CLI缺少关键管理命令(person, task, doctor)

---

## 5. 插件模块对比

### 5.1 OpenClaw插件

**Miloco插件** ([src/](file:///Users/haiman/Documents/trae_projects/xiaomi-miloco/plugins/openclaw/src)):
- 完整的Webhook路由
- 后端服务客户端
- 通知工具
- Mock SDK
- 技能同步脚本

**Heiman插件** ([openclaw/](file:///Users/haiman/Documents/trae_projects/heiman-agent/plugins/openclaw)):
- 基础Webhook路由
- 后端服务客户端
- 通知工具
- 技能同步脚本

**缺失**: Mock SDK、hooks系统、完整的技能集

---

## 6. 文档对比

### 6.1 Miloco文档结构

```
docs/
├── overview/
├── features/
├── api/
├── dev-guide/
├── external-deps/
├── design/
└── prompts/
```

### 6.2 Heiman文档结构

```
knowledge/
├── 01-overview/
├── 02-features/
├── 03-api/
├── 04-dev-guide/
├── 05-external-deps/
├── 06-design/
└── 07-prompts/
```

### 6.3 文档缺失分析

| 文档主题 | Miloco | Heiman |
|----------|--------|--------|
| 安装指南 | ✅(install-guide.md) | ❌ |
| 配置参考 | ✅(settings.schema.json) | ❌ |
| 规则设计 | ✅(rule-design.md) | ❌ |
| API参考 | ✅ | ⚠️ |
| 开发指南 | ✅ | ✅ |

---

## 7. 安装流程对比

### 7.1 Miloco安装流程

**install.sh** 三阶段模式:
1. **--agent-prepare**: 环境检查、依赖安装、服务启动、获取状态
2. **--agent-ask**: Agent收集用户配置(账号授权码、模型API Key)
3. **--agent-finish**: 写入配置、下载模型、安装插件

**关键特性**:
- JSON输出格式便于Agent解析
- 支持增量配置(跳过已配置项)
- 自动处理Python环境
- 包含故障排除逻辑

### 7.2 Heiman安装流程

当前仅支持手动安装:
```bash
cd backend/heiman
pip install -e .
heiman-backend
```

**缺失**:
- 自动化安装脚本
- 环境检测
- Agent交互模式
- 配置引导
- 依赖自动安装

---

## 8. 已实现功能逻辑审查

### 8.1 严重问题

| 问题 | 文件 | 描述 |
|------|------|------|
| 事件循环冲突 | [rule_engine.py:131](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/rule/rule_engine.py#L131) | `asyncio.run()` 在FastAPI事件循环中创建新循环 |
| 启动阻塞 | [manager.py:43](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/manager.py#L43) | `await self._api_client.login()` 无超时处理 |
| 静态资源路径 | [settings.py:49](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/config/settings.py#L49) | 相对路径硬编码，可能导致部署路径错误 |

### 8.2 中等问题

| 问题 | 文件 | 描述 |
|------|------|------|
| 缺少字段验证 | [rule_engine.py:69-84](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/rule/rule_engine.py#L69) | 规则条件评估缺少字段类型校验 |
| 无幂等性保护 | [rule_engine.py](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/rule/rule_engine.py) | 动作执行无幂等性检查，可能重复触发 |
| 无数据清理 | [main.py](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/main.py) | 缺少日志TTL清理和数据库vacuum |
| 无错误恢复 | [manager.py](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/manager.py) | API客户端登录失败无重试机制 |

### 8.3 轻微问题

| 问题 | 文件 | 描述 |
|------|------|------|
| 缺少异常类型 | [middleware/exceptions.py](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/middleware/exceptions.py) | 缺少业务异常类型(ValidationException等) |
| 缺少配置重置 | [config/settings.py](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/config/settings.py) | 无reset_settings机制 |
| API路由前缀 | [main.py:136](file:///Users/haiman/Documents/trae_projects/heiman-agent/backend/heiman/src/heiman/main.py#L136) | 部分路由无前缀`/api` |

---

## 9. 缺失功能优先级排序

### P0 - 核心功能缺失

1. **日志清理机制** - 防止数据库无限增长
2. **API客户端错误恢复** - 提升系统稳定性
3. **规则引擎幂等性** - 防止重复动作执行
4. **事件循环修复** - 解决asyncio.run冲突

### P1 - 重要功能缺失

5. **任务管理模块** - 习惯养成、目标追踪
6. **人员管理模块** - 家庭成员管理
7. **可观测性模块** - 性能监控、问题定位
8. **自动化安装脚本** - 简化部署流程

### P2 - 增强功能缺失

9. **家庭档案模块** - 个性化服务
10. **Agent调度器** - 智能交互集成
11. **CLI命令补全** - person/task/doctor命令
12. **配置系统增强** - 多层配置、动态重载

---

## 10. 建议实施计划

### Phase 1: 稳定性修复(1-2周)
- 修复事件循环冲突
- 添加API客户端重试机制
- 实现日志TTL清理
- 添加数据库增量vacuum

### Phase 2: 核心功能补齐(2-3周)
- 实现任务管理模块(task/task_record)
- 实现人员管理模块(person)
- 增强规则引擎(V2验证矩阵)
- 添加配置重置机制

### Phase 3: 可观测性(1-2周)
- 实现性能指标采集
- 添加token使用统计
- 实现监控API
- 添加CLI doctor命令

### Phase 4: 部署与文档(1周)
- 编写自动化安装脚本
- 完善API文档
- 添加配置schema
- 编写规则设计文档

---

## 11. 总结

### 已完成功能
- ✅ 传感器数据采集(海曼HTTP协议)
- ✅ 事件分类与告警
- ✅ 基础规则引擎
- ✅ RESTful API接口
- ✅ OAuth2认证集成
- ✅ Web前端界面(基础)
- ✅ OpenClaw插件(基础)
- ✅ 多语言国际化

### 核心差距
1. **架构层面**: 缺少Agent调度器、可观测性、家庭档案等核心模块
2. **功能层面**: 缺少任务管理、人员管理、复杂规则逻辑
3. **运维层面**: 缺少自动化安装、日志清理、性能监控
4. **稳定性层面**: 存在事件循环冲突、启动阻塞等严重问题

### 下一步建议
优先修复P0级别的稳定性问题，然后逐步补齐任务管理和人员管理等核心业务模块，最后完善可观测性和部署流程。