---
name: heiman-home-observe
description: home-dreaming 定时任务的 Observe 步骤，仅由该任务调用。负责观察家庭状态和事件，收集数据供后续步骤使用。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-home-observe

home-dreaming 定时任务的观察步骤。

## 何时激活

仅由 home-dreaming 定时任务调用，不对外暴露。

## 核心工作流

### 步骤 1 · 数据收集

```bash
# 获取家庭档案
heiman-cli profile list

# 获取设备状态
heiman-cli device list

# 获取传感器数据
heiman-cli sensor history --hours 24

# 获取事件记录
heiman-cli perception events --hours 24

# 获取任务状态
heiman-cli task list
```

### 步骤 2 · 状态分析

分析收集到的数据：

| 分析项 | 分析内容 |
| ------ | -------- |
| **人员状态** | 谁在家、在哪个房间、活动类型 |
| **设备状态** | 哪些设备在线、哪些离线、运行状态 |
| **环境状态** | 温湿度、空气质量、光照等 |
| **事件趋势** | 近期发生的事件、频率、类型 |
| **任务执行** | 任务完成情况、触发频率、成功率 |

### 步骤 3 · 数据输出

输出观察结果供后续步骤使用：

```json
{
  "observation_time": "2026-06-24T10:00:00Z",
  "people": [
    {"name": "爸爸", "location": "客厅", "activity": "看电视"}
  ],
  "devices": [
    {"did": "light_001", "status": "online", "power": "on"}
  ],
  "environment": {
    "temperature": 25.5,
    "humidity": 60
  },
  "events": [],
  "tasks": []
}
```

## 观察指标

| 指标 | 描述 |
| ---- | ---- |
| **occupancy** | 人员在位情况 |
| **device_status** | 设备在线状态 |
| **environmental_conditions** | 环境条件 |
| **event_frequency** | 事件发生频率 |
| **task_completion** | 任务完成率 |

## 边界

- ✅ 仅由 home-dreaming 定时任务调用
- ✅ 收集家庭状态数据
- ❌ 不直接响应用户查询