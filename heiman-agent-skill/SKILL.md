---
name: heiman-agent
display_name: 海曼智能家居管家
display_name_en: Heiman Smart Home Agent
description: 在 WorkBuddy 中自动查找 git 地址并安装、启动、操作本地 heiman-agent 服务，查询海曼（Heiman）智能家居设备与传感器数据并生成家庭安全/环境分析报告。回答语言始终跟随用户最近一条提问的语言（英文提问必全英文回答，含表头）。触发场景：用户提到 海曼、heiman、heiman-agent、heiman-cli、智能家居、家庭传感器、烟雾报警器、一氧化碳报警器、温湿度传感器、水浸传感器、门磁探测器、家庭安全报告、设备告警、环境舒适度、传感器历史趋势、家庭成员、家庭任务、家庭规则自动化，或要求安装/启停/检查本地 heiman 服务。
description_zh: 自动查找 git 地址并安装、启动、操作本地海曼智能家居传感器 Agent，查询设备状态、事件与规则，生成家庭安全与环境分析报告。
description_en: Auto-discover the git source, install, launch and operate the local Heiman smart-home sensor agent from WorkBuddy. Query Heiman devices, sensors, events, rules and family members, and generate home safety / environment reports. Use when the user mentions Heiman, heiman-agent, heiman-cli, smart home sensors (smoke, CO, temperature/humidity, water leak, door contact), home safety reports, device alarms, indoor comfort, sensor history trends, or asks to start/stop/check the local heiman service.
category: capability
version: 1.0.2
author: Heiman
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
user-invocable: true
---

# 海曼智能家居管家

操作本地 `heiman-agent` 服务（FastAPI 后端 + Web 界面 + `heiman-cli`），把海曼智能家居设备的实时数据变成可执行的结论。

## 输出语言

**在调用任何工具之前，先判定用户最近一条提问的语言，并锁定本次输出语言。** 判定对象是**最近一条提问本身**，不是会话历史：

| 用户最近一条提问 | 本次输出语言 | 说明 |
|---|---|---|
| `Check the device list` | **全英文** | 即使整个会话历史都是中文，也必须英文——以最近一条为准 |
| `查一下设备列表` | 全中文 | 同理 |
| `用英文回答：设备状态` / `用中文写份报告` | 显式指定的语言 | 显式指令 > 提问语言 |
| `1`、`继续`、`ok` | 沿用会话已记录语言 | 真正无法判定才沿用；能判定就跟随 |

全英文输出意味着** everything**：结论、标题、表头（`Device`/`Type`/`Room`/`Status`/`Battery`/`Reading`）、栏目名、脚注、建议、结尾提问——出现任何一个汉字即判定失败（云端设备名/房间名/品牌/错误码保留原文，但英文输出须附英文注释，见下方「云端中文数据怎么处理」）。写完后扫一遍：英文回答里夹了汉字，回去重写。


**云端中文数据怎么处理（英文输出的唯一例外）**：设备名、房间名来自云端，本身常常就是中文（如 `温湿度`、`智能网关`、`客厅`）。英文输出时**保留中文原名**（便于与 App / 云端精确对应），但**首次出现必须紧跟英文注释**——**表格单元格同样适用**：英文表格的 `Device` 列里，每个中文设备名都要写成 `原名 (English gloss)`，不允许裸中文名单独成格：

| 云端原名 | 英文输出写法 |
|---|---|
| `温湿度` | `温湿度 (Temp-Humidity sensor)` |
| `一氧化碳报警器` | `一氧化碳报警器 (Carbon monoxide alarm)` |
| `智能网关` | `智能网关 (Gateway)` |
| `门磁` | `门磁 (Door contact sensor)` |
| `客厅` | `客厅 (Living room)` |

首次注释之后，可只用英文注释名指代。**中文输出不需要注释**（原名与提问语言一致）。设备型号、错误码、品牌名同样保留原文。

**快捷方式（优先用）**：英文模式下 `heiman_snapshot.py` 已为每个传感器算好 `name_display` 字段（= `原名 (English gloss)`），并在输出顶层带 `rendering_hint` 渲染提醒——表格和行文首次出现**直接照抄 `name_display`**，不要自己拼，更不要留裸中文名。

