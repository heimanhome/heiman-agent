# Heiman-Agent API 参考

## 0. 概述

Heiman-Agent 后端基于 FastAPI 实现 RESTful API。默认监听 `http://127.0.0.1:1912`。

**认证方式**：所有 `/api/*` 端点需要 `Authorization: bearer <token>` 头部，`token` 来自 `server.token` 配置。

**OpenAPI 文档**：访问 <http://127.0.0.1:1912/docs> 或 <http://127.0.0.1:1912/redoc>。

## 1. 健康检查

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/health` | ❌ | 服务健康检查 |

**响应**：
```json
{"status": "healthy", "service": "heiman-agent"}
```

## 2. 传感器

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/sensors` | ✅ | 列出所有传感器 |
| GET | `/api/sensors/{did}` | ✅ | 传感器详情 |
| GET | `/api/sensors/{did}/history` | ✅ | 历史数据 |
| POST | `/api/sensors/data` | ✅ | 推送数据点 |

## 3. 事件

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/events` | ✅ | 列出事件（支持 `event_type`、`level`、`acknowledged`、`home_id` 过滤） |
| GET | `/api/events/{event_id}` | ✅ | 事件详情 |
| POST | `/api/events/{event_id}/acknowledge` | ✅ | 确认事件 |

## 4. 规则

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/rules` | ✅ | 列出规则（支持 `enabled` 过滤） |
| GET | `/api/rules/{rule_id}` | ✅ | 规则详情 |
| POST | `/api/rules` | ✅ | 创建规则 |
| PUT | `/api/rules/{rule_id}` | ✅ | 更新规则 |
| DELETE | `/api/rules/{rule_id}` | ✅ | 删除规则 |
| POST | `/api/rules/{rule_id}/enable` | ✅ | 启用 |
| POST | `/api/rules/{rule_id}/disable` | ✅ | 禁用 |
| POST | `/api/rules/{rule_id}/test` | ✅ | 测试 |
| GET | `/api/rules/stats` | ✅ | 规则执行统计 |

## 5. 设备

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/devices` | ✅ | 列出设备 |
| GET | `/api/devices/{device_id}` | ✅ | 设备详情 |
| POST | `/api/devices` | ✅ | 创建设备 |
| PUT | `/api/devices/{device_id}` | ✅ | 更新设备 |
| DELETE | `/api/devices/{device_id}` | ✅ | 删除设备 |
| POST | `/api/devices/{device_id}/toggle` | ✅ | 切换开关 |

## 6. 家庭

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/homes` | ✅ | 列出家庭 |
| GET | `/api/homes/{home_id}` | ✅ | 家庭详情 |
| POST | `/api/homes` | ✅ | 创建家庭 |
| PUT | `/api/homes/{home_id}` | ✅ | 更新家庭 |
| DELETE | `/api/homes/{home_id}` | ✅ | 删除家庭 |
| POST | `/api/homes/{home_id}/members` | ✅ | 添加成员 |
| DELETE | `/api/homes/{home_id}/members/{member_id}` | ✅ | 移除成员 |
| PUT | `/api/homes/{home_id}/members/{member_id}` | ✅ | 更新成员 |

## 7. 人员（v2.1 新增）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/persons` | ✅ | 列出所有人员 |
| GET | `/api/persons/{person_id}` | ✅ | 人员详情 |
| POST | `/api/persons` | ✅ | 创建人员 |
| PUT | `/api/persons/{person_id}` | ✅ | 更新人员 |
| DELETE | `/api/persons/{person_id}` | ✅ | 删除人员 |

**创建人员请求体**：
```json
{
  "name": "Alice",
  "role": "mother"
}
```

**响应**：
```json
{
  "id": "uuid-xxx",
  "name": "Alice",
  "role": "mother",
  "created_at": "2026-06-25T10:00:00",
  "updated_at": "2026-06-25T10:00:00"
}
```

## 8. 任务（v2.1 新增）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/tasks` | ✅ | 列出任务 |
| GET | `/api/tasks/{task_id}` | ✅ | 任务详情 |
| POST | `/api/tasks` | ✅ | 创建任务 |
| PATCH | `/api/tasks/{task_id}` | ✅ | 更新任务描述 |
| DELETE | `/api/tasks/{task_id}` | ✅ | 删除任务 |
| POST | `/api/tasks/{task_id}/pause` | ✅ | 暂停任务 |
| POST | `/api/tasks/{task_id}/resume` | ✅ | 恢复任务 |
| POST | `/api/tasks/{task_id}/links` | ✅ | 添加任务关联 |
| POST | `/api/tasks/{task_id}/record` | ✅ | 初始化任务记录 |
| POST | `/api/tasks/{task_id}/progress/increment` | ✅ | 进度型：递增 |
| POST | `/api/tasks/{task_id}/session/start` | ✅ | 时长型：开始会话 |
| POST | `/api/tasks/{task_id}/session/end` | ✅ | 时长型：结束会话 |
| POST | `/api/tasks/{task_id}/event/append` | ✅ | 事件型：追加事件 |

