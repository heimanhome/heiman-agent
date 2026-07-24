---
name: heiman-ml-ab
description: ML 模型 A/B 测试框架：启动对照实验、查看实验状态、统计分析结果、提升优胜模型。对比 ML 模型与规则模型的实际表现。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-07-23"
  openclaw:
    requires:
      bins: ["curl"]
---

# heiman-ml-ab

ML 模型 A/B 测试框架，用于对比 ML 模型与规则模型的实际表现，提供统计显著性检验和自动推荐。

## 何时激活

| 意图 | 用户说了类似… |
| ---- | ------------- |
| **start_ab** | "开始A/B测试" "对比ML和规则模型" "启动对照实验" "做实验" |
| **ab_status** | "A/B测试进展" "实验状态" "测试怎么样了" "看看实验结果" |
| **analyze_ab** | "分析实验结果" "统计验证" "ML效果好不好" "实验结论" |
| **promote_ab** | "上线ML模型" "切换成ML" "用ML替代规则" "推广优胜模型" |

## 核心工作流

### 启动 A/B 实验

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/ab/start \
  -H "Content-Type: application/json" \
  -d '{
    "experiment_name": "{name}",
    "model_name": "{model_name}",
    "ml_ratio": 0.5,
    "min_sample_size": 100,
    "significance_level": 0.05,
    "duration_hours": 24
  }'
```

**参数说明：**
- `experiment_name` - 实验名称（唯一标识）
- `model_name` - 被测模型名称
- `ml_ratio` - ML 变体流量占比（0.0-1.0，默认 0.5）
- `min_sample_size` - 最小样本量（默认 100）
- `significance_level` - 显著性水平（默认 0.05）
- `duration_hours` - 实验时长（小时）

### 查看实验状态

```bash
curl -s http://localhost:1912/api/ai/ml/ab/status
```

### 分析实验结果

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/ab/analyze \
  -H "Content-Type: application/json" \
  -d '{"experiment_name": "{experiment_name}"}'
```

### 提升 ML 变体

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/ab/promote \
  -H "Content-Type: application/json" \
  -d '{"experiment_name": "{experiment_name}"}'
```

## 工作流决策树

```
启动实验 → 收集样本 → 样本充足？
                         ├─ 否 → 继续收集
                         └─ 是 → 统计分析
                                   ├─ ML 显著优 → promote ML
                                   ├─ 规则显著优 → rollback ML
                                   └─ 无显著差异 → 继续测试
```

## 输出格式

### 实验状态

```json
{
  "success": true,
  "data": {
    "experiments": [
      {
        "name": "anomaly-ab-001",
        "model_name": "anomaly_detector_if",
        "status": "running",
        "ml_ratio": 0.5,
        "samples_collected": 85,
        "min_sample_size": 100,
        "started_at": "2026-07-23T08:00:00Z"
      }
    ]
  }
}
```

### 分析结果

```json
{
  "success": true,
  "data": {
    "experiment_name": "anomaly-ab-001",
    "ml_accuracy": 0.94,
    "rule_accuracy": 0.88,
    "improvement": 0.06,
    "p_value": 0.012,
    "significant": true,
    "confidence": 0.95,
    "recommendation": "promote_ml",
    "sample_count": 150
  }
}
```

### 提升结果

```json
{
  "success": true,
  "data": {
    "experiment_name": "anomaly-ab-001",
    "result": "promoted",
    "ml_ratio": 1.0,
    "message": "ML variant promoted to 100% traffic"
  }
}
```

## 实验统计方法

| 指标 | 说明 |
| ---- | ---- |
| **z-test** | 双样本比例检验，验证 ML 和规则模型的准确率差异是否显著 |
| **p-value** | 小于显著性水平则拒绝零假设（两模型无差异） |
| **improvement** | ML 准确率 - 规则准确率 |
| **recommendation** | `promote_ml` / `rollback_ml` / `continue_testing` |

## 异常处理

| 异常 | 处理 |
| ---- | ---- |
| 实验名重复 | 提示已存在同名实验，建议修改名称或先结束旧实验 |
| 样本量不足 | 显示当前进度和预计完成时间，等待更多数据 |
| 模型未训练 | 提示先训练模型再启动A/B实验 |
| 分析时无数据 | 检查实验是否正常运行，确认数据表 `ab_results` 有记录 |
| 提升失败 | 检查模型文件是否存在，版本是否有效 |

## 边界

- ✅ 启动/查看/分析/提升 A/B 实验
- ✅ 自动统计显著性检验
- ❌ 不支持同时运行多个相同模型的实验
- ⚠️ 实验期间不要手动切换模型版本
- ⚠️ 关键传感器（smoke/gas/co）始终使用规则检测兜底，不参与 A/B 分流

## 示例

用户："帮我测试一下异常检测ML模型，跟规则对比看看谁更好"

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/ab/start \
  -H "Content-Type: application/json" \
  -d '{
    "experiment_name": "anomaly-detector-v1-test",
    "model_name": "anomaly_detector_if",
    "ml_ratio": 0.5,
    "min_sample_size": 100,
    "significance_level": 0.05,
    "duration_hours": 24
  }'
```

用户："昨天那个实验有结果了吗？分析一下"

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/ab/analyze \
  -H "Content-Type: application/json" \
  -d '{"experiment_name": "anomaly-detector-v1-test"}'
```

如果结果显示 ML 显著优于规则（p < 0.05），询问用户是否要推广：

```bash
curl -s -X POST http://localhost:1912/api/ai/ml/ab/promote \
  -H "Content-Type: application/json" \
  -d '{"experiment_name": "anomaly-detector-v1-test"}'
```