## 快速上手（首次使用）

本技能是「说明书 + 运维脚本」，**下载技能 ≠ 服务可用** —— 真正的 heiman-agent 服务仍需在用户本机安装一次。

### 用户视角：两步走

| 步骤 | 谁来做 | 做什么 |
|---|---|---|
| 1. 安装并启动 | **Agent 自动** | 对 WorkBuddy 说「帮我安装并启动 heiman-agent」即可，其余全自动（查找/克隆源码 → 建 venv → 装依赖 → 启动 → 健康检查） |
| 2. 选择绑定方式 | **Agent 询问，用户选** | **必须**用 AskUserQuestion 让用户二选一：A 自己在 Web 界面登录（不动 `.env`）；B 把海曼账号密码交给 Agent，由 Agent 写入 `.env`。详见「第 1.8 步」 |

两条路径**最后都需要一次浏览器 OAuth 授权**——token 只能这么换，这是海曼云端的硬性要求，不是配置问题。

之后日常使用**不需要任何命令**，直接自然语言提问：「客厅现在多少度」「这周有哪些告警」「生成一份家庭安全报告」。

装完的产物在 `~/.heiman/`（venv、源码、数据、日志），服务在 `http://127.0.0.1:1912`。

> **关于 `.env`：路径 A 完全不用动，路径 B 由 Agent 代写。**
> 授权用的 `client_id` / `client_secret` / `redirect_uri` 是后端 `HeimanSettings` 的
> **内置默认值**（源码 `config/settings.py`），与 `.env` 无关。
> `.env` 里的 `HEIMAN_EMAIL` / `HEIMAN_PASSWORD` / `HEIMAN_APP_ID` 只服务旧的无 token 查询通道
> （`login()` 只用 `app_id` + `email`，**密码后端根本不读**），取不到 token。
> 路径 B 的价值是让该通道定位到 user_id，方便排查 appId 归属；**它不能替代 OAuth**。
> 注意 `HEIMAN_APP_ID` 占位符 `your_app_id` 的陷阱（见 `references/troubleshooting.md` 5.1），
> `install` 生成 `.env` 时已自动注释该行，`env set` 也会自动删掉它。

### Web 界面绑定入口速查（Agent 引导用户时用）

| 位置 | 说明 |
|---|---|
| 登录对话框 | 未绑定时刷新页面自动弹出（`HeimanLoginDialog`），点登录按钮即跳 OAuth |
| 侧边栏底部账号区域 | **真正的账号管理入口**（头像 + 账号名）：已绑定点开菜单有「重新绑定 / 解绑」；未绑定点击直接发起绑定 |
| 右上角人形图标 | **静态装饰，无点击事件**——用户点它没反应不是 bug，引导去侧边栏底部 |
| 窗口宽度要求 | 侧边栏仅 ≥768px 显示（`hidden md:flex`）；窗口太窄时让用户最大化浏览器，否则找不到账号入口 |
| 退出/换账号 | 前端菜单「解绑」，或 `api POST /api/auth/logout`（清 token + 断 MQTT）后刷新页面 |

### Agent 视角：首次接到请求时

- 用户在问海曼数据 → 先 `status` 探活；`installed: false` 时**不要追问用户**，直接跑 `install`（会自动查找 git 地址并克隆，无需手动指定来源）。
- 安装耗时较长（实测约 9 分钟，几乎全在 pip 拉依赖），过程中**主动告知用户正在安装且需要几分钟**，避免被误认为卡死。
- 装完若 `service_up: true` 但设备数为 0 → 这是账号未绑定，**不要重复 install**，按「第 1.8 步」**先让用户二选一**（Web 绑定 / 提供凭据代填 `.env`），再引导完成 OAuth 授权。
- **不要主动索要账号密码**：只有用户选了路径 B 才收凭据，且输出与日志里必须脱敏。

