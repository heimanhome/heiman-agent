# 报告输出格式

## 1. 完整报告（Full Report）

```json
{
  "report": {
    "meta": {
      "report_type": "daily | weekly | realtime",
      "report_id": "uuid",
      "generated_time": "ISO8601",
      "model_version": "heiman-agent-v2.0",
      "confidence_score": 0.95
    },
    "data_source": {
      "home_id": "string",
      "home_name": "string",
      "query_time_range": {"start": "ISO8601", "end": "ISO8601"},
      "device_count": {
        "total": 5,
        "online": 4,
        "offline": 1,
        "offline_devices": ["烟雾传感器-厨房"]
      },
      "data_coverage": 0.98
    },
    "executive_summary": "一句话总结家庭整体状态",
    "security": {
      "safety_score": 95,
      "score_breakdown": {
        "alarm_penalty": -10,
        "online_rate_bonus": 0,
        "battery_penalty": -5
      },
      "critical_events": [],
      "warnings": [
        {
          "type": "low_battery",
          "device": "门磁传感器-阳台",
          "level": "warning",
          "value": "12%"
        }
      ]
    },
    "sensors": [
      {
        "device_id": "脱敏ID",
        "device_name": "烟雾报警器-客厅",
        "device_type": "smoke",
        "room": "客厅",
        "status": "online",
        "state": "正常",
        "properties": {"smokeState": 0, "battery": 85},
        "insight": "本周无报警触发，设备在线正常"
      }
    ],
    "trends": {
      "temperature_change": "+2.3°C vs last week",
      "humidity_change": "-5% vs last week"
    },
    "action_suggestions": [
      "建议明日 14:00 开窗通风 30 分钟",
      "建议更换阳台门磁传感器的电池，当前电量仅剩 12%"
    ]
  }
}
```

## 2. 简报（Brief）

用于即时通讯场景，控制在 200 字以内：

```json
{
  "type": "brief",
  "emoji_summary": "🏠 家庭安全指数: 95/100",
  "highlights": [
    "✅ 今日无报警",
    "⚠️ 书房湿度偏高 (78%)",
    "🔋 阳台门磁电量低 (12%)"
  ],
  "quick_actions": ["开启除湿机", "更换电池"]
}
```

## 3. 告警卡片（Alert Card）

```json
{
  "type": "alert",
  "level": "critical | warning | info",
  "title": "🚨 烟雾报警",
  "device": "烟雾传感器-厨房",
  "value": "报警",
  "timestamp": "ISO8601",
  "action_required": true,
  "suggested_actions": ["立即确认安全", "检查厨房", "通风"]
}
```

## 4. 数据脱敏规则

```
- deviceId  → 脱敏为 device_sn_001 格式
- userId    → 不在输出中显示
- 家庭地址  → 仅显示城市级别
- 精确位置  → 使用区域描述
```

## 5. 报告类型与时间范围

| 类型 | 时间范围 | 目标生成时长 |
|------|----------|--------------|
| 日报 `daily` | 当天 00:00 至今 | < 10 秒 |
| 周报 `weekly` | 7 天前 00:00 至今 | < 30 秒 |
| 月报 `monthly` | 30 天前 00:00 至今 | < 30 秒 |
| 实时 `realtime` | 当前快照 | < 3 秒 |

## 6. 输出模板

生成 Markdown 报告时使用（**先按提问语言选模板，再填内容**）：

- `templates/report_zh.md` — 中文报告正文（日报 / 周报 / 月报 / 实时）
- `templates/report_en.md` — 英文报告正文
- `templates/alert-card.md` — 中文单条告警卡片
- `templates/alert-card.en.md` — 英文单条告警卡片

