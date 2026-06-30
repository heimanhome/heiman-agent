---
name: heiman-terminate-task
description: 任务终止 —— 用户主动取消或任务到期时触发，调 `heiman-cli task delete --reason X` 一笔走完 backend（写 task_terminate_log + 删 rule + 删 task，FK CASCADE 清 task_link 与 task_record）。然后再根据实际情况清理关联的 cron job。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-terminate-task

任务终止与清理。

## 何时激活

| 意图 | 用户说了类似… |
| ---- | ------------- |
| **cancel** | "取消任务" "删除任务" "终止任务" |
| **expire** | 任务到期自动触发 |
| **manual** | "停止执行" "不再执行" "结束任务" |

## 核心工作流

### 步骤 1 · 确认终止

确认用户的终止意图：

> "确定要终止该任务吗？终止后无法恢复。"

### 步骤 2 · 执行终止

```bash
# 终止任务（用户主动取消）
heiman-cli task delete --task-id <id> --reason user_cancel

# 终止任务（任务到期）
heiman-cli task delete --task-id <id> --reason expired

# 终止任务（其他原因）
heiman-cli task delete --task-id <id> --reason <reason>
```

| 原因 | 说明 |
| ---- | ---- |
| **user_cancel** | 用户主动取消 |
| **expired** | 任务到期 |
| **completed** | 任务完成 |
| **failed** | 任务执行失败 |
| **abandoned** | 任务放弃 |

### 步骤 3 · 清理关联

backend 会自动清理：
- task_terminate_log（记录终止日志）
- rule（规则）
- task（任务）
- task_link（任务关联）
- task_record（任务记录）

同时需要手动清理：
- 关联的 cron job（通过 OpenClaw cron tool）

```bash
# 获取任务关联的 cron job
heiman-cli task links --task-id <id>

# 删除关联的 cron job
# 通过 OpenClaw cron tool 删除
```

## 终止原因

| 原因 | 触发条件 |
| ---- | -------- |
| **user_cancel** | 用户明确表示取消 |
| **expired** | 任务生命周期结束 |
| **completed** | 任务目标达成 |
| **failed** | 任务多次执行失败 |
| **abandoned** | 用户长时间未响应 |

## 异常处理

| 异常 | 处理 | 回复 |
| ---- | ---- | ---- |
| 任务不存在 | 提示用户 | "任务不存在" |
| 任务已终止 | 提示用户 | "任务已终止" |
| 删除失败 | 重试一次 | "删除失败，正在重试..." |

## 边界

- ✅ 支持手动终止和自动终止
- ✅ 自动清理关联数据
- ❌ 终止后无法恢复
- ⚠️ 需二次确认

## 示例

### 终止任务

用户："取消喝水任务"

```bash
heiman-cli task delete --task-id drink_8_daily --reason user_cancel
```

### 任务到期自动终止

```bash
heiman-cli task delete --task-id med_tomorrow_9am --reason expired
```