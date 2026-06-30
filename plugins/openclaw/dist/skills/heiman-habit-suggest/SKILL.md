---
name: heiman-habit-suggest
description: 每日习惯洞察 —— 从家庭档案识别值得建成任务的习惯，主动 IM 推荐给主人；主人认可后据此建任务。两条路径：cron 触发的【扫描推荐】(路径 A) 与用户回应触发的【回应处理】(路径 B)。防骚扰由 heiman_habit_suggest 工具裁定。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
      tools:
        - heiman_habit_suggest
        - heiman_notify
---

# heiman-habit-suggest

识别值得建成任务的家庭习惯，主动推荐给主人。

## 何时激活

| 路径 | 触发来源 | 说明 |
| ---- | -------- | ---- |
| **路径 A** | cron 定时任务 | 每日扫描家庭档案和设备数据，生成推荐 |
| **路径 B** | 用户回应推荐 | 用户对推荐进行确认或拒绝 |

## 核心工作流

### 路径 A：扫描推荐

1. **数据收集**：
   - 调 `heiman-cli profile list` 获取家庭档案
   - 调 `heiman-cli sensor history` 获取近期传感器数据
   - 调 `heiman-cli task list` 获取已有任务列表（避免重复推荐）

2. **习惯识别**：

| 习惯类型 | 识别信号 | 示例 |
| -------- | -------- | ---- |
| **规律性行为** | 连续 7 天以上同一时间段出现的行为 | 每天早上 7 点起床、晚上 11 点睡觉 |
| **健康相关** | 涉及用药、饮水、运动等健康行为 | 每天吃降压药、每天喝水不足 8 杯 |
| **安全隐患** | 设备状态异常或环境条件超出安全范围 | 门窗未关、燃气泄漏风险、温度异常 |
| **节能机会** | 设备长时间运行但无人使用 | 空调开着但房间无人、灯光白天长亮 |

3. **推荐生成**：
   - 每个推荐包含：习惯描述、推荐理由、建议任务类型
   - 调用 `heiman_habit_suggest` 工具进行防骚扰裁定
   - 符合条件的推荐通过 IM 发送给主人

### 路径 B：回应处理

1. **解析回应**：
   - 确认推荐 → 调用 `heiman-create-task` skill 创建任务
   - 拒绝推荐 → 记录拒绝原因，短期内不再推荐相同内容
   - 修改推荐 → 根据用户反馈调整后重新推荐

2. **任务创建**：
   - 根据推荐类型自动装配任务参数
   - 调用 `heiman-cli task create` 创建任务

## 防骚扰规则

- 每天最多推荐 3 条
- 同一习惯拒绝后 7 天内不再推荐
- 用户明确表示"不要推荐"后停止推荐

## 示例

### 推荐示例

> "发现您每天晚上 11 点后仍在使用手机，建议设置'睡前 30 分钟提醒'任务，帮助改善睡眠习惯。是否创建？"

### 任务创建示例

用户确认后，自动创建任务：

```bash
heiman-cli task create --task-id bedtime_phone_remind --description "睡前30分钟手机使用提醒"
heiman-cli rule create --task-id bedtime_phone_remind \
  --name "[bedtime_phone_remind] 睡前手机提醒" \
  --mode event \
  --condition "用户手持手机，时间在晚上11点后" \
  --action-desc "使用手机推送通知：该休息了，放下手机吧"
```