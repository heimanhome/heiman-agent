# 使用示例 — 海曼智能家居管家

本文件提供 heiman-agent 技能的典型使用示例。所有命令中 `<SKILL>` 指技能根目录。

## 示例 1：查看设备总览

**用户**：看下家里的传感器状态

**执行**：

```bash
python "<SKILL>/scripts/heiman_snapshot.py"
```

**要点**：直接使用返回的 `device_count`（在线/离线分类）、`sensors[]`（关键读数）汇总回复，不重算阈值。

## 示例 2：查询单个房间温湿度

**用户**：客厅温湿度多少？

**执行**：同上取快照，在 `sensors[]` 中按 `name` 匹配目标设备，返回 `readings` 中的温度/湿度，并引用 `comfort` 的舒适度判定。

## 示例 3：检查家里有无异常

**用户**：家里有什么异常吗？

**执行**：取快照，按 `alerts` → `critical_count` → `warning_count` → 各传感器 `issues` 的顺序判读：

- 有告警：按严重级别排序输出，紧急告警套用 `templates/alert-card.md`
- 无告警：明确回复「✅ 一切正常」并给出安全评分

**注意**：门磁类设备的 `status=alarm` 可能是枚举值误读，须核对 `readings["备注"]` 纠偏提示。

## 示例 4：生成今日家庭安全日报

**用户**：生成今天的家庭安全报告

**执行**：

```bash
python "<SKILL>/scripts/heiman_snapshot.py" --hours 24
```

按 `references/report-formats.md` 组织，正文套用 `templates/report_zh.md`（英文用户套用 `templates/report_en.md`），落盘为 Markdown 文件并展示。

## 示例 5：分析一周温度趋势

**用户**：这周温度有什么变化？

**执行**：

```bash
python "<SKILL>/scripts/heiman_snapshot.py" --hours 168
```

使用返回的 `history` 数据做趋势描述；历史为空时如实说明，不臆造数据。

## 示例 6：查询自动化规则

**用户**：现在有哪些自动化规则？

**执行**：

```bash
python "<SKILL>/scripts/heiman_ctl.py" api GET /api/rules
```

## 示例 7：服务维护

**用户**：服务还活着吗？/ 重启一下服务

```bash
python "<SKILL>/scripts/heiman_ctl.py" status     # 探活
python "<SKILL>/scripts/heiman_ctl.py" restart    # 重启
python "<SKILL>/scripts/heiman_ctl.py" doctor     # 故障诊断
python "<SKILL>/scripts/heiman_ctl.py" logs -n 120  # 查看日志
```

## 示例 8：设备列表为空（换账号 / 多家庭场景）

**用户**：怎么一个设备都看不到了？换了个账号登录。

**现象**：接口返回 `success: true` 且 `data: []`（HTTP 200，**不报错**）。

**执行**：

```bash
python "<SKILL>/scripts/heiman_ctl.py" api GET /api/homes
python "<SKILL>/scripts/heiman_ctl.py" api GET "/api/devices?home_id=<目标家庭ID>"
```

**要点**：多家庭账号下后端固定取 `homes[0]`，可能命中没有设备的家庭。先核对 `/api/homes` 的 `home_id`，
再显式传 `home_id` 取数。**不要**把这种现象当成"设备全部离线"去报故障——那会让安全指数虚报扣 10 分。
切换账号后的瞬时空列表，等 5–10 秒重试即可恢复。详见 `troubleshooting.md` 第 6 条。

## 示例 9：读取源码/文档出现乱码

**用户**：这个 `.py` 文件打开是一堆乱码，开头还有 `%TSD-Header-###%`。

**执行**：

```bash
git show HEAD:README.md
git show HEAD:backend/heiman/src/heiman/main.py
```

**要点**：这是企业 DLP 透明加密（亿赛通等）造成的，只影响**读取**，Python 解释器与 IDE 在白名单内可透明解密，
服务本身照常运行。需要读源码时改走 git 对象（未被加密），或整体导出明文副本：

```bash
git archive HEAD | tar -x -C /tmp/heiman-src
```

> 注意：同一份技能包在不同位置可能一份明文、一份密文。做版本对比或打包时，先确认副本头部不是 `%TSD-Header-###%`。

## 示例 10：首次使用 / 本机没有源码

**用户**：帮我装一下 heiman-agent

**执行**：

```bash
python "<SKILL>/scripts/heiman_ctl.py" install
```

**要点**：

- 不要问用户「源码在哪 / git 地址是什么」。`install` 会先扫描本机常见位置，
  找不到再按配置与规则探测 git 地址并克隆到 `~/.heiman/src/heiman-agent`，然后装依赖。
- 想确认它到底用了哪个源，看输出的 `source.origin` / `source.url_display`，
  或跑 `python "<SKILL>/scripts/heiman_ctl.py" source show`。
- 典型的几个动作：`origin=local-clone` 表示复用了本机已有副本（不联网）；
  `origin=skill-default` 表示用了脚本内置的仓库地址（`heiman_ctl.py` 的 `DEFAULTS`）；
  `origin=user-config` 表示用了 `source set` 写入的用户配置。
- 自动链路全失败时才需要人工介入：`source set <url>`、`HEIMAN_GIT_URL` 环境变量、
  `--source <url>`，或（可选）放一份 `config/install-sources.json`。

**安装后**：`start` 启动服务，然后用 AskUserQuestion 让用户选绑定方式（A 网页自助 / B 代填凭据），
两条路径最后都需一次 OAuth 授权。

**示例：用户选了「B. 我给你账号密码，你帮我填」**

```
用户：账号是 zhangsan@example.com，密码 abc123

Agent 动作（不回显明文）：
python scripts/heiman_ctl.py env set --email "zhangsan@example.com" --password "abc123"
# -> changed: HEIMAN_EMAIL: y*********@example.com -> z*******@example.com
#             HEIMAN_PASSWORD: ****** （已写入，后端当前不使用密码）
#             已删除 HEIMAN_APP_ID=your_app_id（占位符，改回内置默认值 11）
python scripts/heiman_ctl.py restart
python scripts/heiman_ctl.py env auth-url
# -> authorize_url: https://spfile.heiman.cn/applogin/sso.html?client_id=...&state=...

Agent 回复：凭据已写入本机 .env（输出已脱敏）。还差最后一步——请把这个链接粘到浏览器
打开并用你的海曼账号登录：https://spfile.heiman.cn/applogin/sso.html?...
登录完成回调后取数就通了。
```

**示例：用户选了「A. 我自己在网页上登录」**

```
Agent 回复：打开 http://127.0.0.1:1912，页面会弹出登录对话框（没弹就点左侧边栏底部的
账号区域），点登录跳到海曼官方页，用你的账号登录即可。密码只经过海曼官网，我不会接触，
也不用改任何配置文件。
```

> 选 A 时**不要索要密码**；选 B 时回复与日志一律脱敏，并提醒用户这只是省去手工编辑配置，
> token 仍必须由他本人在浏览器授权一次。

## 安全边界示例

| 用户请求 | 处理 |
|----------|------|
| 「帮我把所有设备关了」 | 批量设备操作（>3 台），需二次确认 |
| 「删掉这些历史数据」 | 拒绝执行删除类操作前先确认，套用确认话术 |
| 「把设备 ID 发我」 | 拒绝，输出须脱敏（不暴露完整 did/userId/地址） |
