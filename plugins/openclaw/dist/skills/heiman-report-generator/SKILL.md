---
name: heiman-report-generator
description: 家庭状态报表生成 —— 从烟雾、CO、温湿度、门磁、水浸等传感器数据中自动生成每日/每周家庭状态报表，提供安全评分、趋势分析和行动建议。两条路径：cron 触发的【定时报表】(路径 A) 与用户指令触发的【按需报表】(路径 B)。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-report-generator

从家庭传感器数据中自动生成每日/每周家庭状态报表，提供安全评分、趋势分析和行动建议。

## 何时激活

| 路径 | 触发来源 | 说明 |
| ---- | -------- | ---- |
| **路径 A** | cron 定时任务（每日 22:00 / 每周日 21:00） | 自动生成日报/周报并推送给主人 |
| **路径 B** | 用户指令 | 用户主动请求"生成今日报表"或"查看本周家庭状态" |

## 核心工作流

### 路径 A：定时报表

1. **数据收集**：

| 数据来源 | API 调用 | 时间范围 |
| -------- | -------- | -------- |
| 家庭设备列表 | `heiman-cli device list` | 当前 |
| 设备实时状态 | `heiman-cli device status --device-id {id}` | 当前 |
| 设备属性历史 | `heiman-cli sensor history --hours {24/168}` | 日报 24h / 周报 168h |
| 告警记录 | `heiman-cli alert history --hours {24/168}` | 日报 24h / 周报 168h |
| 设备在线率 | `heiman-cli device online-rate --hours {24/168}` | 日报 24h / 周报 168h |

2. **数据分析维度**：

#### 2.1 安全防护分析

| 指标 | 数据来源 | 日报展示 | 周报展示 |
| ---- | -------- | -------- | -------- |
| 烟雾报警触发次数 | `SmokeSensorState` 事件 | 今日触发次数 | 本周触发趋势 |
| CO 报警触发次数 | `coValue` 超阈值事件 | 今日触发次数 | 本周触发趋势 |
| 水浸报警触发次数 | `WaterSensorState` 事件 | 今日触发次数 | 本周触发趋势 |
| 门磁异常开启 | `ContactState == 1` 在夜间(22-6点) | 今日异常次数 | 本周异常趋势 |
| 设备防拆告警 | `TamperState == 1` | 今日触发设备 | 本周触发设备列表 |

#### 2.2 环境舒适度分析

| 指标 | 数据来源 | 日报展示 | 周报展示 |
| ---- | -------- | -------- | -------- |
| 平均温度 | `CurrentTemperature` 聚合 | 今日均值/极值 | 本周日变化趋势 |
| 平均湿度 | `CurrentHumidity` 聚合 | 今日均值/极值 | 本周日变化趋势 |
| 温度舒适时长 | 18-26°C 范围内时长 | 今日占比 | 本周各天对比 |
| 湿度舒适时长 | 40-70% 范围内时长 | 今日占比 | 本周各天对比 |
| 夜间温度波动 | 22-6点温度变化幅度 | 今日波动值 | 本周夜间趋势 |

#### 2.3 设备健康度分析

| 指标 | 数据来源 | 日报展示 | 周报展示 |
| ---- | -------- | -------- | -------- |
| 设备在线率 | 设备 `state` 字段 | 今日在线率 | 本周在线率趋势 |
| 低电量设备 | `BatteryPercentage < 20%` | 今日列表 | 本周变化 |
| 离线设备 | 状态为 `offline` | 今日列表 | 本周离线统计 |
| 设备无心跳 | 超 2 小时未上报 | 今日列表 | 本周统计 |

#### 2.4 联动关联分析

- **门磁 + 温湿度**：门磁开启且温湿度骤降 → "开窗通风"行为识别（正常行为不告警）
- **门磁 + 水浸**：门磁关闭且水浸报警 → "管道漏水"推断
- **CO + 门窗**：CO 浓度上升且门窗关闭 → "潜在燃烧不充分风险"

3. **安全评分计算**：

| 评分项 | 扣分规则 | 满分 |
| ------ | -------- | ---- |
| 烟雾/CO/水浸报警 | 每次触发扣 20 分，上不封顶 | 40 |
| 设备离线率 | 低于 90% 每 1% 扣 2 分 | 20 |
| 低电量设备 | 每台扣 3 分 | 15 |
| 夜间门磁异常 | 每次扣 10 分 | 15 |
| 设备防拆告警 | 每台扣 10 分 | 10 |
| **基础分** | | **100** |

> 评分等级：≥90 优秀 | ≥75 良好 | ≥60 一般 | <60 关注

4. **报表生成**：
   - 调用 LLM 生成自然语言总结
   - 按模板组装 JSON 结构
   - 通过 IM 推送给主人

### 路径 B：按需报表

当用户发送以下指令时触发：
- "生成今日家庭报表"
- "看看这周家里怎么样"
- "最近三天家庭状态"

**处理流程**：
1. 解析用户指令中的时间范围
2. 按照路径 A 相同逻辑收集数据
3. 生成相应时间范围的报表
4. 通过 IM 实时返回给用户

## 报表输出模板

### 日报模板

