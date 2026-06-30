---
name: heiman-perception-digest
description: heiman-perception-digest 定时任务的内部步骤，仅由该任务调用。负责汇总和分析感知数据，生成每日感知摘要。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-perception-digest

感知数据摘要生成。

## 何时激活

仅由 heiman-perception-digest 定时任务调用，不对外暴露。

## 核心工作流

### 步骤 1 · 数据收集

收集当日感知数据：

```bash
# 获取当日事件
heiman-cli perception events --today

# 获取当日活动记录
heiman-cli perception activity --today

# 获取当日传感器数据
heiman-cli sensor history --today

# 获取当日设备状态变化
heiman-cli device history --today
```

### 步骤 2 · 数据汇总

汇总分析数据：

| 汇总项 | 汇总内容 |
| ------ | -------- |
| **人员活动** | 家庭成员在家时间、活动类型、活动频率 |
| **设备使用** | 设备开关次数、运行时长、能耗统计 |
| **环境变化** | 温湿度变化趋势、空气质量变化 |
| **安全事件** | 异常事件次数、类型、处理情况 |
| **自动化触发** | 自动化任务触发次数、成功率 |

### 步骤 3 · 生成摘要

生成每日感知摘要：

```json
{
  "digest_date": "2026-06-24",
  "summary": {
    "people": {
      "total_presence": "8小时",
      "activities": ["看电视", "工作", "用餐"],
      "most_active_room": "客厅"
    },
    "devices": {
      "total_switches": 15,
      "most_used": "客厅灯",
      "energy_usage": "5度"
    },
    "environment": {
      "avg_temperature": 25.5,
      "avg_humidity": 60,
      "air_quality": "良好"
    },
    "security": {
      "events": 0,
      "status": "正常"
    },
    "automation": {
      "triggers": 8,
      "success_rate": 100
    }
  },
  "highlights": [
    "爸爸今天在家工作了4小时",
    "空调运行了6小时，消耗3度电",
    "全天无安全异常"
  ]
}
```

### 步骤 4 · 推送摘要

通过 heiman-notify 将摘要推送给用户。

## 摘要内容

| 部分 | 内容 | 频率 |
| ---- | ---- | ---- |
| **人员活动** | 家庭成员活动情况 | 每日 |
| **设备使用** | 设备使用统计 | 每日 |
| **环境变化** | 环境数据统计 | 每日 |
| **安全事件** | 安全事件汇总 | 每日 |
| **自动化触发** | 自动化执行统计 | 每日 |

## 边界

- ✅ 仅由定时任务调用
- ✅ 生成每日感知摘要
- ✅ 通过 heiman-notify 推送
- ❌ 不直接响应用户查询