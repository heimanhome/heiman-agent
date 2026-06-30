---
name: heiman-create-task
description: 创建/管理"持续运转的家庭任务"—— 由 rule（条件触发自动化）/ schedule（定时提醒）/ record（行为累积统计）/ lifecycle（长期/限时）组合装配；也是 [感知引擎] 语音指令类系统消息的统一入口。覆盖：定时/累积提醒、"X 时 Y" 自动化、行为统计、持续状态阈值等。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-create-task

收到任务相关消息 → 第一步判 **op**，六条路径之一：

| op | 触发来源 | 例子 | 走哪条 |
|---|---|---|---|
| **create** | 用户消息 / `[感知引擎]` 语音指令系统消息 | "每天喝 8 杯水" / "房间有人提醒我" / "明天 X" / "没人就 Y" | 本 skill 后续段（前置检查 → 两层维度判 → 装配映射） |
| **list** | 用户消息 | "我有哪些任务" / "查看任务列表" | 直接调用 `heiman-cli task list --pretty` |
| **logs** | 用户消息 | "X 任务今天触发几次" / "看 X 触发记录" | 调用 `heiman-cli task logs <task_id>` |
| **disable / enable** | 用户消息 | "暂停喝水任务" / "启用 X 任务" | 调用 `heiman-cli task disable/enable <task_id>` |
| **update** | 用户消息 | "把喝水改成 10 杯" / "条件改成阳台有人" | 先 terminate 旧任务，再重新创建 |
| **delete** | 用户消息 | "删除喝水任务" / "把 X 任务去掉" | heiman-terminate-task |

## 输出协议

user-facing text 仅在两个时机出现：
- 终态：tool 链跑完发一段结果
- 反问：等用户答复发一句；**只问本次需要的字段，不夹带已装配信息 / 进度同步 / 任何其他内容**

其余时刻过程描述放 thinking 块，user-facing 静默。

**person 引用规则**：user-facing 文本（终态 + 反问）引用 person 时 role 优先——role 非空只写 role，不带 name 括号标注；role 为空才写 name。

### 终态必含项

内容反映本轮实际 CLI 装配参数，不增不减。格式不限，必含：

1. **任务标识**：task id + 简述
2. **触发场景**：什么时候启动
3. **响应动作**：触发后做什么 + 记录什么
4. **生命周期**：长期常驻 / 限时
5. **装配提示**：按 §装配提示元规则 逐条独立列出

以下内容仅覆盖 **create 路径**。判据走**语义判断**，不照字面词表死扣。下文给的词只作类别示例，不是穷举枚举。

## 装配后自检

工具链跑完到终态输出之间，**必须 echo 下列格式**做自检（任一 N → 修正后重过；echo 内容不输出到 user-facing）：

```
[装配后自检]
1. 含 on-target-desc 时 task → record → rule 顺序完成装配：Y / N / NA
2. 终态 §响应动作 同时含「触发后做什么」+「记录什么」：Y / N
3. 每条装配提示「怎么改」字段给出用户可直接复述的短语：Y / N
```

## 装配提示元规则

凡装配过程中 agent 自主产生的对用户的提示性信息，统称「装配提示」。覆盖：默认猜测、偏离推荐、超阈值范围、需用户验证的常识默认等。

每条装配提示**必产出**，在终态**独立成句**出现，措辞自由。

每条必含 3 要素：

- 实际取值（用户可理解措辞，不暴露内部字段）
- 一句话原因
- 怎么改 / 怎么确认

子维度判据里只标 "→ 触发装配提示"。

**多提示装配**：N 条提示 → N 句，独立成句。

## 输入硬约束

- 多个独立 task → 拆成单 task 列表，各自走分类
- AND 型规则（同一 task 内多触发必须同时成立）→ 拒建

## 前置检查（早于第一层判定）

> [输出协议 reload]：本章节及后续所有装配工具调用期间，过程描述走 thinking，user-facing 仅在终态与反问输出。

### 感知设备清单

调 `heiman-cli sensor list`，取 `enabled=true` 的子集记为 N。结果给 §Rule.感知设备 装配阶段消费。与 §重复检查 / §person 清单 并行调用。

### person 清单

调 `heiman-cli person list` 拿 role/name 列表，结果给 §Rule.condition.query 主语决策消费。与 §感知设备清单 / §重复检查 并行调用。

### task_id 规范

agent 自己起，snake_case `[a-z0-9_]{1,32}`，需含语义（`drink_8_today` / `fall_alert` / `window_open_remind`），不用纯数字 / 简短缩写。

### 重复检查

调 `heiman-cli task list --pretty` 拿活跃 task 列表，按 task_id + description + rule_briefs 比对：