> ⚠️ **别把「填凭据」当最终解法**：`.env` 那条通道查得到用户、换不到 token，
> 设备数为 0 / 日志报 `401 账号未登录` 时，正确动作是补一次 OAuth 授权，见「第 1.8 步」。

## 环境要求

- **Python ≥ 3.10**：脚本使用 `str | None`、`tuple[str, int]` 等 PEP 604 类型标注语法，Python 3.9 及以下会直接语法报错。请先确认 `python --version` ≥ 3.10。
- **技能脚本仅依赖标准库**：`scripts/` 下的脚本不引入任何第三方包，无需为技能本身安装 pip 依赖。
- **安装阶段需要联网**：`install` 会创建 `~/.heiman/venv` 并以 `pip install -e` 安装后端依赖，需能访问 PyPI；离线环境请预先配置内网源。
- **自动获取源码需要 git**：本地没有源码时，`install` 会自动查找 git 地址并克隆
  （详见「安装源自动查找」）。源码已在本地时，不依赖 git。
- **Node.js + pnpm 仅 Web 界面需要**：需要浏览器界面时才要求（`cd web && pnpm install && pnpm build`）；纯取数、分析与报告生成不依赖它。
- **Windows 说明**：脚本用标准库实现，Windows 下可直接运行。`templates/workflow.sh` 是 bash 入口，
  Git Bash / MSYS2 下已兼容（内部用 `pwd -W` 规避 MSYS 路径改写）；完全无 bash 时请按「标准工作流」逐步执行。

## 路径约定

- **技能目录**：本文件所在目录。下文 `<SKILL>` 指该目录。
- **项目根目录**：`heiman-agent` 源码仓库。探测顺序：`--project` → `HEIMAN_AGENT_HOME` →
  状态文件 → 常见安装路径 → 本地克隆有界扫描。找不到时 `install` 会自动从 git 地址克隆。
- **自动克隆目录**：`~/.heiman/src/heiman-agent`。写相对路径时按 `~/.heiman` 解析，
  改 `HEIMAN_HOME` 会让 venv / 数据 / 日志 / 源码整体跟着走。
- **安装源配置（可选）**：默认地址已内置在 `scripts/heiman_ctl.py` 的 `DEFAULTS` 里，
  **技能包不需要任何 config 文件**即可自动安装。需要覆盖时才用
  `source set <url>`（写入 `~/.heiman/config/install-sources.json`），团队分发时也可
  另放 `<SKILL>/config/install-sources.json`。
- **运行时目录**：`~/.heiman`（venv、数据、日志、配置）。
- **服务地址**：`http://127.0.0.1:1912`（默认）。端口由 `~/.heiman/agent.json` 持久化：`start --port` 写入，`status` / `snapshot` 读取，因此无需在每条命令上重复指定。

## 执行总原则

1. **先探活，再取数**：任何数据类任务开始前，先执行 `status`；未运行则执行 `start`。
2. **一律走脚本**：不要手写 curl 或直接拼 URL。取数用 `<SKILL>/scripts/heiman_snapshot.py`，
   服务管理与其他接口用 `<SKILL>/scripts/heiman_ctl.py`。
3. **输出即结论**：给用户的回复是分析结论 + 行动建议，不是原始 JSON。原始 JSON 仅用于自己判断。
4. **只读优先**：查询类任务不修改任何状态。写操作（确认事件、增删规则、控制设备）必须先说明影响并取得用户同意。
5. **脱敏**：输出中不要暴露完整 `did`、`userId`、家庭详细地址。
6. **语言跟随提问（最高优先级，完整规则见文首「输出语言」节）**：以用户**最近一条提问**的语言输出，报告标题、表头、结论、建议全部同一语言。脚本输出、`api` 返回、`references/` 正文都属**中间量**，一律按提问语言转述，不要照抄。

## 安装源自动查找（无需手动指定来源）

本地没有 heiman-agent 源码时，`install` 会自动定位 git 地址、克隆、再装依赖。
**默认地址已内置在 `scripts/heiman_ctl.py` 的 `DEFAULTS` 里，技能包不需要任何 config 文件即可自动安装。**

