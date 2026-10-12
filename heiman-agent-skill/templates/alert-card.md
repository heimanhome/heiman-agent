# 告警卡片模板

用于单条紧急 / 警告告警的输出，控制在 10 行以内。

> 填充规则：`{{...}}` 占位符按 `references/report-formats.md` 第 3 节的告警卡片字段替换；
> 多条目（如 `suggested_actions`）重复该行并手动编号 `1. 2. 3.`，不要保留 `{{#each}}` 语法。

## critical（紧急）

```
{{emoji}} {{title}}
设备：{{device}}
读数：{{value}}
时间：{{timestamp}}

立即处理：
1. {{suggested_action}}
```

示例：

```
🚨 烟雾报警
设备：烟雾报警器-厨房
读数：报警
时间：2026-09-10T11:12:00+08:00

立即处理：
1. 立即确认家人安全
2. 检查厨房是否有明火或浓烟
3. 打开门窗通风，必要时拨打 119
```

## warning（警告）

```
⚠️ {{title}}
设备：{{device}}
读数：{{value}}
时间：{{timestamp}}

建议：{{suggestion}}
```

示例：

```
⚠️ 设备离线
设备：温感报警器-HM-5HW-T
读数：已离线 3 小时 20 分
时间：2026-09-10T11:12:00+08:00

建议：检查设备电池与网关连接，必要时重新配对
```

## info（提示）

```
ℹ️ {{title}}
设备：{{device}}
读数：{{value}}

{{suggestion}}
```

## 级别取值

| level | 触发条件 | 是否要求用户立即响应 |
|-------|----------|----------------------|
| `critical` | `smokeState == 1`；`gasState == 1`（CO/燃气报警）；`value >= 400` ppm（CO 浓度）；`waterState == 1` | 是 |
| `warning` | `smokeState/waterState == 2`；`tamperState == 1`；电量 < 20%；离线 ≥ 60 分钟 | 否，汇总提示 |
| `info` | 常规状态、舒适度提示 | 否 |
