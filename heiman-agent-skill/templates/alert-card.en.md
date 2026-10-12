# Alert Card Template

For a single critical / warning alert. Keep the whole card within 10 lines.

> Fill rule: replace the `{{...}}` placeholders with the alert-card fields defined in
> `references/report-formats.md` section 3. For list fields such as `suggested_actions`,
> repeat the line and number the items manually as `1. 2. 3.` — do not keep any `{{#each}}` syntax.

## critical

```
{{emoji}} {{title}}
Device: {{device}}
Reading: {{value}}
Time: {{timestamp}}

Act now:
1. {{suggested_action}}
```

Example:

```
🚨 Smoke alarm
Device: Smoke alarm - Kitchen
Reading: alarm
Time: 2026-09-10T11:12:00+08:00

Act now:
1. Confirm everyone in the household is safe
2. Check the kitchen for open flames or heavy smoke
3. Open windows and doors to ventilate; call the fire service if needed
```

## warning

```
⚠️ {{title}}
Device: {{device}}
Reading: {{value}}
Time: {{timestamp}}

Suggested action: {{suggestion}}
```

Example:

```
⚠️ Device offline
Device: Heat alarm - HM-5HW-T
Reading: offline for 3 h 20 min
Time: 2026-09-10T11:12:00+08:00

Suggested action: Check the battery and the gateway connection; re-pair the device if needed
```

## info

```
ℹ️ {{title}}
Device: {{device}}
Reading: {{value}}

{{suggestion}}
```

## Level values

| level | Triggered by | Requires immediate user action |
|-------|--------------|--------------------------------|
| `critical` | `smokeState == 1`; `gasState == 1` (CO/gas alarm); `value >= 400` ppm (CO level); `waterState == 1` | Yes |
| `warning` | `smokeState/waterState == 2`; `tamperState == 1`; battery < 20%; offline ≥ 60 min | No, summarize |
| `info` | Normal status, comfort notes | No |

> Keep cloud-provided device names and room names in their original wording — do not rename them.
> If a name is in Chinese (e.g. 温湿度, 客厅), keep it and append an English gloss on first mention:
> `Device: 温湿度 (Temp-Humidity sensor) - 客厅 (Living room)`.
