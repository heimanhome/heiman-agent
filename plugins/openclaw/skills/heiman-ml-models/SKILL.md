---
name: heiman-ml-models
description: ML 模型全生命周期管理：模型列表、详情、训练、反馈、健康检查。管理异常检测、行为识别、舒适度评估、决策引擎等机器学习模型。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-07-23"
  openclaw:
    requires:
      bins: ["curl"]
---

# heiman-ml-models

ML 机器学习模型全生命周期管理，覆盖异常检测、行为识别、舒适度评估、决策引擎等模型。

## 何时激活

| 意图 | 用户说了类似… |
| ---- | ------------- |
| **list_models** | "有哪些ML模型" "模型列表" "查看模型状态" "模型管理" |
| **model_detail** | "查看异常检测模型" "舒适度模型详情" "模型信息" |
| **train_model** | "训练异常检测模型" "重新训练" "训练所有模型" "更新模型" |
| **submit_feedback** | "提交反馈" "这个检测不对" "反馈模型结果" "纠正模型" |
| **check_health** | "ML健康检查" "模型系统状态" "检查模型" |

## 核心工作流

### 列出所有模型

```bash
curl -s http://localhost:1912/api/ai/ml/models
```

### 查看模型详情

```bash
curl -s http://localhost:1912/api/ai/ml/models/{model_name}
```

支持的模型名称：`anomaly_detector_if`、`anomaly_detector_clf`、`comfort_evaluator`、`behavior_recognizer`、`decision_engine`、`rule_generator`

### 训练指定模型

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/models/{model_name}/train \
  -H "Content-Type: application/json" \
  -d '{"model_type": "{model_name}"}'
```

### 训练所有模型

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/models/train-all \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 提交反馈

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/models/{model_name}/feedback \
  -H "Content-Type: application/json" \
  -d '{"sensor_data": {...}, "actual_label": "correct_or_incorrect", "comment": "..."}'
```

### 检查重训练需求

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/models/check-retrain \
  -H "Content-Type: application/json" \
  -d '{"model_name": "{model_name}"}'
```

### ML 健康检查

```bash
curl -s http://localhost:1912/api/ai/ml/health
```

## 模型说明

| 模型名称 | 类型 | 说明 |
| -------- | ---- | ---- |
| `anomaly_detector_if` | IsolationForest | 无监督异常检测（离群点识别） |
| `anomaly_detector_clf` | RandomForestClassifier | 异常类型分类（环境/电量/行为等） |
| `comfort_evaluator` | RandomForestRegressor | 舒适度评分（0-100分） |
| `behavior_recognizer` | RandomForestClassifier | 11类行为识别（睡眠/烹饪/离家等） |
| `decision_engine` | - | 决策引擎（综合分析与建议生成） |
| `rule_generator` | - | 智能规则生成器 |

## 输出格式

### 模型列表

```json
{
  "success": true,
  "data": {
    "models": [
      {
        "name": "anomaly_detector_if",
        "type": "isolation_forest",
        "status": "trained",
        "accuracy": 0.92,
        "version": 3,
        "last_trained": "2026-07-20T10:30:00Z"
      }
    ],
    "total": 6
  }
}
```

### 训练结果

```json
{
  "success": true,
  "data": {
    "model_name": "anomaly_detector_if",
    "accuracy": 0.94,
    "samples_trained": 500,
    "version": 4,
    "training_time_ms": 1200
  }
}
```

### 健康状态

```json
{
  "success": true,
  "data": {
    "registry_ok": true,
    "models_available": 4,
    "feedback_pending": 12,
    "retrain_needed": ["anomaly_detector_if"]
  }
}
```

## 异常处理

| 异常 | 处理 |
| ---- | ---- |
| 模型未训练 | 提示用户先执行 `train_model`，使用 bootstrap 数据初始化训练 |
| 训练失败 | 检查数据目录权限，确认 `data/models/` 存在且可写 |
| 反馈数据不足 | 告知当前反馈数量和建议阈值（50条），继续收集反馈 |
| 模型文件丢失 | 显示"模型文件不存在，需要重新训练" |

## 边界

- ✅ 模型列表/详情/训练/反馈/健康检查
- ✅ 单个模型训练和批量训练
- ❌ 不直接修改模型参数（需代码层面修改）
- ⚠️ 训练耗时可能较长（大样本时），提示用户耐心等待
- ⚠️ 关键传感器（smoke/gas/co）始终使用规则检测作为安全回退

## 示例

用户："帮我看看有哪些AI模型，状态怎么样"

```bash
curl -s http://localhost:1912/api/ai/ml/models
```

用户："异常检测模型准确率不高，重新训练一下"

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/models/anomaly_detector_if/train \
  -H "Content-Type: application/json" \
  -d '{"model_type": "anomaly_detector_if"}'
```

用户："训练完所有模型"

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/models/train-all \
  -H "Content-Type: application/json" \
  -d '{}'
```