| 类型 | 判据 | 处理 |
|---|---|---|
| A 名字冲突 | 待建 task_id 命中现有活跃 task | 让用户换 task_id 或先 terminate 旧 |
| B 语义重复 | description 表意一致 / rule_briefs 触发+动作组合本质相同 | 反问三选一：替换 / 强制新建 / 取消 |
| C 触发冲突 | 同 source + 同 condition + 动作矛盾或参数改写 | 反问三选一：替换并删旧（旧历史不可恢复）/ 暂停旧建新（旧历史保留，可恢复）/ 取消 |

**跳过条件**：
- 命中 task_id 是 paused → 让用户先 enable 或 delete，不算冲突
- 作用对象不同（不同传感器/房间/设备）→ 不算冲突
- 同 source + 同 condition 但 piid 不同 → 不算冲突，并存

**禁止主动 update / delete**：A / B / C 类命中后等用户答复，不私自 update / delete 已有 rule / cron / record / task。

---

# 第一层 · task 维度判定

> [输出协议 reload]：本章节及后续所有装配工具调用期间，过程描述走 thinking，user-facing 仅在终态与反问输出。

task 是聚合根，含：

- 0~N 个 rule（**Rule** 判存在性）
- 0~N 个 cron（**Schedule** 判存在性）
- 0~1 个 record（**Record** 判存在性）
- 1 个 lifecycle 属性（**Lifecycle** 判取值）

Rule/Schedule/Record 是子组件存在性（Y/N）；Lifecycle 是 task 整体属性（permanent/temporary）。四者独立判，不互依赖。

## Rule?（Y/N）

**Y** = 用户描述需要系统**持续观察现实世界**才能触发的场景，含以下任一语义：

- **环境状态变化**：人在/不在、设备开关状态、温度湿度烟雾等环境量异常
- **人体可观测动作或行为**：任何能被传感器或摄像头识别的人体动作或姿态
- **人身安全异常**：摔倒、入侵、求救、火灾相关
- **计数/累计数字目标**：N 次/杯/个 或 累计 N 小时/分钟

**N** = 纯时间触发或纯查询，不依赖现实事件。

**Rule 跟 Schedule 完全独立**：句中含任何现实事件信号（动作/环境/状态变化/计数目标）就 Rule=Y，**即使同句有定时提醒**。

## Schedule?（Y/N）

**核心判据**：触发是否依赖**时钟锚点**（在某个未来时间点 / 周期性时间点上由系统主动发起）。

- **时钟锚点触发**：用户期望系统按时钟自动触发，无需现实事件配合 → **Y**
- **现实事件触发**：触发由感知事件或时长持续状态发起，不依赖时钟 → **N**

**Y 的语义**（含以下任一）：

- 单一未来**具体时点**（明天 12 点 / N 分钟后 / 一会儿 / 后天 等明确到小时/分钟/相对偏移）
- 周期性**具体时点**（每天早上 8 点 / 每周三 9 点 / 工作日 7 点 等明确含时段或时点的周期）
- 显式定时措辞（定时提醒 / 到点提醒 / 每 N 小时催一次 等含具体时间间隔的措辞）
- **周期+计数无具体时点 + 无显式定时措辞**（每天/每周 N 杯/次/个 等周期目标） → 默认装周期定时提醒 → **触发装配提示**

**"每天累计/合计/总共/加起来 N 小时/分钟"** → Schedule=N。区别于"每天 N 杯/N 次"离散计数 → Schedule=Y 定时提醒。

**不归 Schedule**：

- 时长阈值（"持续/连续 N 分钟"）
- 限时窗口（"今天/这周/这个月"）
- 语气词（一声/一下）

## Record?（Y/N）

**核心判据**：用户语义里**是否含"累计/计数"信号**。

- **含**累计/计数 → **Y**
- **不含** → **N**

**累计/计数信号**（含以下任一即 Y）：

- **计数达标**：够 N / 超过 N / 目标 N / 喝 N 杯 / 走 N 步 / 吃 N 次药 / 做 N 个
- **计数统计**："几杯/多少次/几个"等问句计数
- **时长累计**：累计/总共/合计/加起来 N 小时/分钟
- **量化反查**：算/统计/看/问 X 多久 / X 了多久 / 算 X 几次 / 看 X 用了多少时间
- **历史记录意图**：记录/统计/跟踪/数 / 记下每次 / 看历史
- **周期重置**：每天 N 杯 / 每周 N 次

**Record=Y → Rule=Y（强约束）**：record 各 kind 必须由 rule 触发写入。

## Lifecycle（permanent / temporary）

**核心判据**：用户的规则是**长期常驻**还是**只在某个有限时间段内有效**。

