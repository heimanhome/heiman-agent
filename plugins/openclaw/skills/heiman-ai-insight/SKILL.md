---
name: heiman-ai-insight
description: AI 综合智能分析：异常检测、舒适度评估、行为识别、智能建议、事件摘要、综合分析。一站式 AI 洞察，全方位理解家庭状态。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-07-23"
  openclaw:
    requires:
      bins: ["curl", "heiman-cli"]
---

# heiman-ai-insight

AI 综合智能分析，覆盖异常检测、舒适度评估、行为识别、智能建议、事件摘要等全维度洞察。

## 何时激活

| 意图 | 用户说了类似… |
| ---- | ------------- |
| **anomaly_detect** | "看看有没有异常" "异常检测" "家里安全吗" "有危险吗" |
| **comfort_check** | "家里舒服吗" "舒适度怎么样" "环境好不好" |
| **behavior_check** | "谁在家" "现在在干嘛" "有什么活动" "行为分析" |
| **smart_suggest** | "给点建议" "怎么优化" "有什么推荐" "AI建议" |
| **summary** | "总结一下" "最近怎么样" "家庭报告" "概况" |
| **comprehensive** | "全面分析" "综合分析" "整体情况" "全貌" |

## 核心工作流

### 异常检测

```bash
curl -s "http://localhost:1912/api/ai/anomaly?home_id={home_id}"
curl -s "http://localhost:1912/api/ai/anomaly/behavior?home_id={home_id}"
```

### 舒适度评估

```bash
curl -s "http://localhost:1912/api/ai/comfort?home_id={home_id}"
```

### 行为/活动识别

```bash
curl -s "http://localhost:1912/api/ai/activity?home_id={home_id}"
curl -s "http://localhost:1912/api/ai/activity/routine?home_id={home_id}"
```

### 智能建议

```bash
curl -s "http://localhost:1912/api/ai/suggest?home_id={home_id}"
```

### 事件摘要

```bash
curl -s "http://localhost:1912/api/ai/summary?home_id={home_id}"
```

### 综合分析

```bash
curl -s "http://localhost:1912/api/ai/analyze?home_id={home_id}"
```

### 用户习惯与建议

```bash
heiman-cli ai habits --user-id <user_id>
heiman-cli ai suggestions --user-id <user_id> --home-id <home_id>
```

## 输出格式

### 异常检测结果

```json
{
  "success": true,
  "data": {
    "anomalies": [
      {
        "type": "environment",
        "severity": "warning",
        "sensor": "客厅温湿度",
        "value": 32.5,
        "threshold": 30.0,
        "message": "温度偏高"
      }
    ],
    "total_anomalies": 1,
    "risk_level": "low"
  }
}
```

### 舒适度结果

```json
{
  "success": true,
  "data": {
    "score": 78,
    "level": "comfortable",
    "temperature_score": 75,
    "humidity_score": 82,
    "air_quality_score": 90,
    "suggestions": ["建议适当降温"]
  }
}
```

### 行为识别结果

```json
{
  "success": true,
  "data": {
    "current_activity": "cooking",
    "confidence": 0.88,
    "next_predicted": "eating",
    "routine_match": true
  }
}
```

## 异常处理

| 异常 | 处理 |
| ---- | ---- |
| 无传感器数据 | 提示检查传感器连接，确认数据采集正常 |
| ML 模型不可用 | 回退到规则引擎分析，告知使用规则模式 |
| 分析超时 | 建议缩小查询范围（指定 home_id、减少传感器数量） |

## 边界

- ✅ 异常检测（ML+规则双模）、舒适度、行为识别、智能建议
- ✅ 关键传感器（smoke/gas/co）始终使用规则兜底
- ❌ 不直接控制设备（走 `heiman-devices`）
- ❌ 建议类输出仅供参考，不自动执行操作
- ⚠️ ML 模型未训练时自动使用规则分析

## 示例

用户："全面看看家里的情况"

依次调用：
```bash
curl -s "http://localhost:1912/api/ai/anomaly?home_id=default"
curl -s "http://localhost:1912/api/ai/comfort?home_id=default"
curl -s "http://localhost:1912/api/ai/activity?home_id=default"
```

汇总结果：安全无异常，舒适度 78 分（舒适），当前活动：烹饪中。给出综合评估。