```bash
python scripts/heiman_ctl.py install                                   # 全自动（推荐入口）
python scripts/heiman_ctl.py source show                               # 看当前解析到的源（不联网）
python scripts/heiman_ctl.py source probe                              # 探测候选地址可达性
python scripts/heiman_ctl.py source set "<git-url>" --branch master    # 换仓库地址
python scripts/heiman_ctl.py source sync --branch master               # 只同步源码，不装依赖
```

要点：

- **本地优先**：已有副本 / 状态文件 / 常见安装路径命中即直接复用，不联网克隆。
- **远端必探测**：`git ls-remote` 确认可达才采用；单项超时 6s、总预算 40s，**命中即停**。
- **探活与取数强制直连**：对 `127.0.0.1` 不走代理，开发机设了全局代理也无需配 `NO_PROXY`
  （否则代理会把本地请求转发出去返回 502，导致 `status` 把健康服务误判成不可用）。

> 换地址优先用 `source set`（写 `~/.heiman/config/install-sources.json`），
> 不要编辑 Python 代码——用户配置不会被技能更新覆盖。
> 完整查找顺序、配置字段表、离线部署等场景见 `@references/install-source.md`。

## 标准工作流

### 第 1 步：探活

```bash
python "<SKILL>/scripts/heiman_ctl.py" status
```

输出字段：`service_up`（服务是否可用，等同 `ok`）、`managed_by_skill`、`installed`、`project_root`、
`pid`、`url`、`health`、`hint`。

**`service_up: true` → 进入第 2 步。**（注意：判定字段是 `service_up`，没有 `running` 字段。）

未运行 → 启动：

```bash
python "<SKILL>/scripts/heiman_ctl.py" start
```

若报「未找到项目根目录」，不要追问用户，直接跑 `install`（会自动查找并克隆源码）。

### 第 1.5 步：仅需确认服务是否存活时

```bash
python "<SKILL>/scripts/heiman_ctl.py" health        # 只调 /health，输出更精简
python "<SKILL>/scripts/heiman_ctl.py" where         # 打印探测到的项目根目录 / venv / 日志路径 / 安装源
```

未安装（`installed: false`）→ `install` + `start`，随后按「第 1.8 步」让用户选绑定方式。

### 第 1.8 步：绑定海曼账号（必须先让用户二选一）

**先说结论，避免走弯路**：`.env` 里的邮箱/密码**换不到 token**（后端 `login()` 只用
`app_id` + `email` 查用户，密码根本不读，回包里也没有 token），所以无论选哪条路径，
**最后都必须有一次浏览器 OAuth 授权**。装完服务若设备数为 0、日志报 `401 账号未登录`，
就是这个授权没做。

#### 第一步：用 AskUserQuestion 让用户选绑定方式（必做，不要替用户决定）

```json
{
  "questions": [{
    "header": "绑定方式",
    "multiSelect": false,
    "question": "heiman-agent 已装好，怎么绑定你的海曼账号？",
    "options": [
      {"label": "A. 我自己在网页上登录（推荐）",
       "description": "打开 http://127.0.0.1:1912 点登录，跳转海曼官方页输账号密码。密码只经过海曼官网，Agent 不接触、也不改任何配置文件"},
      {"label": "B. 我给你账号密码，你帮我填",
       "description": "Agent 把邮箱密码写入 backend/heiman/.env 并自动清掉 HEIMAN_APP_ID 占位符。注意：填完仍需你在浏览器登录一次完成授权"}
    ]
  }]
}
```

**不要在用户表态前替他填 `.env`**，也不要主动索要密码——只有选了 B 才向用户要凭据。
用户给了密码后，**回复与日志里一律不回显明文**。

#### 路径 A：Web 界面绑定（推荐，不碰 `.env`）

1. 浏览器打开 `http://127.0.0.1:1912`；
2. 未绑定时页面自动弹出登录对话框；未弹出则点**左侧边栏底部**的账号区域
   （入口细节见「快速上手」的「Web 界面绑定入口速查」表）；
3. 跳转海曼官方授权页 → 用户用自己的账号登录 → 自动回调换 token。