- **长期常驻**：用户期望规则不限时一直生效，每次满足触发条件都响应 → **permanent**
- **限时有效**：用户期望规则只在某个有限时间段内有效，过期或满足完成条件后失效 → **temporary**

按以下信号**顺序判**，命中第一个即停：

1. **周期信号**（每天/每周/工作日/周末/每月/以后/一直/总是/每次/都）→ permanent
2. **时间窗信号**（用户原话明确含时间段截止：今天/今晚/这周/本月/本月底前）→ temporary
3. **达标完成信号**（"做够 N / 达到 N 个 / 满足 N 次"作为整个规则的终止条件）→ temporary
4. **绝对一次性时刻信号**（"明天 X 点 / N 分钟后 / 后天 / 一会儿"作为唯一触发点）→ temporary
5. **以上都无** → permanent

---

# 第二层 · 按取值展开子维度

## Rule=Y 时填 Rule

### Rule.mode（event / state）

**核心判据**：是否需要对"进入条件"和"离开条件"**双向响应**？
- 是 → `state`
- 否 → `event`（触发条件含持续时长用 `duration_seconds` 修饰，不改 mode）

按顺序判，命中即停：

1. **Record.kind=duration（跨次累计 record）** → `state`
2. **人身安全/紧急异常** → `event`
3. **显式 state 信号** → `state`
4. **到达/进入类瞬时事件** → `state` + 长 `exit_debounce_seconds` + `on_exit` 留空
5. **其他一次性判断** → `event`

### Rule.condition.query

**condition.query 是「判定 X 在发生」的命题**——主语 + 谓语，主语类型由命题语义决定。

- 必须是当下传感器信号的具体描述
- 不含字面 AND/OR 信号词
- 不含断言式措辞（"检测到 / 识别到 / 已..." 等）
- 不含时长修饰（持续/累计 N 分钟 → 走 duration_seconds 或独立时长字段）

**主语取值规则**：

| 命题语义 | 主语取值 |
|---|---|
| 人在做某事（具体姓名 / 家庭关系称谓）| 跑 `heiman-cli person list` 解析 |
| 抽象集合（家人 / 家庭成员）| `已注册成员` + 触发装配提示 |
| 有人 / 任何人 | `任何人` + 触发装配提示 |
| 陌生人 / 外人 | `陌生人` |
| 物体异常（烟雾 / 火焰 / 积水）| 物体名词，取自用户原话 |
| 场景状态（无人 / 明暗）| `画面` 或具体房间名 |
| 句中无明示主体 | `用户` + 触发装配提示 |

### Rule.action

每方向单独判（state mode 下 ENTERED / EXITED 独立选）：

| 动作性质 | 装配 | fire 时谁执行 |
|---|---|---|
| 能 100% 写死（开关固定设备、播固定文本）| action JSON | rule engine 直接执行 |
| 需按运行时状态/上下文决定 | desc 文案（业务意图）| fire-agent 独立 turn 推理执行 |

**desc 写法**：业务语义，不贴 CLI 命令字面。文案以**客观陈述事件**为准，不含「检测到/识别到/感知到」等系统视角词。

### Rule.duration_seconds

**含义**：触发条件需要持续 N 秒才算成立。

推荐值：

| 动作类别 | 推荐 |
|---|---|
| 一般简单姿态动作 | 30 |
| 久坐/久站/久躺类前置确认 | 60 |
| 屏幕/读写沉浸类前置确认 | 90 |
| 运动/健身/锻炼类前置确认 | 180 |
| 拿不准 | 60 |

### Rule.exit_debounce_seconds

state mode 防边沿抖动 / 防重复触发。

| 场景 | 推荐 |
|---|---|
| state 双向边沿去重（默认） | 60 |
| 瞬时事件防重复 / 持续行为入态 · 长窗（默认） | 1800 |

## Schedule=Y 时填 Schedule

**Schedule.message**：写业务意图，fire-agent fire 时独立 turn 推理执行。

### Schedule.触发器

| 类型 | 信号 |
|---|---|
| `at` | 单一未来时刻 |
| `every` | 固定间隔 |
| `cron` | 时钟模式 / 周期重复 |

## Record=Y 时填 Record

### Record.kind

| kind | 用户语义 |
|---|---|
| `progress` | 计数达标 + 明确目标正整数 |
| `duration`（含阈值） | 累计/连续超过 N 小时/分钟 |
| `duration`（无阈值） | 记录/统计/追踪 X 时长，无目标数字 |
| `event` | 累积事件流 |

### Record.task_type

| task_type | 判据 |
|---|---|
| `recurring` | 含周期/习惯化语义 |
| `oneshot` | kind=progress/duration + 含限时窗口语义 |
| `longterm` | kind=event + 任意时间语义或无时间语义 |

