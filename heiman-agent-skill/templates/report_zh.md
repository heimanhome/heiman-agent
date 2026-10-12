# 🏠 家庭安全与环境报告

> 报告类型：{{report_type}} ｜ 家庭：{{home_name}} ｜ 生成时间：{{generated_time}}
> 数据范围：{{start}} ~ {{end}} ｜ 数据覆盖率：{{data_coverage}}%

## 一句话总结

{{executive_summary}}

## 安全指数

**{{safety_score}} / 100**

| 扣分项 | 分值 |
|--------|------|
| 告警扣分 | {{alarm_penalty}} |
| 在线率扣分 | {{online_penalty}} |
| 低电量扣分 | {{battery_penalty}} |

### 🚨 紧急事件

| 设备 | 读数 | 时间 | 建议动作 |
|------|------|------|----------|
| {{device}} | {{value}} | {{timestamp}} | {{action}} |

### ⚠️ 警告项

| 设备 | 类型 | 值 |
|------|------|----|
| {{device}} | {{type}} | {{value}} |

## 设备概览

| 设备 | 类型 | 房间 | 状态 | 关键读数 | 电量 |
|------|------|------|------|----------|------|
| {{device_name}} | {{device_type}} | {{room}} | {{status_text}} | {{reading}} | {{battery}} |

- 设备总数：{{device_count_total}}
- 在线：{{device_count_online}} ｜ 离线：{{device_count_offline}}
- 离线设备：{{offline_devices}}

## 环境舒适度

| 指标 | 当前值 | 舒适区间 | 判定 |
|------|--------|----------|------|
| 温度 | {{temperature}} °C | 18–26 °C | {{temp_verdict}} |
| 湿度 | {{humidity}} % | 40–60 % | {{humidity_verdict}} |

## 趋势

- 温度：{{temperature_change}}
- 湿度：{{humidity_change}}

## 行动建议

1. {{action_suggestion}}

---

*设备 ID 已脱敏。数据来源：heiman-agent 本地服务。*

<!-- 填充规则见 references/report-formats.md 第 6 节：占位符按字段填入，表格多行则重复该行，无数据写「无」。 -->