#### 路径 B：用户提供账号密码，Agent 代写 `.env`

```bash
# 1) 写入凭据（脚本自动删除 HEIMAN_APP_ID 占位符，回退到源码内置默认值 11）
python scripts/heiman_ctl.py env set --email "<用户给的邮箱>" --password "<用户给的密码>"

# 2) 重启让配置生效
python scripts/heiman_ctl.py restart

# 3) 生成 OAuth 授权地址发给用户（token 唯一来源，这步不能省）
python scripts/heiman_ctl.py env auth-url
```

脚本行为要点：

- `env set` 只改 `HEIMAN_EMAIL` / `HEIMAN_PASSWORD`，**保留 `.env` 其余配置**；
- 遇到 `HEIMAN_APP_ID=your_app_id` 这类**占位符**（非纯数字）自动删掉该行，
  让源码内置默认值 `11` 生效；已是真实数值则原样保留；
- `env show` 输出一律脱敏（`HEIMAN_PASSWORD` 恒为 `******`）；
- `env clear` 把凭据重置回模板占位符（用户反悔时用）。

若重启后日志仍 `total=0`（约 1/6 账号不属于 appId 11），按
`references/troubleshooting.md` 5.1 节用「仅 email」请求**自动回读真实 appId**，
**不要向用户索取**。

#### 通用说明

- token 存在数据库 `kv` 表的 `heiman_oauth_token` 键里，带 `refresh_token` 自动续期，
  **重启后自动加载，无需重复授权**；
- 验证：`python scripts/heiman_snapshot.py` —— homes / devices / sensors 应非空；
- 无头/远程场景（没有浏览器 UI）统一走 `env auth-url` 取授权地址发给用户。

### 第 2 步：取数

**首选**：一条命令拿到归一化后的完整快照（已含类型识别、阈值判定、严重级别、安全评分）：

```bash
python "<SKILL>/scripts/heiman_snapshot.py"                  # 默认中文文案
python "<SKILL>/scripts/heiman_snapshot.py" --lang en-US     # 英文文案（提问为英文时必带）
```

**取数与语言一起定**：脚本产出的文案（`type_label`、`readings` 的键名、`issues[].message`、
`comfort.*_verdict`）随 `--lang` 切换，不传默认 `zh-CN`。判定结果与数值不受语言影响。
下游要取值时一律读 `metrics`（稳定英文键，如 `metrics.temperature`），不要解析 `readings` 里的本地化文本。

- 中文提问 → `--lang zh-CN`（默认，可省略）
- 英文提问 → `--lang en-US`（**必带**，否则快照会给出中文文案）
- 其他语言 → 取最接近的 `en-US` 取数，输出时再改写成提问语言

快照会回带 `lang` 字段，用于确认本次渲染语言。

输出 JSON 关键字段：`lang`、`safety_score`、`score_breakdown`、`alerts`、`critical_count`、`warning_count`、
`comfort`、`device_count`、`sensors[]`（每项含 `name_display`——英文模式下为 `原名 (English gloss)`，渲染设备名时直接照抄、`readings`、`metrics`、`issues`、`level`）。

需要历史趋势时加 `--hours`：

```bash
python "<SKILL>/scripts/heiman_snapshot.py" --hours 168 --lang en-US
```

**按需补充**：快照未覆盖的接口用 `api` 子命令直接调用：

```bash
python "<SKILL>/scripts/heiman_ctl.py" api GET /api/rules --lang en-US
python "<SKILL>/scripts/heiman_ctl.py" api GET /api/tasks
python "<SKILL>/scripts/heiman_ctl.py" api GET /api/ai/summary
```

⚠️ `api` 返回的是后端原始数据，可能带中文字段名或中文枚举值，**输出前必须按提问语言转述**，不要照抄。
`--lang zh-CN|en-US` 会把语言作为 `Accept-Language` 传给后端，并在输出里回带 `lang` 字段；
后端当前对多数端点**不做内容协商**（例如设备 `name` 仍返回中文原名），因此该参数只是尽力而为——
**真正的保障仍是模型自己按提问语言转述**（云端数据保留原文 + 英文注释的规则见文首「输出语言」节）。

