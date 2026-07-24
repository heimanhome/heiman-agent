---
name: heiman-ml-explain
description: ML 模型可解释性分析：特征重要性排名、预测决策解释、排列重要性计算。帮助理解模型为什么做出某个判断，提升 AI 透明度。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-07-23"
  openclaw:
    requires:
      bins: ["curl"]
---

# heiman-ml-explain

ML 模型可解释性分析工具，揭示模型决策背后的原因，让 AI 判断透明可解释。

## 何时激活

| 意图 | 用户说了类似… |
| ---- | ------------- |
| **feature_importance** | "哪些特征最重要" "特征重要性" "模型关注什么" "影响因素排名" |
| **explain_model** | "解释一下模型" "模型怎么判断的" "模型为什么这样" |
| **explain_prediction** | "为什么判定异常" "这个预测的依据" "解释这次推断" "决策理由" |

## 核心工作流

### 查看特征重要性

```bash
curl -s http://localhost:1912/api/ai/ml/feature-importance/{model_name}
```

支持的模型名称：`anomaly_detector_if`、`anomaly_detector_clf`、`comfort_evaluator`、`behavior_recognizer`

### 解释整体模型

```bash
curl -s http://localhost:1912/api/ai/ml/explain/{model_name}
```

### 解释单次预测

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/explain/prediction \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "{model_name}",
    "features": {
      "temperature": 26.5,
      "humidity": 65.0,
      "co_level": 5.0,
      "smoke_level": 2.0
    }
  }'
```

## 可解释性方法

| 方法 | 说明 | 适用模型 |
| ---- | ---- | -------- |
| **内置特征重要性** | 模型自带的 `feature_importances_` 属性（基尼重要性） | 所有树模型 |
| **排列重要性** | 随机打乱单个特征后测量准确度下降幅度 | 所有模型 |
| **扰动法** | 逐步扰动每个特征值，观测预测结果变化（近似 SHAP） | 单次预测解释 |
| **排名一致性** | 用 Jaccard 相似度对比内置重要性与排列重要性排名 | 全模型解释 |

## 输出格式

### 特征重要性排名

```json
{
  "success": true,
  "data": {
    "model_name": "anomaly_detector_if",
    "feature_importance": [
      { "feature": "co_level", "importance": 0.35, "rank": 1 },
      { "feature": "smoke_level", "importance": 0.28, "rank": 2 },
      { "feature": "temperature", "importance": 0.18, "rank": 3 },
      { "feature": "humidity", "importance": 0.12, "rank": 4 },
      { "feature": "battery_level", "importance": 0.07, "rank": 5 }
    ],
    "permutation_importance": [
      { "feature": "co_level", "importance_drop": 0.15, "rank": 1 },
      { "feature": "smoke_level", "importance_drop": 0.12, "rank": 2 },
      { "feature": "temperature", "importance_drop": 0.05, "rank": 3 }
    ],
    "ranking_similarity": 0.85
  }
}
```

### 预测解释

```json
{
  "success": true,
  "data": {
    "model_name": "anomaly_detector_clf",
    "prediction": "combination_anomaly",
    "confidence": 0.87,
    "feature_contributions": [
      { "feature": "co_level", "contribution": 0.42, "direction": "increased" },
      { "feature": "smoke_level", "contribution": 0.30, "direction": "increased" },
      { "feature": "temperature", "contribution": 0.15, "direction": "increased" }
    ],
    "base_value": 0.05,
    "explanation": "判定为联合异常的主要原因是 CO 浓度(贡献+0.42)和烟雾浓度(贡献+0.30)同时升高"
  }
}
```

### 整体模型解释

```json
{
  "success": true,
  "data": {
    "model_name": "anomaly_detector_if",
    "model_type": "IsolationForest",
    "n_estimators": 100,
    "feature_count": 8,
    "feature_importance": [...],
    "sample_prediction": {
      "prediction": "normal",
      "confidence": 0.95
    }
  }
}
```

## 异常处理

| 异常 | 处理 |
| ---- | ---- |
| 模型不支持特征重要性 | 说明该模型类型（如规则引擎）不支持重要性分析，建议查看决策规则 |
| 预测输入特征不匹配 | 列出期望的特征名称和当前输入的特征，帮助用户修正 |
| 模型未训练 | 提示先训练模型再进行分析 |

## 边界

- ✅ 树模型（RandomForest/IsolationForest）完整支持内置重要性
- ✅ 所有模型支持排列重要性（通用方法）
- ✅ 预测解释支持任意模型（模型无关的扰动法）
- ❌ URL/OneHotEncoded 等非结构化特征解释有限
- ⚠️ 排列重要性需要多次推理，大数据集时较慢
- ⚠️ 扰动法近似 SHAP，非精确 SHAP 值

## 示例

用户："异常检测模型最看重哪些传感器数据？"

```bash
curl -s http://localhost:1912/api/ai/ml/feature-importance/anomaly_detector_if
```

根据返回结果解读：CO 浓度最重要（35%），其次是烟雾浓度（28%），温度和湿度影响较小。

用户："为什么说现在家里有异常？解释一下判断依据"

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/explain/prediction \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "anomaly_detector_clf",
    "features": {
      "temperature": 28.0,
      "humidity": 70.0,
      "co_level": 120.0,
      "smoke_level": 15.0,
      "battery_level": 80.0,
      "hour": 14,
      "is_night": false
    }
  }'
```

用户："整体分析一下行为识别模型" 

```bash
curl -s http://localhost:1912/api/ai/ml/explain/behavior_recognizer
```