## Rule=Y + 动作含通知类语义 时填通道

**触发条件**：用户用了**含糊动作词且未明示通道**。

含糊动作词分两类：

- **通知类**：提醒 / 告诉 / 通知 / 告知 / 喊我 / 让我知道 等
- **对人输出语音/文本类**：夸 / 鼓励 / 表扬 / 安慰 / 欢迎 / 招呼 / 说一句 等

必反问 A/B/C，等用户答复后装 desc：

- **A. 使用音箱播报通知**
- **B. 使用手机推送通知**
- **C. 使用 AI 对话通知**

---

# 第三层 · 装配映射

按维度取值映射到 CLI 命令。多命令按顺序执行。

`--name` 必带 `[<task_id>]` 前缀。

## CLI 命令

| 维度 | CLI |
|---|---|
| 创建 task | `heiman-cli task create --task-id <id> --description "<描述>"` |
| Rule=Y | `heiman-cli rule create --task-id <id> <rule-flags>` |
| Schedule=Y | 调 OpenClaw cron tool 创建 cron job → 拿 `jobId`；调 `heiman-cli task link --task <id> --kind cron --ref <jobId>` 挂 |
| Record=Y | `heiman-cli task record init <id> --kind <progress/duration/event> --content '<JSON>'` |
| Lifecycle=temporary | 调 OpenClaw cron tool 建 termination at job |

## Rule flag 映射

| 维度取值 | flag |
|---|---|
| name（必填） | `--name "[<task_id>] <场景描述>"` |
| `mode=event` | `--mode event` |
| `mode=state` | `--mode state` |
| `condition.query` | `--condition "<query>"` |
| event + action JSON | `--action '<JSON>'` |
| event + desc | `--action-desc "<desc>"` |
| state + on_enter action JSON | `--on-enter-action '<JSON>'` |
| state + on_enter desc | `--on-enter-desc "<desc>"` |
| state + on_exit action JSON | `--on-exit-action '<JSON>'` |
| state + on_exit desc | `--on-exit-desc "<desc>"` |
| `duration_seconds=N` | `--duration-seconds N` |
| `exit_debounce_seconds=N` | `--exit-debounce-seconds N` |

## Record content JSON

| kind | content |
|---|---|
| progress（temporary）| `{"target":N,"unit":"<次/杯/步>","window":"<day/week>","expires_at":"<ISO>"}` |
| progress（recurring）| `{"target":N,"unit":"<次/杯/步>","window":"<day/week>","recurring_pattern":{"window":"<day/week>"}}` |
| duration 含阈值（temporary）| `{"target_minutes":N,"expires_at":"<ISO>"}` |
| duration 含阈值（recurring）| `{"target_minutes":N,"recurring_pattern":{"window":"<day/week>"}}` |
| event | `{}` |

## 装配失败回滚

多步执行任一步失败 → 调 `heiman-cli task delete <task_id> --reason abandoned` 回滚。

## 装配示例

### 例 1

用户："客厅没人就关灯"

```bash
heiman-cli task create --task-id living_room_off --description "客厅没人关灯"
heiman-cli rule create --task-id living_room_off \
  --name "[living_room_off] 客厅无人关灯" \
  --mode event \
  --condition "画面中无人" \
  --duration-seconds 300 \
  --action '{"did":"<客厅灯 DID>","iid":"prop.on","value":false,"idempotent":true}'
```

### 例 2

用户："每天累计玩手机超 1 小时提醒"

```bash
heiman-cli task create --task-id phone_time_daily --description "每天累计玩手机超 1 小时提醒"
heiman-cli task record init phone_time_daily \
  --kind duration \
  --content '{"target_minutes":60,"recurring_pattern":{"window":"day"}}'
heiman-cli rule create --task-id phone_time_daily \
  --name "[phone_time_daily] 玩手机累计时长" \
  --mode state \
  --condition "用户手持手机，屏幕亮起朝向脸部，目光低头注视屏幕" \
  --duration-seconds 90 \
  --exit-debounce-seconds 60 \
  --on-enter-desc "记录计时起点" \
  --on-exit-desc "结束计时" \
  --on-target-desc "使用手机推送通知：今日累计玩手机已达目标时长，休息一下"
```

### 例 3

用户："明天 9 点提醒吃药"

```bash
AT_TIME=$(heiman-cli time-compute --anchor '{"kind":"tomorrow_at","time":"09:00:00"}')
heiman-cli task create --task-id med_tomorrow_9am --description "明天 9 点提醒吃药"
# 调 OpenClaw cron tool 建 at job → 拿 jobId
heiman-cli task link --task med_tomorrow_9am --kind cron --ref <jobId>
```