用户意图到调用的映射统一见下方「意图路由」表。

完整端点表见 `@references/api-spec.md`；`heiman-cli` 命令见 `@references/cli-reference.md`。

### 第 3 步：分析

1. **直接用快照结论**：`safety_score`、`alerts`、`level`、`comfort` 已由脚本按阈值算好，不要重算。
2. 需要解释字段含义或设备类型时查 `@references/device-model.md`。
3. 需要补充阈值依据、给出更细的定级说明时查 `@references/thresholds.md`。
4. 需要写趋势、离线处理、意图路由时查 `@references/analysis-logic.md`。
5. 快照中的 `readings["备注"]`（英文模式下为 `readings["note"]`）是脚本给出的纠偏提示（如门磁 `status=alarm` 的误报），必须在结论中体现。
6. **不要自己解析文案**：数值一律取 `metrics`（如 `metrics.temperature`、`metrics.co`）；`readings` 的键名与取值已按 `--lang` 选好语言，直接沿用即可，不要跨语言做字符串匹配（例如不要写 `if "报警" in status`）。
7. `references/*.md` 是**内部中文文档**，只用于判断，其中的措辞不要带进输出。

### 第 3.5 步：枚举与单位的展示文案

**机器值与展示文案必须分离**：`level`、`status`、`type`、`scope`、`battery` 这类枚举是程序判定的**机器值，永不翻译**（判断、比较、传给下游时一律用原值）；只有**给人看的展示文案**才按语言切换。这样既保证英文回答不夹中文，又不破坏 `if level == "critical"` 这类逻辑。

**判定一律用机器值**：`level == "critical"` ✅ ／ `level == "严重"` ❌。

#### 严重级别（`level` / `issues[].level` / `alerts[].level`）

| 机器值 | 中文 | English |
|---|---|---|
| `emergency` | 紧急 | emergency |
| `critical` | 严重 | critical |
| `warning` | 警告 | warning |
| `info` | 提示 | info |
| `normal` | 正常 | normal |

#### 设备状态（`status` / `device_count`）

| 机器值 | 中文 | English |
|---|---|---|
| `normal` | 正常 | normal |
| `alarm` | 报警 | alarm |
| `offline` | 离线 | offline |
| `low_battery` | 电量低 | low battery |
| `fault` | 故障 | fault |

#### 影响范围（`estimated_scope`）

机器值 `building_wide` / `floor_wide` / `localized`，展示文案与判定场景见
`@references/thresholds.md` 的「影响范围」表（含出现场景，比这里完整）。

#### 设备类型（`type`）

`type` 是机器值（`smoke` / `co` / `temperature` / `plug` / `water` / `motion` / `switch` / `gateway`），
展示时读快照已按 `--lang` 本地化好的 `type_label`，**不要**自己再查表翻译，也不要改 `type` 本身。

#### 舒适度判定（`comfort.*_verdict`）

快照已按 `--lang` 本地化并含数值与区间（如 `"湿度 68.0%，偏离舒适区间 40–60%"`），**直接沿用**，不要再拼一遍。

#### 单位

单位跟随文案语言，仅在**中英习惯不同**时才切换；℃/ppm/% 两种语言通用，保持原样。

| 量 | 中文 | English |
|---|---|---|
| 温度 | `25.0 ℃` 或 `25.0 °C` | `25.0 °C` |
| 湿度 | `60 %` | `60 %` |
| CO 浓度 | `35 ppm` | `35 ppm` |
| 电量 | `85 %` | `85 %` |

> **英文模式下的高频错例**：`Critical 告警`、`严重 alarm`、`设备 offline 建议检查电源`——
> 都是把机器值直接塞进了中文/英文句子里。正确写法：`Critical alert`、`Serious alarm`、`Device offline, check the power supply`。

### 第 4 步：输出

**先定语言，再定形式**（语言规则见文首「输出语言」节）。**会话历史是中文而本条提问是英文时，用英文模板**：

