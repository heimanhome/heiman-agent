---
name: heiman-events
description: 查询和管理海曼传感器事件，包括告警确认、事件过滤和历史记录查询。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-events

处理海曼传感器事件管理，通过 `heiman-cli` 查询、确认和过滤事件。

## 何时激活

| 意图 | 用户说了类似… |
|------|-------------|
| **list** | "查看事件" "最近有什么告警" |
| **acknowledge** | "确认告警" "处理这个报警" |
| **filter** | "严重告警" "未确认的事件" |

## 核心工作流

### 步骤 1 · 确定操作类型

根据用户表述确定操作类型：
- 查看事件列表 → `event list`
- 确认事件 → `event acknowledge <event_id>`
- 过滤事件 → `event list --level <level>`

### 步骤 2 · 执行操作

| 命令 | 用途 |
|------|------|
| `heiman-cli event list` | 获取所有事件 |
| `heiman-cli event list --level <level>` | 按级别过滤事件 |
| `heiman-cli event acknowledge <event_id>` | 确认事件 |

### 步骤 3 · 回复

- 列出事件：按时间倒序显示，包含级别、消息和状态
- 确认事件：返回确认结果
- 过滤结果：只显示符合条件的事件

## 事件级别

| 级别 | 说明 |
|------|------|
| CRITICAL | 严重告警（如烟雾报警、一氧化碳超标） |
| HIGH | 高级告警（如水浸检测、温度异常） |
| MEDIUM | 中等告警（如设备离线） |
| LOW | 低级告警（如电量不足） |

## 异常处理

| 异常 | 处理 | 回复 |
|------|------|------|
| 事件不存在 | 返回错误 | "未找到该事件" |
| 确认失败 | 重试一次 | "确认失败，请重试" |

## 示例

| 用户说 | 命令 |
|--------|------|
| "查看最近的告警" | `heiman-cli event list` |
| "确认这个报警" | `heiman-cli event acknowledge event_001` |
| "严重告警有哪些" | `heiman-cli event list --level CRITICAL` |
