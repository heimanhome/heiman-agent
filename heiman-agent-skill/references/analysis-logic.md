# 分析逻辑与工作流

## 通用分析流程

```
用户请求
    │
    ▼
┌─────────────────┐
│  意图识别        │  日报/周报 · 实时查询 · 设备控制 · 问题诊断
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
上下文完整?  不完整 → 依次获取：家庭 → 设备 → 状态 → 告警日志
    │
    ▼
┌─────────────────────────┐
│ 数据验证与异常检测        │  离线设备标记 · 空值处理 · 一致性检查
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 多维度分析               │  安全预警 · 环境舒适度 · 设备健康度 · 趋势
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 报表生成                 │  结构化 JSON · 自然语言摘要 · 行动建议
└─────────────────────────┘
```

## 数据获取步骤

### 步骤 1：确定家庭

```bash
python scripts/heiman_ctl.py api GET /api/homes
```

取 `data[0].id` 作为 `homeId`。多家庭时向用户确认。

### 步骤 2：获取设备列表

```bash
python scripts/heiman_ctl.py api GET /api/devices
python scripts/heiman_ctl.py api GET /api/sensors
```

按 `type` / `sensor_type` 归类，统计在线 / 离线数量。
设备名（`name` / `productName`）中含"烟雾 / CO / 一氧化碳 / 温湿度 / 温感 / 门磁 / 水浸"等关键词时可用于辅助识别。

### 步骤 3：获取实时状态

```bash
python scripts/heiman_ctl.py api GET /api/sensors/{did}
```

`GET /api/sensors` 已返回全部实时属性，通常无需逐个再查。

### 步骤 4：获取告警与事件

```bash
python scripts/heiman_ctl.py api GET /api/events
python scripts/heiman_ctl.py api GET "/api/events/stats"
python scripts/heiman_ctl.py api GET "/api/sensors/{did}/history?start_time=<now-24h ISO8601>&limit=1000"
```

时间范围约定：日报 = 当天 00:00 至今；周报 = 7 天前 00:00 至今；月报 = 30 天前 00:00 至今。

### 步骤 5：数据清洗

1. 过滤断电重启产生的瞬时空值（`null`）；
2. 标记离线超过 60 分钟的设备；
3. `room_name` 为字符串 `"None"` 或 `null` 时归一化为"未分配房间"；
4. 去重并按时间倒序。

## 安全评分算法

```python
def calculate_safety_score(devices, alarms):
    score = 100

    # 告警扣分
    for alarm in alarms:
        if alarm.level == "CRITICAL":
            score -= 20
        elif alarm.level == "HIGH":
            score -= 10
        elif alarm.level == "MEDIUM":
            score -= 5

    # 在线率扣分
    online_rate = online_count / total_count
    if online_rate < 0.9:
        score -= 10

    # 电池扣分
    low_battery_count = sum(1 for d in devices if d.battery not in (None, -1) and d.battery < 20)
    score -= low_battery_count * 5

    return max(0, min(100, score))
```

网关设备（`battery == -1`）不参与电池扣分。

## 紧急告警流程

```
检测到紧急告警
(smokeState=1、gasState=1 或 CO 浓度 value>=400 ppm、waterState=1)
         │
         ▼
┌─────────────────┐
│ 立即通知 (P0)   │  不等待用户请求
│ 推送 + 记日志    │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 生成事件报告     │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 等待确认/处理    │
└─────────────────┘
```

## 离线设备处理流程

```
获取设备列表
    │
    ▼
识别 offline 设备
    │
    ▼
检查离线时长（对比最后在线时间）
    │
┌───┴────┐
▼        ▼
< 1h    >= 1h
忽略    标注"设备离线"，建议检查电源与网络
```

## 意图路由表

| 用户意图 | 关键词 | 数据来源 |
|----------|--------|----------|
| 全量概览 | 传感器、设备、全部、状态 | `/api/sensors` + `/api/devices` |
| 单设备查询 | 客厅温度、书房湿度 | `/api/sensors` 按 `name` 匹配 |
| 告警排查 | 异常、告警、报警、有没有事 | `/api/events` + `/api/sensors` 状态位 |
| 历史趋势 | 历史、趋势、变化、这周 | `/api/sensors/{did}/history` |
| 规则管理 | 规则、自动化、触发 | `/api/rules` |
| 家庭信息 | 家庭、成员、房间 | `/api/homes` `/api/rooms` `/api/identity/persons` |
| 系统健康 | 服务、状态、健康、监控 | `/health` `/api/observability/overview` |
| 报告生成 | 报告、日报、周报、总结 | 上述组合 → templates/ |

## 约束

- 单次查询最多返回 100 条历史记录，历史数据默认保留 30 天；
- 实时数据延迟不超过 1 个采集周期（默认 30 秒，`SENSOR_REFRESH_INTERVAL_SECONDS`）；
- 仅可访问已授权家庭下的设备，禁止跨家庭；
- 响应时间目标：实时查询 < 3 秒，日报 < 10 秒，周报 < 30 秒。