| 提问语言 | 报告正文模板 | 告警卡片模板 |
|---|---|---|
| 中文 | `@templates/report_zh.md` | `@templates/alert-card.md` |
| 英文 | `@templates/report_en.md` | `@templates/alert-card.en.md` |
| 其他语言 | 以 `report_en.md` 为基准改写固定文案，**不要退回中文模板** | 以 `alert-card.en.md` 为基准改写 |

- 日常问答 → 直接给结论 + 建议，3–10 行，用提问语言作答。
- 报告类请求 → 按 `@references/report-formats.md` 组织，套用上表对应语言的模板。
- 单条紧急告警 → 套用上表对应语言的模板。

**模板填充规则**：模板只是结构参考，包内**不含渲染脚本**。把 `{{...}}` 占位符替换为实际值；
列表/表格类字段有多少条就重复多少行，并手动编号 `1. 2. 3.`；无数据时中文写「无」、英文写 `None`，不要留空。
报告落盘文件名按语言加后缀（如 `2026-09-28-home-report-en.md`）。

报告默认写成 Markdown 文件并展示；用户只要结论时直接在对话中回答。

### 输出前自检（语言跟随验收）

回答前逐条核对，任一条不符就改：

| # | 检查项 | 通过标准 |
|---|--------|---------|
| 1 | 语言判定 | 与用户最近一条提问语言一致；显式指令（"用英文"）优先 |
| 2 | 无法判定 | 只输入"1"/"继续"/"ok"时沿用本会话语言，不擅自切回中文 |
| 3 | 全量一致 | 结论、建议、标题、表头、栏目名、列表项**同一语言**，无中英混杂 |
| 4 | 机器值未泄漏 | 回答正文不出现裸枚举（`critical`/`alarm`/`offline`/`building_wide` 直接夹在中文句中，或中文枚举夹在英文句中） |
| 5 | 中间量已转述 | 脚本输出、`api` 返回、`references/` 正文的中文均已转述为目标语言，未照抄 |
| 6 | 云端数据保留原文 + 英文注释 | 设备名、房间名、型号、错误码、品牌名保持原文；**英文输出中中文设备名/房间名首次出现必须附英文注释**（表格 `Device` 列同样适用，不留裸中文名单元格） |
| 7 | 模板选对 | 英文提问用 `report_en.md` / `alert-card.en.md`，未退回中文模板 |
| 8 | 数值与判定不变 | 切换语言后 `safety_score`、`level`、计数、`metrics` 数值**完全一致**，只有文案不同 |

最省事的自查：把答案在心里读一遍——若英文回答里夹了中文字符，或中文回答里夹了英文枚举，就是没通过。

### 备选：一条命令跑完

`@templates/workflow.sh` 把「安装 → 探活 → 取数」封装成一条命令，适合 CI 或定时任务：

```bash
bash "<SKILL>/templates/workflow.sh" --hours 168 --lang en-US --auto-install
```

`--port` 只影响 `start`；`status` / `snapshot` 从状态文件读端口。`--lang` 会透传给 `heiman_snapshot.py`。
`--auto-install` 只在检测到未安装时触发，会自动查找 git 地址并克隆（可配 `--source` / `--branch`）。
Windows 无 bash 时按上面第 1、2 步顺序执行。

## 意图路由

| 用户说法 | 处理 |
|----------|------|
| "看下家里的传感器" / "设备状态" | `heiman_snapshot.py` → 按在线/离线分类汇总，列出关键读数 |
| "客厅温度多少" | `heiman_snapshot.py`，在 `sensors[]` 里按 `name` 匹配 → 读数 + `comfort` 判定 |
| "家里有什么异常吗" | `heiman_snapshot.py` 的 `alerts` / `critical_count` / `warning_count`，按严重级别排序；无异常则明确回「✅ 一切正常」 |
| "这周温度有什么变化" | `heiman_snapshot.py --hours 168`（脚本自动换算 `start_time`）→ 趋势分析 |
| "生成今天的家庭安全报告" | 完整流程 → 日报模板 → 落盘 Markdown |
| "帮我建个规则" | 先 `api GET /api/rules` 看现有规则，与用户确认条件与动作后 `POST /api/rules` |
| 家庭成员 / 家庭 / 房间 / 任务 | 快照已含 `members`、`homes`、`rooms`；需单独取用 `api GET /api/identity/persons`、`/api/homes`、`/api/rooms`、`/api/tasks` |
| AI 分析结论 | `api GET /api/ai/anomaly`、`/api/ai/comfort`、`/api/ai/summary`、`/api/ai/suggest` |
| "服务还活着吗" / "重启服务" | `status` / `restart`；系统健康看 `api GET /health`、`/api/observability/overview` |