> **语言选择规则**（对应 `SKILL.md`「执行总原则」第 6 条）：
> 提问为中文 → 用 `report_zh.md` / `alert-card.md`；
> 提问为英文 → 用 `report_en.md` / `alert-card.en.md`；
> 提问为其他语言 → 以**英文模板**为基准改写固定文案，**不要退回中文模板**。
> 报告标题、表头、栏目名、结论、建议等**固定文案**必须与提问语言一致，不允许中英混杂；
> 云端返回的设备名、房间名保持原文、不翻译；**英文报告中首次出现须附英文注释**（如 `温湿度 (Temp-Humidity sensor)`、`客厅 (Living room)`），此后可用注释名指代；**表格 `Device` 列同样适用**——每个中文设备名单元格都写成 `原名 (English gloss)`，不留裸中文名单元格。

> 模板是**结构参考**，占位符由模型按本节字段手工填充，包内不提供渲染脚本。
> 占位符统一使用 `{{key}}` 形式（如 `{{report_type}}`、`{{safety_score}}`），不要写成 `{{a|b|c}}`。
> 列表类字段（如 `critical_events`）按模板示例逐条展开为 Markdown 列表，不要保留 `{{#each}}` 语法。

**占位符取值对照**（模板用扁平名，快照是嵌套结构；`heiman_snapshot.py` 实际输出为准）：

| 模板占位符 | 快照字段 |
|---|---|
| `{{report_type}}` | 由请求决定：`daily` / `weekly` / `monthly` / `realtime` |
| `{{safety_score}}` / `{{alarm_penalty}}` / `{{online_penalty}}` / `{{battery_penalty}}` | `safety_score` / `score_breakdown.alarm_penalty` / `.online_penalty` / `.battery_penalty` |
| `{{device_count_total}}` / `{{device_count_online}}` | `device_count.total` / `device_count.online` |
| `{{device_count_offline}}` | `len(device_count.offline)`——注意该字段是**离线设备名列表**，数量要自己取长度 |
| `{{offline_devices}}` | `device_count.offline`（名列表，逗号连接） |
| `{{temperature}}` / `{{humidity}}` | `comfort.temperature_avg` / `comfort.humidity_avg` |
| `{{temp_verdict}}` / `{{humidity_verdict}}` | `comfort.temperature_verdict` / `comfort.humidity_verdict` |
| `{{temperature_change}}` / `{{humidity_change}}` | **无直接字段**。快照**没有** `trends` 字段，只有 `history`（`--hours` 触发）。`history` 非空时自行对比首末样本得出变化量；`history` 为空（`{}`，常见于近期无历史采样）时按语言写「无」/「None」，并说明"仅实时对比不可用"——**不要**编造趋势数值 |
| 设备行 `{{device_name}}` / `{{device_type}}` / `{{room}}` / `{{status_text}}` / `{{reading}}` / `{{battery}}` | `sensors[]` 逐项：**英文输出用 `name_display`**（=`name` + 英文注释，直接照抄）；中文输出用 `name` / `type_label` / `room` / `status` / `readings` / `metrics.battery` |

告警卡片字段（`alert-card*.md`）见第 3 节；`alerts[]` 每项实际含 `device` / `type`（取值字段名，如 `battery`、`gasState`、`co_ppm`）/ `room` / `level` / `message`——**没有** `value` 或 `timestamp`，模板里这两列请从 `message` 中提取或留空说明。

> 本文件是给模型看的**内部中文说明**；其措辞、以及上方 JSON 示例中的中文取值**不是**输出要求，
> 实际输出语言一律跟随用户提问语言（见 `SKILL.md`「执行总原则」第 6 条）。

## 7. 空数据与异常场景

| 场景 | 输出要求 |
|------|----------|
| 无事件无告警 | 明确写"✅ 今日无报警"，不要留空 |
| 设备离线 | 标注"设备离线（已离线 X 小时）"，建议检查电源与网络 |
| 部分设备无数据 | 说明"部分设备数据暂不可用"，不影响其他设备分析 |
| 全部设备离线 | 说明数据不可用原因，并提示检查网关与云端连接 |
| 用户问的传感器离线 | 明确告知无法获取，给出 3 条排查建议 |
