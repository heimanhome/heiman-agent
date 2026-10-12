# 🏠 Home Safety & Environment Report

> Report type: {{report_type}} ｜ Home: {{home_name}} ｜ Generated at: {{generated_time}}
> Data range: {{start}} ~ {{end}} ｜ Data coverage: {{data_coverage}}%

## Executive Summary

{{executive_summary}}

## Safety Score

**{{safety_score}} / 100**

| Penalty item | Score |
|--------------|-------|
| Alarm penalty | {{alarm_penalty}} |
| Offline penalty | {{online_penalty}} |
| Low battery penalty | {{battery_penalty}} |

### 🚨 Critical Events

| Device | Reading | Time | Suggested action |
|--------|---------|------|------------------|
| {{device}} | {{value}} | {{timestamp}} | {{action}} |

### ⚠️ Warnings

| Device | Type | Value |
|--------|------|-------|
| {{device}} | {{type}} | {{value}} |

## Device Overview

| Device | Type | Room | Status | Key Reading | Battery |
|--------|------|------|--------|-------------|---------|
| {{device_name}} | {{device_type}} | {{room}} | {{status_text}} | {{reading}} | {{battery}} |

- Total devices: {{device_count_total}}
- Online: {{device_count_online}} ｜ Offline: {{device_count_offline}}
- Offline devices: {{offline_devices}}

## Environment Comfort

| Metric | Current | Comfort Range | Verdict |
|--------|---------|---------------|---------|
| Temperature | {{temperature}} °C | 18–26 °C | {{temp_verdict}} |
| Humidity | {{humidity}} % | 40–60 % | {{humidity_verdict}} |

## Trends

- Temperature: {{temperature_change}}
- Humidity: {{humidity_change}}

## Action Suggestions

1. {{action_suggestion}}

---

*Device IDs are desensitized. Data source: heiman-agent local service.*

<!-- Fill rule: see references/report-formats.md section 6 — replace every placeholder with its field value, repeat the row for multiple entries, write "None" when there is no data. If a cloud device/room name is in Chinese (e.g. 温湿度, 客厅), keep the original name and append an English gloss on first occurrence, e.g. 温湿度 (Temp-Humidity sensor), 客厅 (Living room). This applies to table cells as well: every Device-column cell holding a Chinese name must carry the gloss — no bare Chinese name in a cell. -->
