# Heiman Agent REST API 协议

后端基址：`http://127.0.0.1:1912`（默认端口 1912，可在 `.env` 中通过 `SERVER_PORT` 修改）。

## 鉴权

除 `/health` 外，所有 `/api/*` 接口都需要鉴权。服务级调用使用服务令牌：

```
Authorization: Bearer <SERVER_TOKEN>
```

`SERVER_TOKEN` 默认值 `heiman_test_token_123`，可在 `backend/heiman/.env` 中覆盖。
也支持查询串形式：`?token=<SERVER_TOKEN>` 或 `?access_token=<access_token>`。

调用方式（技能脚本已封装）：

```bash
python scripts/heiman_ctl.py api GET /api/sensors
python scripts/heiman_ctl.py api POST /api/events/<event_id>/acknowledge
python scripts/heiman_ctl.py api POST /api/rules --data '{"name":"...","conditions":[...]}'
```

## 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 返回 `{"status":"healthy","service":"heiman-agent"}`；子系统 FAILED/STALLED 时返回 503 |

注意：健康检查**没有** `/api` 前缀，`/api/health` 会返回 404。

## 端点总表

### 通用查询参数

| 参数 | 适用接口 | 说明 |
|------|----------|------|
| `home_id` | `/api/devices`、`/api/sensors`、`/api/rooms`、事件类接口 | **多家庭账号务必显式指定**。不传时后端客户端固定取 `homes[0]`，可能命中没有设备的家庭，返回 `success: true` + `data: []`（HTTP 200，不报错）。详见 `troubleshooting.md` 第 6 条 |
| `hours` | `/api/sensors/{did}/history` | ⚠️ **该接口不存在此参数**（传了会被静默忽略） |
| `start_time` / `end_time` | `/api/sensors/{did}/history` | 时间窗口，ISO8601（如 `2026-09-21T00:00:00+00:00`）；`start_time` = 只看该时刻之后 |
| `limit` | `/api/sensors/{did}/history` | 返回条数上限，默认 `100`，**最大 `1000`**（超出返回 422） |

> ⚠️ `/api/sensors/{did}/history` **没有 `hours` 参数**。传入的 `hours` 会被 FastAPI 静默忽略（HTTP 200、不报错），
> 结果退化为「最近 `limit` 条」，趋势窗口失真。要按小时回溯请自行换算 `start_time = now − N 小时`；
> `heiman_snapshot.py --hours N` 已内置该换算。

示例：

```bash
python scripts/heiman_ctl.py api GET "/api/devices?home_id=<目标家庭ID>"
python scripts/heiman_ctl.py api GET "/api/sensors/{did}/history?start_time=2026-09-21T00:00:00%2B00:00&limit=1000"
```

### 传感器 `/api/sensors`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sensors` | 传感器实时列表（含 `sensor_type`、`value`、`status`、`battery`、各 `*State` 字段）；支持 `?home_id=` |
| GET | `/api/sensors/{did}` | 单个传感器详情 |
| GET | `/api/sensors/{did}/history` | 历史数据（`?start_time=` + `?end_time=` + `?limit=`，**无 `hours`**） |
| POST | `/api/sensors/data` | 手动写入一条传感器数据 |

### 设备 `/api/devices`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/devices` | 设备列表（含 `productName`、`parentId`、`deriveMetadata`）；支持 `?home_id=` |
| GET | `/api/devices/{device_id}` | 单设备详情 |
| GET | `/api/devices/{device_id}/panel` | 设备面板定义 |
| POST | `/api/devices/{device_id}/toggle` | 开关类设备翻转 |
| POST | `/api/devices/{device_id}/control` | 下发控制指令 |
| POST | `/api/devices/panel/session/close` | 关闭面板会话 |

### 事件 `/api/events`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/events` | 事件列表 |
| GET | `/api/events/{event_id}` | 事件详情 |
| GET | `/api/events/stats` | 事件统计 |
| GET | `/api/events/stream` | SSE 实时事件流 |
| GET | `/api/events/stream/status` | SSE 连接状态 |
| POST | `/api/events/{event_id}/acknowledge` | 确认单条事件 |
| POST | `/api/events/batch/acknowledge` | 批量确认 |

### 规则 `/api/rules`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/rules` | 规则列表 |
| GET | `/api/rules/{rule_id}` | 规则详情 |
| GET | `/api/rules/stats` | 规则统计 |
| POST | `/api/rules` | 创建规则 |
| PUT | `/api/rules/{rule_id}` | 更新规则 |
| DELETE | `/api/rules/{rule_id}` | 删除规则 |
| POST | `/api/rules/{rule_id}/conditions` | 追加条件 |
| POST | `/api/rules/{rule_id}/actions` | 追加动作 |
| GET | `/api/rules/suggestions` | AI 规则建议列表 |
| POST | `/api/rules/suggestions/generate` | 生成规则建议 |
| POST | `/api/rules/suggestions/{id}/approve` | 采纳建议 |
| POST | `/api/rules/suggestions/{id}/reject` | 拒绝建议 |

### 家庭与房间 `/api/homes` `/api/rooms`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/homes` | 家庭列表 |
| GET | `/api/homes/{home_id}` | 家庭详情 |
| POST / PUT / DELETE | `/api/homes` `/api/homes/{home_id}` | 增改删家庭 |
| POST | `/api/homes/{home_id}/members` | 添加成员 |
| GET | `/api/rooms` | 房间列表 |

