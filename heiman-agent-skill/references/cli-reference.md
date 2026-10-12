# heiman-cli 命令参考

`heiman-cli` 是 heiman-agent 的官方命令行工具，安装后位于 venv 的 `Scripts/heiman-cli.exe`（Windows）或 `bin/heiman-cli`（macOS/Linux）。

统一调用方式（技能脚本已封装，无需关心路径）：

```bash
python scripts/heiman_ctl.py cli <命令...>
```

配置来源：`~/.heiman/config.json`，关键字段 `server.url`（默认 `http://127.0.0.1:1912`）、`server.token`、`debug`。
所有命令默认输出紧凑 JSON，加 `--pretty` 输出缩进格式。
退出码：`0` 成功，`1` 参数/校验错误，`2` 网络错误，`3` 业务错误。

> 子命令与参数以实际安装版本的 `python scripts/heiman_ctl.py cli <命令> --help` 输出为准；
> `heiman-cli` 由 `install` 步骤安装到 `~/.heiman/venv`，未完成 `install` 时 `cli` 子命令不可用
> （可先用 `heiman_ctl.py where` 确认 venv 路径，再检查 `Scripts/heiman-cli.exe` 是否存在）。

## 命令组

### service — 服务生命周期

```bash
python scripts/heiman_ctl.py cli service start
python scripts/heiman_ctl.py cli service status
python scripts/heiman_ctl.py cli service logs
```

子命令：`start` `stop` `restart` `status` `kill` `logs`

### health — 健康检查

```bash
python scripts/heiman_ctl.py cli health check
python scripts/heiman_ctl.py cli health status
```

### sensor — 传感器

```bash
python scripts/heiman_ctl.py cli sensor list
python scripts/heiman_ctl.py cli sensor info <did>
python scripts/heiman_ctl.py cli sensor history <did> --hours 24
```

> `sensor history --hours N` 由 CLI 内部换算成 REST 的 `start_time`（REST 端点本身**没有** `hours` 参数）。

### device — 设备

```bash
python scripts/heiman_ctl.py cli device list
python scripts/heiman_ctl.py cli device get <device_id>
python scripts/heiman_ctl.py cli device status <device_id>
python scripts/heiman_ctl.py cli device props <device_id>
python scripts/heiman_ctl.py cli device history <device_id>
python scripts/heiman_ctl.py cli device online-rate
python scripts/heiman_ctl.py cli device toggle <device_id>
python scripts/heiman_ctl.py cli device control <device_id> --action ...
python scripts/heiman_ctl.py cli device refresh
```

### event — 事件

```bash
python scripts/heiman_ctl.py cli event list
python scripts/heiman_ctl.py cli event get <event_id>
python scripts/heiman_ctl.py cli event ack <event_id>
python scripts/heiman_ctl.py cli event ack-all
python scripts/heiman_ctl.py cli event stats
python scripts/heiman_ctl.py cli event delete <event_id>
```

### rule — 规则

```bash
python scripts/heiman_ctl.py cli rule list
python scripts/heiman_ctl.py cli rule get <rule_id>
python scripts/heiman_ctl.py cli rule create --help
python scripts/heiman_ctl.py cli rule update <rule_id>
python scripts/heiman_ctl.py cli rule enable <rule_id>
python scripts/heiman_ctl.py cli rule disable <rule_id>
python scripts/heiman_ctl.py cli rule test <rule_id>
python scripts/heiman_ctl.py cli rule stats
python scripts/heiman_ctl.py cli rule delete <rule_id>
```

### home / person / task

```bash
python scripts/heiman_ctl.py cli home list
python scripts/heiman_ctl.py cli home get <home_id>

python scripts/heiman_ctl.py cli person list
python scripts/heiman_ctl.py cli person create --name "Alice" --role "mother"
python scripts/heiman_ctl.py cli person update <person_id>
python scripts/heiman_ctl.py cli person rename <person_id> --name "新名字"
python scripts/heiman_ctl.py cli person delete <person_id>

python scripts/heiman_ctl.py cli task list
python scripts/heiman_ctl.py cli task create --description "Daily 10k steps" \
  --kind progress --target 10000 --unit steps --window day
python scripts/heiman_ctl.py cli task progress <task_id> --delta 1000
python scripts/heiman_ctl.py cli task session <task_id> start
python scripts/heiman_ctl.py cli task pause <task_id>
python scripts/heiman_ctl.py cli task resume <task_id>
```

### ai — AI 分析

```bash
python scripts/heiman_ctl.py cli ai analyze
python scripts/heiman_ctl.py cli ai anomaly
python scripts/heiman_ctl.py cli ai comfort
python scripts/heiman_ctl.py cli ai activity
python scripts/heiman_ctl.py cli ai routine
python scripts/heiman_ctl.py cli ai suggest
python scripts/heiman_ctl.py cli ai summary
python scripts/heiman_ctl.py cli ai habits
python scripts/heiman_ctl.py cli ai health
python scripts/heiman_ctl.py cli ai edge-models
```

### monitor / observability

```bash
python scripts/heiman_ctl.py cli monitor status
python scripts/heiman_ctl.py cli monitor nodes
python scripts/heiman_ctl.py cli monitor resources
python scripts/heiman_ctl.py cli monitor memory
python scripts/heiman_ctl.py cli monitor rules

python scripts/heiman_ctl.py cli observability overview
python scripts/heiman_ctl.py cli observability stats
python scripts/heiman_ctl.py cli observability token-usage
python scripts/heiman_ctl.py cli observability agent-runs
```

### auth / account / admin / config / debug

```bash
python scripts/heiman_ctl.py cli auth status
python scripts/heiman_ctl.py cli auth login --help
python scripts/heiman_ctl.py cli account info
python scripts/heiman_ctl.py cli admin status
python scripts/heiman_ctl.py cli admin heiman-config
python scripts/heiman_ctl.py cli admin heiman-test
python scripts/heiman_ctl.py cli config show
python scripts/heiman_ctl.py cli config set server.url http://127.0.0.1:1912
python scripts/heiman_ctl.py cli debug ping
python scripts/heiman_ctl.py cli debug routes
```

### doctor — 一键自检

```bash
python scripts/heiman_ctl.py cli doctor
```

### alert — 告警历史

```bash
python scripts/heiman_ctl.py cli alert history
```

### home_profile — 家庭画像

```bash
python scripts/heiman_ctl.py cli home_profile entries
python scripts/heiman_ctl.py cli home_profile rendered
```

## 直接使用 REST API 的等价写法

CLI 与 REST 一一对应，遇到 CLI 未覆盖的接口时直接用 `api` 子命令：

```bash
python scripts/heiman_ctl.py api GET  /api/ai/anomaly
python scripts/heiman_ctl.py api POST /api/ai/learning/start
python scripts/heiman_ctl.py api GET  /api/observability/overview
```
