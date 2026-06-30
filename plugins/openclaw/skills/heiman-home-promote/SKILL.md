---
name: heiman-home-promote
description: home-dreaming 定时任务的 Promote 步骤，仅由该任务调用。负责根据观察结果提出改进建议和优化方案。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-home-promote

家庭优化建议生成。

## 何时激活

仅由 home-dreaming 定时任务调用，不对外暴露。

## 核心工作流

### 步骤 1 · 接收观察数据

接收 heiman-home-observe 的输出数据：

```json
{
  "observation_time": "...",
  "people": [...],
  "devices": [...],
  "environment": {...},
  "events": [...],
  "tasks": [...]
}
```

### 步骤 2 · 分析优化机会

分析观察数据，识别优化机会：

| 分析维度 | 优化方向 | 示例 |
| -------- | -------- | ---- |
| **节能** | 设备使用优化 | 空调温度过高、灯光长亮 |
| **安全** | 安全隐患排除 | 门窗未关、燃气泄漏风险 |
| **健康** | 健康习惯建议 | 久坐提醒、饮水提醒 |
| **舒适** | 环境优化 | 温湿度调节、空气质量改善 |
| **效率** | 自动化优化 | 任务优化、场景联动 |

### 步骤 3 · 生成建议

生成优化建议：

```json
{
  "promote_time": "2026-06-24T10:00:00Z",
  "suggestions": [
    {
      "type": "energy_saving",
      "title": "空调温度优化",
      "description": "客厅空调设定温度为 26 度，建议调整为 27 度，预计节能 10%",
      "priority": "medium",
      "action": "调空调温度到 27 度"
    },
    {
      "type": "health",
      "title": "久坐提醒",
      "description": "爸爸已连续工作 2 小时，建议起身活动",
      "priority": "high",
      "action": "发送久坐提醒"
    }
  ]
}
```

### 步骤 4 · 提交建议

通过 heiman-notify 将建议推送给用户。

## 建议类型

| 类型 | 描述 | 优先级 |
| ---- | ---- | ------ |
| **energy_saving** | 节能建议 | 低/中 |
| **security** | 安全建议 | 高 |
| **health** | 健康建议 | 中/高 |
| **comfort** | 舒适建议 | 低/中 |
| **efficiency** | 效率建议 | 低/中 |

## 优先级规则

| 优先级 | 条件 |
| ------ | ---- |
| **high** | 涉及安全、健康紧急问题 |
| **medium** | 涉及日常优化、效率提升 |
| **low** | 涉及舒适改善、个性化建议 |

## 边界

- ✅ 仅由 home-dreaming 定时任务调用
- ✅ 生成优化建议
- ✅ 通过 heiman-notify 推送
- ❌ 不直接响应用户查询