### 家庭成员 `/api/identity`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/identity/persons` | 人员列表 |
| POST | `/api/identity/persons` | 创建人员 |
| PUT / DELETE | `/api/identity/persons/{person_id}` | 更新 / 删除 |
| POST | `/api/identity/persons/sync` | 从海曼云端同步人员 |

### 任务 `/api/tasks`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tasks` | 任务列表（去重视图） |
| GET | `/api/tasks/{task_id}` | 任务详情 |
| POST | `/api/tasks` | 创建任务 |
| POST | `/api/tasks/{task_id}/progress/increment` | 进度累加 |
| POST | `/api/tasks/{task_id}/session/start` `.../end` | 会话计时 |
| POST | `/api/tasks/{task_id}/event/append` | 追加任务事件 |
| GET | `/api/tasks/{task_id}/record` | 任务记录 |
| DELETE | `/api/tasks/{task_id}` | 删除任务 |

### AI 分析 `/api/ai`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/ai/anomaly` | 异常检测结果 |
| GET | `/api/ai/anomaly/behavior` | 行为异常 |
| GET | `/api/ai/comfort` | 舒适度评估 |
| GET | `/api/ai/activity` `/api/ai/activity/routine` | 活动识别 / 作息规律 |
| GET | `/api/ai/analyze` `/api/ai/analyze/fused` | 综合 / 融合分析 |
| GET | `/api/ai/suggest` `/api/ai/suggestions` | 建议 |
| GET | `/api/ai/summary` | 摘要 |
| GET | `/api/ai/health` | AI 子系统健康 |
| GET | `/api/ai/habits` | 习惯画像 |
| GET | `/api/ai/emotion` `/api/ai/emotion/profile` | 情绪引擎 |
| GET | `/api/ai/assistant` | 智能助手入口 |
| GET | `/api/ai/alerts` `/api/ai/alerts/{analysis_id}` `/api/ai/alerts/event/{event_id}` | 告警分析 |
| POST | `/api/ai/learning/start` `/stop` `/trigger` `/feedback` | 自学习系统 |
| GET | `/api/ai/learning/status` `/performance` `/cycles` `/rules` | 自学习状态 |
| GET | `/api/ai/energy/stats` `/report` `/optimization` | 能耗分析 |
| GET | `/api/ai/devices` | AI 视角设备列表 |
| GET | `/api/ai/ml/models` `/api/ai/ml/models/{name}` | ML 模型管理 |
| POST | `/api/ai/ml/models/{name}/train` | 触发训练 |
| GET | `/api/ai/ml/explain/{model_name}` | 模型可解释性 |
| GET | `/api/ai/ml/ab/status` `/api/ai/ml/online/status` | A/B 与在线学习 |
| GET | `/api/ai/perception/events` `/perception/identity` | 感知引擎 |

### 模型 `/api/models`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/models` | 模型列表 |
| POST | `/api/models/{model_id}/deploy` `/stop` | 部署 / 停止 |
| PUT | `/api/models/{model_id}/configure` | 配置 |
| POST | `/api/models/upload` | 上传模型 |

### 可观测性 `/api/observability`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/observability/overview` | 系统总览 |
| GET | `/api/observability/system` `/sensor` `/rule` `/event` `/database` | 分项指标 |
| GET | `/api/observability/token-usage` `/token-usage/daily` `/token-usage/buckets` | LLM Token 用量 |
| GET | `/api/observability/performance` `/stats` | 性能与统计 |
| GET | `/api/observability/traces` `/traces/{trace_id}` | 调用链 |
| GET | `/api/observability/agent-runs` | Agent 运行记录 |

### 节点监控 `/api/monitor`

`/status` `/nodes` `/nodes/{name}` `/resources` `/memory` `/memory/series`

### 日志 `/api/logs`

`/api/logs` `/operation` `/error` `/export` `/device`

### 管理 `/api/admin`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/status` | 系统状态 |
| GET / POST | `/api/admin/debug` | 调试开关读写 |
| POST | `/api/admin/debug/log-pack` | 生成日志包 |
| GET / PUT | `/api/admin/heiman-config` | 读写海曼账号配置 |
| POST | `/api/admin/heiman-config/test` | 测试海曼云端连通性 |
| POST | `/api/admin/heiman-config/activate` | 激活指定配置 |

### 家庭画像 `/api/home-profile`

`/entries` `/rendered` `/commit` `/import` `/reset` `/profile:write` `/candidates:write` `/subject:reassign`

### 认证 `/api/auth`

`GET/POST /api/auth/login`、`GET /api/auth/token`、`POST /api/auth/refresh`、`GET /api/auth/me`、`GET /api/auth/profile`、`POST /api/auth/logout`、`POST /api/auth/home-select`、`GET /api/auth/last-home`。

## 海曼云端代理

后端把海曼云 API 原样代理出来，便于排查云端问题：

```
/heiman-cloud/{path}        # 生产
/heiman-cloud-cn/{path}     # 国内
/heiman-cloud-test/{path}   # 测试
```

示例：`GET http://127.0.0.1:1912/heiman-cloud/api-app/device/get/listByPage`

## 海曼云端 MQTT

| 方向 | Topic |
|------|-------|
| 设备上报 | `/{productId}/{deviceId}/properties/report` |
| 设备事件 | `/{productId}/{deviceId}/event/{eventId}` |
| 平台读属性 | `/{productId}/{deviceId}/properties/read` |
| 平台写属性 | `/{productId}/{deviceId}/properties/write` |
| 平台调功能 | `/{productId}/{deviceId}/function/invoke` |

Broker：`mqtt.heiman.cn:1884`（SSL），由 `HEIMAN_SECURE_ID` / `HEIMAN_SECURE_KEY` 鉴权。