### 8.1 三种任务类型

**进度型（progress）**：
```json
{
  "description": "每天走 10000 步",
  "kind": "progress",
  "target": 10000,
  "unit": "steps",
  "window": "day"
}
```

**时长型（duration）**：
```json
{
  "description": "每天学习 2 小时",
  "kind": "duration",
  "target_minutes": 120
}
```

**事件型（event）**：
```json
{
  "description": "本周读书",
  "kind": "event"
}
```

### 8.2 任务关联

任务可与 rule 或 cron 表达式关联：

```json
{
  "link_kind": "rule",
  "link_ref": "rule_001"
}
```

全局唯一约束：`(link_kind, link_ref)`。

## 9. 可观测性（v2.1 新增）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/observability/overview` | ✅ | 监控总览 |
| GET | `/api/observability/system` | ✅ | 系统指标（CPU/内存/磁盘/uptime） |
| GET | `/api/observability/sensor` | ✅ | 传感器统计 |
| GET | `/api/observability/rule` | ✅ | 规则引擎统计 |
| GET | `/api/observability/event` | ✅ | 事件统计 |
| GET | `/api/observability/database` | ✅ | 数据库统计 |

**总览响应**：
```json
{
  "system": {
    "cpu_percent": 12.5,
    "memory_percent": 45.0,
    "memory_used_mb": 18000.0,
    "memory_total_mb": 65536.0,
    "disk_percent": 0.5,
    "disk_used_gb": 11.0,
    "disk_total_gb": 7449.0,
    "uptime_seconds": 3600.0
  },
  "sensor": {
    "total_sensors": 12,
    "online_sensors": 11,
    "offline_sensors": 1,
    "data_points_today": 1024,
    "data_points_total": 100000,
    "by_type": {"SMOKE": 4, "TEMPERATURE": 4, "HUMIDITY": 4}
  },
  "rule": {
    "total_rules": 8,
    "enabled_rules": 6,
    "triggered_today": 12,
    "triggered_total": 1024,
    "actions_executed_today": 24
  },
  "event": {
    "total_events": 256,
    "events_today": 4,
    "by_level": {"HIGH": 2, "INFO": 250},
    "by_type": {"smoke": 1, "temperature": 3},
    "unacknowledged": 1
  },
  "database": {
    "db_size_mb": 5.2,
    "table_count": 13,
    "sensor_logs_count": 100000,
    "events_count": 256,
    "rules_count": 8
  }
}
```

## 10. 监控（资源监控）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/monitor/status` | ✅ | 节点状态 |
| GET | `/api/monitor/memory` | ✅ | 内存快照 |
| GET | `/api/monitor/resources` | ✅ | 资源使用 |
| GET | `/api/monitor/events` | ✅ | 事件日志 |

## 11. 日志

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/logs` | ✅ | 系统日志（支持 `level`、`action`、`user`、`search` 过滤） |
| GET | `/api/logs/operation` | ✅ | 操作日志 |
| GET | `/api/logs/error` | ✅ | 错误日志 |
| GET | `/api/logs/export` | ✅ | 导出日志（CSV） |

## 12. 模型

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/models` | ✅ | 列出模型 |
| GET | `/api/models/{model_id}` | ✅ | 模型详情 |
| POST | `/api/models/{model_id}/deploy` | ✅ | 部署模型 |
| POST | `/api/models/{model_id}/stop` | ✅ | 停止模型 |
| PUT | `/api/models/{model_id}/configure` | ✅ | 配置模型 |
| POST | `/api/models/upload` | ✅ | 上传模型 |

## 13. 错误码

| 状态码 | 含义 | 业务码 |
|--------|------|--------|
| 200 | 成功 | - |
| 400 | 请求参数错误 | 1000-1099 |
| 401 | 未认证 | 3000-3099 |
| 403 | 无权限 | 3001 |
| 404 | 资源不存在 | 2000-2099 |
| 409 | 资源冲突 | 4090 |
| 422 | 字段验证失败 | 1010 |
| 429 | 限流 | 4290 |
| 500 | 服务器内部错误 | 9000 |
| 503 | 服务不可用 | 5030-5031 |

**错误响应格式**：
```json
{
  "code": 1010,
  "message": "Rule validation failed",
  "data": null
}
```

## 14. 限流与配额

- 默认无显式限流
- 建议在反向代理层（Nginx/Caddy）配置 rate-limit
