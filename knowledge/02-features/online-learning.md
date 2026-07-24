---
title: 在线持续学习
category: features
order: 12
tags: [ml, online-learning, feedback, auto-retrain]
---

# ML 在线持续学习

黑曼支持反馈驱动的在线持续学习，模型通过用户反馈自动迭代优化，越用越准。

## 学习流程

```
用户反馈 → 反馈累积 → 触发阈值检查 → 重训练 → 性能对比 → 自动部署
```

## 反馈格式

用户通过前端 UI 或 API 提交反馈：

```json
{
  "sensor_data": {
    "temperature": 26.5,
    "humidity": 65.0,
    "co_level": 5.0,
    "smoke_level": 2.0
  },
  "actual_label": "normal",
  "comment": "当前正常，没有异常"
}
```

反馈类型：
- `normal` / `correct` - 预测正确
- `incorrect` / `wrong` - 预测错误
- 异常类型标签（如 `environment_anomaly`、`battery_anomaly` 等）

## API 端点

### 在线学习状态

```http
GET /api/ai/ml/online/status
```

返回各模型的反馈累积数量、重训练阈值、是否需要重训练。

### 触发重训练

```http
POST /api/ai/ml/online/retrain
Content-Type: application/json

{}

# 或指定模型
POST /api/ai/ml/online/retrain?model_name=comfort_evaluator
Content-Type: application/json

{}
```

## 自动重训练策略

| 条件 | 动作 |
| ---- | ---- |
| 反馈数 < 阈值 | 继续收集，不触发 |
| 反馈数 ≥ 阈值 | 触发重训练检查 |
| 新模型准确率提升 < 1% | 保留但标记"待观察" |
| 新模型准确率提升 ≥ 1% | 自动部署替换旧模型 |
| 新模型准确率反而下降 | 丢弃新模型，保留旧模型 |

## 重训练阈值

| 模型 | 默认阈值 | 说明 |
| ---- | -------- | ---- |
| `anomaly_detector_if` | 50 | 异常检测需要较多样本 |
| `anomaly_detector_clf` | 50 | 分类任务需要平衡各类别 |
| `comfort_evaluator` | 50 | 回归任务 |
| `behavior_recognizer` | 50 | 行为类别多，需要更多样本 |

## 数据存储

- 反馈数据存储在 `data/ml_feedback/` 目录
- 历史模型版本保存在 `data/models/backups/`
- 保留最近 5 个版本用于回退

## 模型版本管理

```
data/models/
├── anomaly_detector_if_v4.joblib     # 当前版本
├── backups/
│   ├── anomaly_detector_if_v1.joblib
│   ├── anomaly_detector_if_v2.joblib
│   └── anomaly_detector_if_v3.joblib
└── metrics/
    └── anomaly_detector_if.json      # 各版本指标记录
```

## 注意事项

- 重训练过程会占用 CPU 资源，可能短暂影响服务响应
- 关键传感器（smoke/gas/co）的规则检测不参与在线学习
- 反馈数据不会自动过期，如需清理请手动处理 `data/ml_feedback/`

## 相关模块

- [ML 模型管理](./ml-model-management.md) - 手动训练和管理
- [A/B 测试](./ab-testing.md) - 对比测评模型效果
- [模型可解释性](./model-explainability.md) - 理解模型决策