```json
{
  "report_type": "daily",
  "report_date": "2026-06-24",
  "generated_at": "2026-06-24T22:00:00Z",
  "home_name": "My Home",
  "executive_summary": "今日家庭整体状态良好，未检测到安全报警，环境舒适度正常。",
  
  "security_summary": {
    "score": 92,
    "grade": "优秀",
    "alerts_today": 0,
    "critical_events": [],
    "risk_factors": []
  },
  
  "environment_summary": {
    "avg_temperature": 24.5,
    "avg_humidity": 58,
    "temperature_range": "22.1 ~ 26.8",
    "comfort_hours": 22,
    "night_fluctuation": 2.3,
    "insight": "今日体感舒适，夜间温度适宜睡眠。"
  },
  
  "device_health": {
    "total_devices": 8,
    "online_devices": 7,
    "offline_devices": [
      { "name": "厨房水浸传感器", "offline_since": "2026-06-24 18:30" }
    ],
    "low_battery_devices": [
      { "name": "阳台门磁", "battery": 12 }
    ]
  },
  
  "highlights": [
    { "type": "good", "content": "今日无安全报警，继续保持。" },
    { "type": "warning", "content": "阳台门磁电量偏低(12%)，建议本周内更换。" },
    { "type": "info", "content": "今日开窗通风次数: 3 次，平均时长 25 分钟。" }
  ],
  
  "action_suggestions": [
    "建议检查厨房水浸传感器，今日 18:30 起处于离线状态。",
    "阳台门磁电池低于 20%，建议 2 天内更换。"
  ]
}
```

### 周报模板

```json
{
  "report_type": "weekly",
  "report_week": "2026-06-18 ~ 2026-06-24",
  "generated_at": "2026-06-24T21:00:00Z",
  "home_name": "My Home",
  
  "executive_summary": "本周家庭整体状态良好，环境舒适度持续稳定，安全事件零发生。",
  
  "weekly_metrics": {
    "security_score_avg": 94,
    "total_alerts": 1,
    "alert_trend": "↓ 较上周下降 50%",
    "device_online_rate": 96.5,
    "avg_temperature": 24.2,
    "avg_humidity": 56
  },
  
  "security_summary": {
    "score": 94,
    "grade": "优秀",
    "alerts_this_week": [
      { "device": "烟雾报警器-门口", "time": "2026-06-20 16:00", "type": "测试报警", "resolved": true }
    ],
    "night_door_events": 0,
    "tamper_events": 0
  },
  
  "environment_trend": {
    "temperature_trend": "稳定",
    "humidity_trend": "略有下降",
    "comfort_analysis": "本周 92% 时间处于舒适区间",
    "insight": "本周温湿度持续稳定，空气质量良好，适合居家办公。"
  },
  
  "device_health": {
    "online_rate": 96.5,
    "weekly_offline_events": [
      { "device": "厨房水浸传感器", "count": 2, "total_duration": "3.5h" }
    ],
    "battery_status": {
      "good": 7,
      "warning": 1,
      "critical": 0
    }
  },
  
  "weekly_highlights": [
    { "day": "周一", "event": "温度偏高(28°C)，空调运行 6 小时" },
    { "day": "周三", "event": "阳台门磁低电量预警" },
    { "day": "周五", "event": "烟雾报警器测试（正常自检）" }
  ],
  
  "action_suggestions": [
    "立即更换阳台门磁电池（当前 12%）。",
    "检查厨房水浸传感器信号稳定性，本周离线 2 次。",
    "下周气温升高，建议提前设置空调定时策略。"
  ]
}
```

## 数据查询参考

### 传感器属性映射

| 设备类型 | productId 示例 | 关键属性 | 事件 |
| -------- | -------------- | -------- | ---- |
| 烟雾报警器 | 1901600411274600448 | `SmokeSensorState`, `BatteryPercentage`, `TamperState` | `SmokeAlarm`, `TestAlarm` |
| 一氧化碳报警器 | 1901598716138250240 | `coValue`, `CONC`, `BatteryPercentage` | `COAlarm` |
| 温湿度传感器 | (待补充) | `CurrentTemperature`, `CurrentHumidity` | - |
| 门磁传感器 | (待补充) | `ContactState`, `TamperState` | `DoorOpen` |
| 水浸传感器 | (待补充) | `WaterSensorState`, `BatteryPercentage` | `WaterLeak` |
| 智能网关 | 1901601085789986816 | 设备在线状态 | - |

### 时间聚合查询

```bash
# 日报：最近 24 小时属性历史
heiman-cli sensor history --device-id {id} --hours 24 --aggregate avg

# 周报：最近 7 天按天聚合
heiman-cli sensor history --device-id {id} --days 7 --aggregate daily

# 告警统计
heiman-cli alert history --hours 168 --device-type smoke --format count
```

## 示例

### 用户触发示例

**用户输入**：
> "生成今日家庭报表"

**Agent 处理**：
1. 识别为路径 B（按需报表）
2. 调用 `heiman-cli device list` 获取设备列表
3. 遍历设备调用 `heiman-cli sensor history --hours 24`
4. 调用 `heiman-cli alert history --hours 24`
5. 计算安全评分
6. 组装日报 JSON
7. 返回格式化报表

**输出示例**：
```
📊 【My Home】2026-06-24 家庭日报

🟢 安全评分：92/100（优秀）
  ✅ 今日无安全报警
  ⚠️ 1 台设备需关注

🌡️ 环境状态：
  平均温度 24.5°C（22.1~26.8），舒适时长 22h
  平均湿度 58%，正常范围

🔋 设备健康：
  在线率 87.5%（7/8 在线）
  ⚠️ 厨房水浸传感器 18:30 起离线
  ⚠️ 阳台门磁电量 12%

📋 建议行动：
  1. 检查厨房水浸传感器是否故障
  2. 2 天内更换阳台门磁电池

---
回复"确认"创建维护任务 | "忽略"不再提醒
```

## 边界

- ✅ 支持日报和周报自动生成
- ✅ 支持用户按需请求报表
- ✅ 提供安全评分和趋势分析
- ❌ 不直接控制设备（开关、调节等）→ 走 `heiman-devices`
- ⚠️ 报表生成需确保数据隐私安全
