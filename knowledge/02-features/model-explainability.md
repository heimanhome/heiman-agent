---
title: 模型可解释性
category: features
order: 13
tags: [ml, explainability, feature-importance, shap, xai]
---

# ML 模型可解释性

模型可解释性工具帮助理解 AI 决策背后的原因，提升系统透明度和用户信任。

## 可解释性方法概览

| 方法 | 类型 | 适用模型 | 计算成本 | 精度 |
| ---- | ---- | -------- | -------- | ---- |
| 内置特征重要性 | 全局 | 树模型 | 低 | 中（有偏） |
| 排列重要性 | 全局 | 所有模型 | 中（多次推理） | 高 |
| 扰动法 | 局部 | 所有模型 | 中 | 中（近似 SHAP） |
| Jaccard 相似度 | 排名对比 | 所有模型 | 低 | N/A |

## API 端点

### 特征重要性排名

```http
GET /api/ai/ml/feature-importance/{model_name}
```

支持模型：`anomaly_detector_if`、`anomaly_detector_clf`、`comfort_evaluator`、`behavior_recognizer`

返回内置重要性 + 排列重要性双排名，以及 Jaccard 相似度对比。

### 整体模型解释

```http
GET /api/ai/ml/explain/{model_name}
```

返回模型结构信息、所有特征的重要性排名、样本预测示例。

### 单次预测解释

```http
POST /api/ai/ml/explain/prediction
Content-Type: application/json

{
  "model_name": "anomaly_detector_clf",
  "features": {
    "temperature": 26.5,
    "humidity": 65.0,
    "co_level": 5.0,
    "smoke_level": 2.0
  }
}
```

## 特征重要性计算方式

### 1. 内置特征重要性（Gini Importance）

树模型通过 `feature_importances_` 属性直接获取每个特征的基尼重要性。

```python
importances = model.feature_importances_
for name, imp in zip(feature_names, importances):
    print(f"{name}: {imp:.4f}")
```

**局限**：对高基数特征有偏，不适合作为唯一参考。

### 2. 排列重要性（Permutation Importance）

随机打乱单个特征值后测量准确率下降幅度：

```python
# 伪代码
for feature in features:
    accuracy_before = evaluate(model, X, y)
    X_shuffled = shuffle_feature(X, feature)
    accuracy_after = evaluate(model, X_shuffled, y)
    importance = accuracy_before - accuracy_after
```

排列重要性越大，说明该特征对模型越重要。

### 3. 扰动法（Perturbation Analysis）

逐步扰动特征值，观测预测结果变化：

```
base_prediction = model.predict(features)       # 基线预测
for feature in features:
    perturbed = perturb(features, feature, ±10%)  # 扰动该特征
    new_prediction = model.predict(perturbed)
    contribution = |new_prediction - base_prediction|  # 贡献度
```

这种方法**模型无关**，适用于任何模型。

## 结果解读

### 特征贡献方向

| direction | 含义 |
| --------- | ---- |
| `increased` | 该特征使预测值升高（如"更异常"） |
| `decreased` | 该特征使预测值降低（如"更正常"） |
| `neutral` | 该特征对本次预测影响极小 |

### 排名一致性

Jaccard 相似度衡量内置重要性与排列重要性排名的重叠程度：

$$J(A, B) = \frac{|A \cap B|}{|A \cup B|}$$

- ≥ 0.7：两种方法排名高度一致，结果可信
- 0.4-0.7：存在一定差异，建议以排列重要性为准
- < 0.4：排名严重不一致，可能存在特征共线或高基数问题

## 使用场景

| 场景 | 推荐方法 |
| ---- | -------- |
| 模型调优（哪些特征可删） | 排列重要性 |
| 理解模型逻辑 | 全局分析（内置+排列双排名） |
| 解释单次判断 | 预测解释（扰动法） |
| 模型审核/合规 | 排列重要性 + 预测解释 |

## 限制与边界

- 非树模型（如逻辑回归、SVM）不支持内置重要性，仅支持排列重要性
- 扰动法近似 SHAP，非精确 SHAP 值
- 排列重要性需要多次推理，大特征空间时较慢
- 共线特征（如 `hour` 和 `is_night`）可能导致重要性分裂

## 相关模块

- [ML 模型管理](./ml-model-management.md) - 训练和管理模型
- [A/B 测试](./ab-testing.md) - 对比测评模型效果
- [在线学习](./online-learning.md) - 反馈驱动的持续学习
