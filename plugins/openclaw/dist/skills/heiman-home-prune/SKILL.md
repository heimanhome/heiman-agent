---
name: heiman-home-prune
description: home-dreaming 定时任务的 Prune 步骤，仅由该任务调用。负责清理无效数据、过期任务和冗余配置。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-home-prune

数据清理与优化。

## 何时激活

仅由 home-dreaming 定时任务调用，不对外暴露。

## 核心工作流

### 步骤 1 · 数据扫描

扫描需要清理的数据：

```bash
# 扫描过期任务
heiman-cli prune tasks --expired

# 扫描离线设备
heiman-cli prune devices --offline

# 扫描过期记录
heiman-cli prune records --old

# 扫描无效配置
heiman-cli prune config --invalid
```

### 步骤 2 · 清理执行

执行清理操作：

| 清理项 | 清理条件 | 清理方式 |
| ------ | -------- | -------- |
| **过期任务** | 任务已终止且超过 30 天 | 删除任务记录 |
| **离线设备** | 设备离线超过 7 天 | 标记为待处理 |
| **过期记录** | 记录超过 90 天 | 归档或删除 |
| **无效配置** | 配置引用不存在 | 删除配置 |

```bash
# 清理过期任务
heiman-cli prune tasks --expired --delete

# 清理过期记录
heiman-cli prune records --old --archive

# 清理无效配置
heiman-cli prune config --invalid --delete
```

### 步骤 3 · 清理报告

生成清理报告：

```json
{
  "prune_time": "2026-06-24T10:00:00Z",
  "cleaned": {
    "tasks": {"deleted": 5, "archived": 0},
    "devices": {"marked": 2, "deleted": 0},
    "records": {"deleted": 100, "archived": 50},
    "config": {"deleted": 3}
  },
  "issues": []
}
```

## 清理规则

| 项目 | 保留期限 | 处理方式 |
| ---- | -------- | -------- |
| **任务记录** | 30 天 | 删除 |
| **事件记录** | 90 天 | 归档 |
| **传感器数据** | 30 天 | 删除 |
| **离线设备** | 7 天 | 标记待处理 |
| **无效配置** | 立即 | 删除 |

## 边界

- ✅ 仅由 home-dreaming 定时任务调用
- ✅ 自动清理过期数据
- ✅ 生成清理报告
- ❌ 不直接响应用户查询