# 安装源自动查找（完整参考）

主文件 `SKILL.md` 的「安装源自动查找」节只保留常用命令与要点，本文是完整细节。
**日常安装不需要读本文**——默认地址已内置在 `scripts/heiman_ctl.py` 的 `DEFAULTS` 里，
技能包不携带任何 config 文件也能自动安装。排查「装不上 / 装错仓库」时才来查。

## 一、自动查找顺序

| # | 来源 | 需要联网 | 说明 |
|---|------|---------|------|
| 1 | `--source <git-url>` | 否（但克隆要） | 命令行显式指定，优先级最高（非自动） |
| 2 | `--project <path>` | 否 | 命令行显式指定本地已有源码，不克隆 |
| 3 | `HEIMAN_GIT_URL` | 否（但克隆要） | 环境变量，可选 `HEIMAN_GIT_BRANCH` |
| 4 | `HEIMAN_AGENT_HOME` / 内置常见安装路径 | 否 | 固定位置探测，零开销 |
| 5 | 本地已存在副本（有界扫描） | 否 | 找 `backend/heiman/pyproject.toml`；深度 ≤3、时间预算 10s，结果缓存 24h |
| 6 | `~/.heiman/agent.json` | 否 | 状态文件记住上次装的是哪个仓库 |
| 7 | `~/.heiman/config/install-sources.json` | 否（但克隆要） | 用户级配置（可选） |
| 8 | `<SKILL>/config/install-sources.json` | 否（但克隆要） | 技能级配置（可选） |
| 9 | 脚本内置默认值 | 否（但克隆要） | `heiman_ctl.py` 的 `DEFAULTS`，**开箱即得** |
| 10 | generated 候选 | 是 | hosts × orgs × 仓库名 逐个探测（兜底，最慢） |

要点：

- **本地优先**：1–8 里凡是能直接指到本地目录的（2/4/5/6），都不走网络克隆。
- **远端必探测**：来自 3/7/8/9 的远端地址，先用 `git ls-remote --heads` 确认可达，
  指定了 `branch` 时还要确认分支存在，全部满足才采用。
- **探测有预算**：单项超时 6s、总预算 40s，触顶即在 `tried` 里标注「总预算耗尽，已跳过」，
  绝不会无限等待。
- **命中即停**：找到第一个可用的源就返回，不继续尝试后面的。

## 二、配置文件（可选）

| 层 | 路径 | 用途 |
|---|---|---|
| 内置默认值 | `scripts/heiman_ctl.py: DEFAULTS` | 随技能分发，团队共用默认地址，**始终生效** |
| 技能级（可选） | `<SKILL>/config/install-sources.json` | 想改默认值又不想动 Python 代码时使用 |
| 用户级（可选） | `~/.heiman/config/install-sources.json` | 个人环境覆盖，由 `source set` 生成 |

合并顺序：内置 → 技能级 → 用户级（逐字段深度合并），后者覆盖前者。
`source show` 输出的 `config_layers` 会列出每层是否命中，`"optional": true` 的层
没加载属于正常情况。

### 字段说明（配置文件里出现时才会覆盖内置值）

| 字段 | 默认 | 说明 |
|---|---|---|
| `repo_name` | `heiman-agent` | 仓库名，generated 候选与扫描识别时使用 |
| `primary` | 内网仓库地址 | 首选 git 地址 |
| `primary_branch` | `master` | 首选分支；也可用环境变量 `HEIMAN_GIT_BRANCH` 覆盖 |
| `candidates` | 内网仓库 SSH 地址 | 备选地址数组，元素为字符串或 `{url, branch, origin}` |
| `generated.hosts` | github/gitlab/gitee | generated 候选的域名列表 |
| `generated.orgs` | Heiman 等 | generated 候选的组织名列表 |
| `scan.roots` | `~`、Documents 等 | 扫描根目录（深度 3） |
| `scan.extra_roots` | `D:/`、`C:/` | 盘符根，用更小的深度 2 扫描 |
| `scan.max_depth` | `3` | 普通根目录扫描深度 |
| `scan.extra_root_depth` | `2` | 盘符根扫描深度 |
| `scan.budget_seconds` | `10.0` | 单次扫描时间预算，到点即停 |
| `scan.cache_hours` | `24` | 扫描结果缓存时长 |
| `scan.skip_dirs` | node_modules 等 | 跳过的目录名（大小写不敏感） |
| `probe.timeout_seconds` | `6.0` | 单个地址探测超时 |
| `probe.total_budget_seconds` | `40.0` | 一轮探测的总时间预算 |
| `clone.dest` | `src/heiman-agent` | 克隆目标目录。相对路径按 `~/.heiman` 解析（推荐）；也支持绝对路径与 `~` |
| `clone.depth` | `1` | 浅克隆深度；服务端不支持时自动回退全量 |
| `clone.timeout_seconds` | `600` | 单次 clone/fetch 超时 |

