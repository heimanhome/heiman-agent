---
name: heiman-rules
description: 管理海曼传感器自动化规则，包括规则创建、启用/禁用和状态查询。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-rules

处理海曼传感器自动化规则管理，通过 `heiman-cli` 创建、查询和控制规则。

## 何时激活

| 意图 | 用户说了类似… |
|------|-------------|
| **list** | "查看规则" "有哪些自动化规则" |
| **enable** | "启用规则" "打开自动报警" |
| **disable** | "禁用规则" "关闭自动报警" |
| **create** | "创建规则" "当温度超过时通知我" |

## 核心工作流

### 步骤 1 · 确定操作类型

根据用户表述确定操作类型：
- 查看规则列表 → `rule list`
- 启用规则 → `rule enable <rule_id>`
- 禁用规则 → `rule disable <rule_id>`
- 创建规则 → `rule create`

### 步骤 2 · 执行操作

| 命令 | 用途 |
|------|------|
| `heiman-cli rule list` | 获取所有规则 |
| `heiman-cli rule enable <rule_id>` | 启用规则 |
| `heiman-cli rule disable <rule_id>` | 禁用规则 |

### 步骤 3 · 回复

- 列出规则：显示规则名称、状态和条件
- 启用/禁用：返回操作结果
- 创建规则：提示用户提供规则条件和动作

## 规则条件

| 条件类型 | 说明 | 示例 |
|----------|------|------|
| temperature | 温度条件 | 温度 > 30°C |
| humidity | 湿度条件 | 湿度 > 80% |
| smoke | 烟雾检测 | 检测到烟雾 |
| co | 一氧化碳检测 | CO > 50ppm |
| water | 水浸检测 | 检测到水浸 |

## 异常处理

| 异常 | 处理 | 回复 |
|------|------|------|
| 规则不存在 | 返回错误 | "未找到该规则" |
| 操作失败 | 重试一次 | "操作失败，请重试" |

## 示例

| 用户说 | 命令 |
|--------|------|
| "查看所有规则" | `heiman-cli rule list` |
| "启用温度报警规则" | `heiman-cli rule enable rule_001` |
| "禁用夜间报警" | `heiman-cli rule disable night_alert` |