完整示例见 `@references/examples.md`（含自动安装、设备总览、单房间查询、异常排查、日报、趋势、规则、服务维护，以及多家庭取空、加密源码两个排障案例）。

## 安全边界

**可以做**：查询设备与历史数据、分析安全与舒适度、生成报告、发送告警建议。

**不可做**（拒绝并说明原因）：

- 跨家庭访问设备或数据；
- 修改设备固件配置；
- 在输出中暴露原始设备 ID、用户 ID、精确位置；
- **在回复、日志或任何非 `.env` 文件里留存用户的账号密码**（明文回显、写进笔记/报告/命令历史里都不行）；
- **未经用户明确选择就代填凭据**——只有用户在「第 1.8 步」选了路径 B 才允许写 `.env`。

> 路径 B 是**用户主动授权后的例外**：用户把账号密码交给 Agent，Agent 只把它们写进本机
> `backend/heiman/.env`（用 `env set`，脚本本身会脱敏输出），随后立即提醒用户改密码或
> 走路径 A 重绑。除此之外一律不碰凭据。

**需二次确认的操作**：

1. 发送 critical / emergency 级别通知；
2. 批量设备操作（超过 3 台）；
3. 删除历史数据、删除规则、删除任务；
4. 修改用户信息或家庭配置。

确认话术：「即将执行 X，影响范围是 Y，确认继续吗？」

## 故障处理

任务失败时按顺序排查：

```bash
python "<SKILL>/scripts/heiman_ctl.py" doctor
python "<SKILL>/scripts/heiman_ctl.py" where       # 项目根目录 / venv / 日志路径定位失败时先看这里
python "<SKILL>/scripts/heiman_ctl.py" health      # 只看 /health 连通性
python "<SKILL>/scripts/heiman_ctl.py" logs -n 120
```

常见问题与修复见 `@references/troubleshooting.md`。高频四类：

| 现象 | 处理 |
|------|------|
| 端口 1912 被占用 | `start --port 1913`，或停掉占用进程 |
| 日志报 `账号未登录` / 401 | token 失效或未绑定：让用户二选一——前端重新绑定（`http://127.0.0.1:1912` → 侧边栏底部账号区域），或提供凭据走 `env set` + `env auth-url`；已绑定仍失败则 `api POST /api/auth/logout` 清 token 后重绑。改 `.env` 只能定位用户、不能换 token，别把「填凭据」当成最终解法 |
| **换账号后设备列表为空（`data: []`，HTTP 200）** | 多家庭账号下客户端固定取 `homes[0]`，可能命中无设备的家庭；核对 `/api/homes` 的 `home_id`，显式传 `home_id` 取数。详见 troubleshooting 第 6 条 |
| **找不到项目根目录 / 安装源** | 直接跑 `install`（自动扫描本地 + 探测 git 地址克隆）；仍失败才按提示填 `primary` 或 `--source`。详见 troubleshooting 第 1 条 |
| **git 源探测全部失败** | `source probe` 看逐个报错；内网优先用 http/https（本机 22 端口不通），必要时 `--no-probe`。详见 troubleshooting 第 13 条 |
| 读取源码得到 `%TSD-Header-###%` 乱码 | 企业加密软件所致；用 `git show HEAD:<path>` 或 `git archive` 取明文 |

## 关键约束

- 单次历史查询上限 100 条，数据默认保留 30 天。
- 实时数据延迟不超过一个采集周期（默认 30 秒）。
- 服务是**本地**的：用户没启动服务时不要臆造数据，如实说明并提供启动命令。