### 支持的地址形式

```
https://host/org/repo.git
http://host/org/repo.git          # 可用，但会告警"明文传输"
git@host:org/repo.git             # SCP 形式，内部转成 ssh://
file:///D:/mirror/heiman-agent    # 本地/网络盘镜像
```

需要鉴权时把凭据写进 URL（`https://user:token@host/org/repo.git`），
脚本会自动脱敏，日志与输出里只会看到 `https://***:***@host/...`。

## 三、命令

```bash
# 全自动安装（推荐入口）
python scripts/heiman_ctl.py install

# 指定分支 / 目标目录 / 不更新已有副本 / 不探测
python scripts/heiman_ctl.py install --branch master --dest D:/src/heiman-agent
python scripts/heiman_ctl.py install --no-update
python scripts/heiman_ctl.py install --no-probe

# 查看当前解析到的源（不联网落地）
python scripts/heiman_ctl.py source show

# 探测所有候选地址的可达性
python scripts/heiman_ctl.py source probe
python scripts/heiman_ctl.py source probe --url "<git-url>" --branch master

# 扫描本机已存在的克隆
python scripts/heiman_ctl.py source scan
python scripts/heiman_ctl.py source scan --root "D:/code" --root "E:/work" --max-depth 4

# 只同步源码，不装依赖
python scripts/heiman_ctl.py source sync --branch master

# 持久化 / 清除用户级配置
python scripts/heiman_ctl.py source set "<git-url>" --branch master
python scripts/heiman_ctl.py source clear
```

`source show` 关键字段：

- `origin` — 来源层级：`cli` / `env` / `local-clone` / `state` / `user-config` /
  `skill-config` / `skill-default`（脚本内置默认值）/ `generated`
- `url_display` — 脱敏后的地址（原始含凭据地址不会输出）
- `branch`、`local_path`、`action`（`cloned` / `updated` / `reused` / `resolved`）
- `tried[]` — 逐个候选的探测结果，排障时看这个

## 四、典型场景

### 换仓库地址

```bash
python scripts/heiman_ctl.py source set "https://new-host/heiman/agent.git" --branch main
python scripts/heiman_ctl.py install
```

个人机器用 `source set` 就够了。团队统一分发时，可在技能包里放一份
`<SKILL>/config/install-sources.json`（技能级层），它覆盖内置默认值、
又被人各自的 `source set` 覆盖——但这一步不是必须的。

### 内网 / 走代理

```bash
export http_proxy="http://proxy.corp:8080"
export https_proxy="http://proxy.corp:8080"
python scripts/heiman_ctl.py source probe
```

脚本只在访问**远端 git 仓库**时走代理；对 `127.0.0.1` / `localhost` 的探活、取数
一律**强制直连**，因此开发机设了全局代理也不需要手动配 `NO_PROXY`——
否则代理会把本地请求一并转发并返回 502，导致 `status` 把健康的服务误判成不可用。

本机实测：公网仓库 `https://github.com/heimanhome/heiman-agent.git`（master 分支）
与内网 Gitea `http://192.168.1.14:10082/xiaoli/heiman-agent.git`（匿名可读，22 端口
不通所以只用 http）均可达。内网地址作为 candidates 备选保留：GitHub 连不上时
自动兜底；如果希望反过来内网优先，把两个地址对调即可。

### 完全离线

```bash
# 有网机器上先拉好
python scripts/heiman_ctl.py source sync --dest /media/usb/heiman-agent
# 目标机器指向本地副本
python scripts/heiman_ctl.py --project "/media/usb/heiman-agent" install
```

### 扫描太慢 / 误扫

```bash
HEIMAN_NO_SCAN=1 python scripts/heiman_ctl.py install        # 关闭扫描
HEIMAN_SCAN_ROOTS="D:/code;E:/work" python scripts/heiman_ctl.py source scan
```

## 五、安全约束

| 约束 | 实现 |
|---|---|
| 不卡交互 | `GIT_TERMINAL_PROMPT=0`、`GCM_INTERACTIVE=never`、SSH `BatchMode=yes` |
| 凭据不泄漏 | 输出与日志统一 `redact_url()`；状态文件只存脱敏地址 |
| 不覆盖已有副本 | origin 不同时只复用并给出切换提示 |
| 有界执行 | 扫描深度/时间预算、探测单超时+总预算、clone 超时 |

## 六、排障

见 `troubleshooting.md` 第 1、13、14 条。快速三连：

```bash
python scripts/heiman_ctl.py doctor
python scripts/heiman_ctl.py source show
python scripts/heiman_ctl.py source probe
```
