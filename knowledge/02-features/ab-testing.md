---
title: A/B 测试框架
category: features
order: 11
tags: [ml, ab-testing, experiment, statistics]
---

# ML A/B 测试框架

A/B 测试框架用于科学对比 ML 模型和规则模型的实际表现，通过双样本 z-test 验证差异的统计显著性。

## 实验流程

```
1. 启动实验  →  2. 收集样本  →  3. 统计分析  →  4. 决策 Promotion
   (设置参数)     (流量分流)     (z-test)        (推广/回退/继续)
```

## 核心概念

| 概念 | 说明 |
| ---- | ---- |
| **A 组（对照组）** | 使用规则引擎处理（当前线上逻辑） |
| **B 组（实验组）** | 使用 ML 模型处理（待验证的新逻辑） |
| **流量分桶** | 按 `home_id` 哈希分流，确保同一家庭始终分到同一组 |
| **显著性水平** | 默认 0.05，p < α 则认为差异显著 |
| **最小样本量** | 默认 100，样本不足时自动延长实验 |

## API 端点

### 启动实验

```http
POST /api/ai/ml/ab/start
Content-Type: application/json

{
  "experiment_name": "anomaly-detector-v1",
  "model_name": "anomaly_detector_if",
  "ml_ratio": 0.5,
  "min_sample_size": 100,
  "significance_level": 0.05,
  "duration_hours": 24
}
```

| 参数 | 默认值 | 说明 |
| ---- | ------ | ---- |
| `experiment_name` | 必填 | 唯一实验标识 |
| `model_name` | 必填 | 被测模型名称 |
| `ml_ratio` | 0.5 | ML 流量占比（0-1） |
| `min_sample_size` | 100 | 最小样本量 |
| `significance_level` | 0.05 | 显著性水平 |
| `duration_hours` | 24 | 最大实验时长 |

### 查看状态

```http
GET /api/ai/ml/ab/status
```

### 分析结果

```http
POST /api/ai/ml/ab/analyze
Content-Type: application/json

{
  "experiment_name": "anomaly-detector-v1"
}
```

分析输出包括：
- `ml_accuracy` - ML 模型准确率
- `rule_accuracy` - 规则准确率
- `improvement` - 提升幅度
- `p_value` - 统计显著性 p 值
- `significant` - 是否显著
- `recommendation` - 建议动作

### 推广模型

```http
POST /api/ai/ml/ab/promote
Content-Type: application/json

{
  "experiment_name": "anomaly-detector-v1"
}
```

推广后 ML 模型承担 100% 流量，规则引擎转为安全回退。

## 统计方法

### z-test 双样本检验

$$z = \frac{\hat{p}_B - \hat{p}_A}{\sqrt{\hat{p}(1-\hat{p})(\frac{1}{n_A} + \frac{1}{n_B})}}$$

其中 $\hat{p}_A$ 和 $\hat{p}_B$ 分别是规则和 ML 模型的准确率。

### 决策规则

| p-value | 结论 | 建议 |
| ------- | ---- | ---- |
| p < 0.05 且 ML 更优 | ML 显著优于规则 | `promote_ml` |
| p < 0.05 且规则更优 | 规则显著优于 ML | `rollback_ml` |
| p ≥ 0.05 | 无显著差异 | `continue_testing` |

## 多实验管理

- 同一模型同一时间只能有一个运行中的实验
- 已完成实验保留在 `data/ab_experiments/` 中
- 支持实验历史查询和对比

## 安全约束

- **关键传感器（smoke/gas/co）不参与 A/B 分流**，始终由规则引擎兜底
- 实验结果不可手动修改，确保数据完整性
- 推广操作记录在审计日志中

## 最佳实践

1. **先训练再测试**：确保模型已充分训练再启动 A/B 实验
2. **足够样本量**：样本量不足时结论不可靠，建议 ≥ 100
3. **控制实验时间**：避免实验过长导致外部因素干扰
4. **一项一项测**：避免同时运行多个实验造成交叉污染

## 相关模块

- [ML 模型管理](./ml-model-management.md) - 训练和管理模型
- [在线学习](./online-learning.md) - 反馈驱动的持续学习
