---
title: ML 模型管理
category: features
order: 10
tags: [ml, ai, model, training]
---

# ML 机器学习模型管理

黑曼智能家居内置 6 个机器学习模型，覆盖异常检测、行为识别、舒适度评估、决策建议等核心场景。

## 模型列表

| 模型名称 | 算法 | 类型 | 输入特征数 | 说明 |
| -------- | ---- | ---- | ---------- | ---- |
| `anomaly_detector_if` | IsolationForest | 无监督 | 8 | 基于隔离森林的异常检测，识别数据中的离群点 |
| `anomaly_detector_clf` | RandomForestClassifier | 分类 | 8 | 异常类型分类器，区分环境/电量/行为等异常类型 |
| `comfort_evaluator` | RandomForestRegressor | 回归 | 6 | 舒适度评分 0-100 分，综合评估温度/湿度/空气质量 |
| `behavior_recognizer` | RandomForestClassifier | 分类 | 12 | 11 类行为识别（睡眠/烹饪/离家/工作/娱乐等） |
| `decision_engine` | - | 规则+模型 | - | 综合分析与自动化决策建议引擎 |
| `rule_generator` | - | 规则+模板 | - | 基于历史数据自动生成智能规则 |

## API 端点

### 模型概览

```http
GET /api/ai/ml/models
```

返回所有模型的状态、版本、准确率等摘要信息。

### 模型详情

```http
GET /api/ai/ml/models/{model_name}
```

返回指定模型的完整信息，包括特征名称、训练参数、历史版本。

### 训练模型

```http
POST /api/ai/ml/models/{model_name}/train
Content-Type: application/json

{
  "model_type": "anomaly_detector_if"
}
```

支持别名：`anomaly_detector_if` / `anomaly_detector_clf` 可替代为 `anomaly_detector`。

### 批量训练

```http
POST /api/ai/ml/models/train-all
Content-Type: application/json

{}
```

### 提交反馈

```http
POST /api/ai/ml/models/{model_name}/feedback
Content-Type: application/json

{
  "sensor_data": { "temperature": 26.5, "humidity": 65.0 },
  "actual_label": "correct",
  "comment": "检测正确"
}
```

反馈累积到阈值后会触发在线学习自动重训练。

### 重训练检查

```http
POST /api/ai/ml/models/check-retrain
Content-Type: application/json

{
  "model_name": "anomaly_detector_if"
}
```

### 健康检查

```http
GET /api/ai/ml/health
```

## 输入特征

### 异常检测模型（8 个特征）

- `temperature` - 温度 (°C)
- `humidity` - 湿度 (%)
- `co_level` - CO 浓度 (ppm)
- `smoke_level` - 烟雾浓度
- `battery_level` - 电量 (%)
- `hour` - 当前小时数 (0-23)
- `is_night` - 是否夜间
- `activity_level` - 活动等级

### 舒适度模型（6 个特征）

- `temperature` / `humidity` / `air_quality` / `noise_level` / `light_level` / `hour`

### 行为识别模型（12 个特征）

- `temperature` / `humidity` / `hour` / `is_night` / `activity_level`
- `kitchen_activity` / `bedroom_activity` / `livingroom_activity`
- `last_behavior` / `hour_sin` / `hour_cos` / `day_of_week`

## 安全回退机制

关键传感器（烟雾、天然气、CO）始终使用**规则引擎作为安全回退**，确保：
- 模型未训练时，规则引擎接管
- ML 判断异常但规则未触发时，发出低优先级告警
- 规则触发时，无论 ML 判断如何，优先采纳规则判定

## 反馈闭环

```
传感器数据 → ML 模型预测 → 用户反馈
                                  ↓
            自动重训练 ← 累积 50 条 ← 反馈收集
                ↓
          新旧模型对比 → 改进 > 1% → 自动部署
```

## 相关模块

- [A/B 测试](./ab-testing.md) - 对比 ML 模型和规则模型
- [在线学习](./online-learning.md) - 模型持续进化
- [模型可解释性](./model-explainability.md) - 理解模型决策
