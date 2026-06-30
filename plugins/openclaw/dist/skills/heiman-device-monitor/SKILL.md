---
name: heiman-device-monitor
description: 设备智能监控 —— 从传感器数据中识别设备异常、安全隐患和运维需求，主动向主人推荐处理任务。两条路径：cron 触发的【扫描监控】(路径 A) 与用户回应触发的【回应处理】(路径 B)。防骚扰由 heiman_habit_suggest 工具裁定。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
      tools:
        - heiman_habit_suggest
---

# heiman-device-monitor

从家庭传感器数据中识别设备异常、安全隐患和运维需求，主动推荐处理任务。

## 何时激活

| 路径 | 触发来源 | 说明 |
| ---- | -------- | ---- |
| **路径 A** | cron 定时任务（每 6 小时/每日） | 扫描全屋设备状态，识别异常模式 |
| **路径 B** | 用户回应推荐 | 用户对推荐进行确认、延迟或拒绝 |

## 核心工作流

### 路径 A：扫描监控

1. **数据收集**：
   - 调 `heiman-cli device list` 获取所有设备及其最新状态
   - 调 `heiman-cli sensor history --hours 24` 获取最近 24 小时传感器数据
   - 调 `heiman-cli alert history --hours 72` 获取近期告警记录
   - 调 `heiman-cli task list --status pending` 获取未完成的任务（避免重复推荐）

2. **异常模式识别**：

| 监控类别 | 识别信号 | 示例 | 紧急程度 |
| -------- | -------- | ---- | -------- |
| **设备离线** | 设备状态 `offline` 超过 2 小时 | 厨房烟雾报警器离线 | ⚠️ 高 |
| **低电量** | 电池电量 < 20% | 门磁传感器电量仅剩 12% | ⚠️ 中 |
| **持续告警** | 同一设备触发告警超过 3 次/24h | 烟雾报警器频繁误报 | 🔥 紧急 |
| **环境异常** | 温湿度超出舒适范围超过 6 小时 | 客厅温度持续 > 32°C | ⚠️ 中 |
| **设备防拆** | `TamperState == 1` | 卧室烟雾报警器被拆下 | 🔥 紧急 |
| **数据异常** | 传感器长时间无数据上报 | 水浸传感器 12 小时无心跳 | ⚠️ 高 |
| **安全阈值** | CO 浓度持续高于 30ppm | 厨房 CO 浓度连续 1 小时 > 30ppm | 🔥 紧急 |
| **设备老化** | 设备使用超过 5 年（根据注册时间） | 智能网关已服役 5 年 | ℹ️ 低 |

3. **影响评估**：
   - 每个异常需要评估对家庭安全的影响范围
   - 关联分析：门磁开启 + 温湿度骤降 → 推断开窗通风（正常行为，不告警）
   - 门磁关闭 + 水浸报警 → 推断管道漏水（紧急告警）

4. **推荐生成**：
   - 按紧急程度排序，生成 1-3 条推荐
   - 每条推荐包含：设备名称、异常描述、影响评估、建议操作
   - 调用 `heiman_habit_suggest` 工具进行防骚扰裁定
   - 紧急事件（🔥）**立即推送**，不受防骚扰限制

### 路径 B：回应处理

1. **解析回应**：
   - 确认处理 → 调用 `heiman-create-task` skill 创建维护任务
   - 忽略警告 → 记录忽略原因，短期内不再重复提醒同类型异常
   - 询问详情 → 提供更详细的设备状态数据

2. **任务创建**：
   - **设备维护任务**：如"更换客厅烟雾报警器电池"
   - **安全检查任务**：如"检查厨房 CO 报警器是否故障"
   - **环境调节任务**：如"开启客厅空调降温"
   - 调用 `heiman-cli task create` 创建任务

## 防骚扰规则

- 同一设备同一异常类型，24 小时内只推荐一次
- 用户"忽略"后，7 天内不再提醒该设备同类异常
- 紧急事件（🔥）始终推送，直到状态恢复
- 每天推荐总数不超过 5 条

## 示例

### 推荐示例 1：低电量警告

> "🔋 阳台门磁传感器（door_balcony）电量仅剩 12%，建议尽快更换电池，以免影响安防监控。是否创建'更换门磁电池'任务？"

用户确认后：
```bash
heiman-cli task create --task-id replace_door_battery --description "更换阳台门磁传感器电池" --priority high --due "+2d"
```

### 推荐示例 2：环境异常

> "🌡️ 书房温湿度传感器（th_study）监测到室温持续 6 小时超过 32°C，可能影响设备运行和人体舒适度。建议远程开启空调或检查窗帘遮挡。是否创建'远程控温'任务？"

用户确认后：
```bash
heiman-cli task create --task-id study_cooling --description "书房远程降温（开启空调/调节窗帘）" --priority medium --due "+1h"
heiman-cli rule create --task-id study_cooling \
  --name "[study_cooling] 书房高温自动降温" \
  --mode event \
  --condition "书房温度 > 30°C 持续 1 小时" \
  --action-desc "自动开启书房空调至 26°C"
```

### 推荐示例 3：紧急告警

> "🚨 **紧急告警**：厨房 CO 报警器（co_kitchen）检测到一氧化碳浓度持续超过 30ppm，超过 1 小时未恢复。请立即检查厨房燃气设备，并开窗通风。已自动创建紧急任务。"

```bash
heiman-cli task create --task-id co_emergency_kitchen --description "紧急：厨房 CO 浓度超标，请立即检查" --priority urgent --due "+15m"
```

## 数据结构参考

### 设备状态数据结构

```json
{
  "device_id": "1942869486798540800",
  "device_name": "020001ac",
  "device_type": "smoke_detector",
  "room": "门口",
  "state": "online",
  "properties": {
    "SmokeSensorState": 0,
    "BatteryPercentage": 45,
    "TamperState": 0
  },
  "last_report": "2026-06-24T08:30:00Z",
  "alert_count_24h": 0,
  "registered_at": "2025-11-26T00:00:00Z"
}
```

### 异常事件数据结构

```json
{
  "alert_id": "ld0tv5oBBq5cCyKFeGVS",
  "device_id": "1942869486798540800",
  "title": "测试报警",
  "contents": "2025-11-26 16:00:19 测试报警\n【门口-烟雾报警器-My Home】",
  "level": 5,
  "create_time": 1764144019537,
  "resolved": false
}
```

### 推荐输出格式

```json
{
  "recommendations": [
    {
      "id": "rec_20260624_001",
      "device_id": "1942869486798540800",
      "category": "low_battery",
      "severity": "medium",
      "title": "门磁传感器电量低",
      "description": "阳台门磁传感器电量仅剩 12%，建议更换电池",
      "suggested_task": {
        "name": "更换阳台门磁电池",
        "priority": "high",
        "due_offset": "+2d"
      }
    }
  ]
}
```

## 边界

- ✅ 自动扫描设备状态，识别异常模式
- ✅ 支持紧急事件优先推送
- ✅ 防骚扰机制避免过度提醒
- ❌ 不直接控制设备（开关、调节等）→ 走 `heiman-devices`
- ⚠️ 紧急事件自动创建任务，无需用户确认
