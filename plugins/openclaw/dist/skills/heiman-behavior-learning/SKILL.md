---
name: heiman-behavior-learning
description: 基于历史数据学习用户习惯，预测用户行为，提供智能建议。支持获取用户习惯、预测活动、更新用户偏好。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-25"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-behavior-learning

用户行为学习与智能预测。

## 何时激活

| 意图 | 用户说了类似… |
| ---- | ------------- |
| **learn_habits** | "我的习惯是什么" "我通常几点回家" "作息规律" |
| **predict_activity** | "接下来会做什么" "我今晚几点睡" "预测一下" |
| **get_suggestions** | "有什么建议" "智能建议" "帮我安排" |
| **update_preference** | "我喜欢这样" "更新我的偏好" "记住我的习惯" |

## 核心工作流

### 获取用户习惯

```bash
heiman-cli ai habits --user-id <user_id> --pretty
```

输出示例：
```json
{
  "habits": [
    {
      "category": "wake_up",
      "average_time": "07:30",
      "confidence": 0.85,
      "weekdays": [0, 1, 2, 3, 4],
      "sample_count": 20
    }
  ],
  "preferences": {}
}
```

### 获取智能建议

```bash
heiman-cli ai suggestions --user-id <user_id> --home-id <home_id> --pretty
```

输出示例：
```json
{
  "suggestions": [
    {
      "action": "prepare_home",
      "description": "预计即将回家，准备舒适环境",
      "confidence": 0.85
    }
  ],
  "prediction": {
    "activity": "return_home",
    "confidence": 0.85,
    "expected_time": "18:30"
  },
  "habits": []
}
```

### 更新用户偏好

```bash
heiman-cli ai preference --user-id <user_id> --key <key> --value <value>
```

## 习惯类型

| 类型 | 描述 | 示例 |
| ---- | ---- | ---- |
| **wake_up** | 起床时间 | 早上7:30 |
| **sleep** | 睡觉时间 | 晚上11:00 |
| **leave_home** | 出门时间 | 早上8:30 |
| **return_home** | 回家时间 | 晚上6:30 |
| **meal** | 用餐时间 | 中午12:00 |
| **work** | 工作时间 | 早上9:00 |
| **relax** | 休闲时间 | 晚上8:00 |
| **exercise** | 运动时间 | 晚上7:00 |

## 智能建议类型

| 类型 | 描述 | 触发条件 |
| ---- | ---- | -------- |
| **prepare_home** | 准备回家环境 | 预测即将回家 |
| **prepare_bedroom** | 准备卧室 | 预测即将睡觉 |
| **secure_home** | 检查安全状态 | 预测即将出门 |
| **adjust_temperature** | 调整温度 | 环境不舒适 |
| **energy_saving** | 节能建议 | 无人时关闭设备 |

## 输出格式

### 习惯信息

```
用户习惯分析：
- 起床时间：07:30（置信度：85%）
- 睡觉时间：23:00（置信度：78%）
- 回家时间：18:30（置信度：90%）
```

### 智能建议

```
智能建议：
1. 预计您将在18:30回家，已为您准备舒适环境
2. 当前室温偏高，建议开启空调
```

## 边界

- ✅ 获取用户习惯、预测活动、智能建议
- ❌ 无法直接控制设备 → 走 `heiman-devices`
- ⚠️ 数据隐私：习惯数据本地存储，不上传云端

## 示例

用户："我通常几点回家？"

```bash
heiman-cli ai habits --user-id default --pretty
```

输出：
```json
{
  "habits": [
    {
      "category": "return_home",
      "average_time": "18:30",
      "confidence": 0.9,
      "weekdays": [0, 1, 2, 3, 4],
      "sample_count": 25
    }
  ],
  "preferences": {}
}
```

回复："根据您的习惯分析，您通常在18:30左右回家（置信度90%）。"