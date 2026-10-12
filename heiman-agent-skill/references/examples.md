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

## 安全边界示例

| 用户请求 | 处理 |
|----------|------|
| 「帮我把所有设备关了」 | 批量设备操作（>3 台），需二次确认 |
| 「删掉这些历史数据」 | 拒绝执行删除类操作前先确认，套用确认话术 |
| 「把设备 ID 发我」 | 拒绝，输出须脱敏（不暴露完整 did/userId/地址） |
