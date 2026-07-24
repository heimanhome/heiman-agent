---
name: heiman-ml-online
description: ML 模型在线持续学习：查看学习状态、手动触发重训练、自动增量更新。模型根据用户反馈持续进化，越用越准。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-07-23"
  openclaw:
    requires:
      bins: ["curl"]
---

# heiman-ml-online

ML 模型在线持续学习，让模型根据用户反馈自动迭代优化，持续提升准确率。

## 何时激活

| 意图 | 用户说了类似… |
| ---- | ------------- |
| **online_status** | "在线学习状态" "模型在学吗" "自动学习怎么样" "看看学习进度" |
| **trigger_retrain** | "手动重训" "重新学习" "更新模型" "触发训练" "让模型重新学" |
| **auto_retrain** | "模型能自己学吗" "自动更新" "持续学习" |

## 核心工作流

### 查看在线学习状态

```bash
curl -s http://localhost:1912/api/ai/ml/online/status
```

### 触发重训练（所有模型）

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/online/retrain \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 触发重训练（指定模型）

```bash
curl -s -X POST "http://localhost:1912/api/ai/ml/online/retrain?model_name={model_name}" \
  -H "Content-Type: application/json" \
  -d '{}'
```

支持的模型名称：`anomaly_detector_if`、`anomaly_detector_clf`、`comfort_evaluator`、`behavior_recognizer`、`decision_engine`

## 学习策略说明

| 阶段 | 说明 |
| ---- | ---- |
| **收集反馈** | 用户通过 `/api/ai/ml/models/{name}/feedback` 提交反馈，系统持续积累标注数据 |
| **触发阈值** | 当反馈累积达到阈值（默认 50 条），系统自动触发重训练检查 |
| **增量训练** | 使用 `scikit-learn` 模型的 `warm_start` 或全量重训练 |
| **性能对比** | 对比新旧模型准确率，改进超过 1% 才自动部署 |
| **自动部署** | 新模型训练完成后自动替换旧模型，无缝更新 |

## 输出格式

### 在线学习状态

```json
{
  "success": true,
  "data": {
    "models": [
      {
        "name": "anomaly_detector_if",
        "feedback_count": 45,
        "retrain_threshold": 50,
        "needs_retrain": false,
        "last_retrain": "2026-07-20T10:30:00Z",
        "current_accuracy": 0.92
      },
      {
        "name": "comfort_evaluator",
        "feedback_count": 67,
        "retrain_threshold": 50,
        "needs_retrain": true,
        "last_retrain": "2026-07-15T08:00:00Z",
        "current_accuracy": 0.85
      }
    ]
  }
}
```

### 重训练结果

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "model_name": "comfort_evaluator",
        "retrained": true,
        "old_accuracy": 0.85,
        "new_accuracy": 0.89,
        "improved": true,
        "improvement": 0.04,
        "deployed": true
      }
    ]
  }
}
```

## 异常处理

| 异常 | 处理 |
| ---- | ---- |
| 反馈数据不足 | 显示各模型的当前反馈数和阈值，建议继续收集反馈 |
| 重训练后准确率下降 | 回退到旧模型，保留新模型但标记为"待观察" |
| 模型文件写入失败 | 检查 `data/models/` 目录权限和磁盘空间 |
| 训练超时 | 提示用户减少样本量或检查数据质量 |

## 边界

- ✅ 查看在线学习状态、手动触发重训练
- ✅ 自动部署改进超过阈值的模型
- ❌ 不删除历史版本（旧模型保留作为回退）
- ⚠️ 重训练会占用 CPU 资源，可能短暂影响服务响应
- ⚠️ 自动部署仅在改进超过 1% 时触发

## 示例

用户："看看模型学习得怎么样了"

```bash
curl -s http://localhost:1912/api/ai/ml/online/status
```

用户："舒适度模型反馈够了，帮我重新训练一下"

```bash
curl -s -X POST "http://localhost:1912/api/ai/ml/online/retrain?model_name=comfort_evaluator" \
  -H "Content-Type: application/json" \
  -d '{}'
```

用户："所有需要更新的模型都重新训练一下"

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/online/retrain \
  -H "Content-Type: application/json" \
  -d '{}'
```
