# 故障排查

先用自检命令缩小范围：

```bash
python scripts/heiman_ctl.py doctor
python scripts/heiman_ctl.py status
python scripts/heiman_ctl.py logs -n 120
```

## 1. 找不到项目根目录 / 找不到安装源

**现象**：`start` 返回 `未找到 heiman-agent 项目根目录`，或 `install` 返回
`未能自动定位到可用的 heiman-agent 安装源`。

**处理**：先跑自动安装，它自己会找源码或 git 地址，不需要手填来源

```bash
python scripts/heiman_ctl.py install
python scripts/heiman_ctl.py where      # 看它最终定位到了哪
python scripts/heiman_ctl.py source show
```

只在自动链路失败时才需要人工介入，任选其一：

```bash
# 1) 写入用户级配置（推荐，优先级最高且不被脚本更新覆盖）
python scripts/heiman_ctl.py source set "<git-url>" --branch master
# 2) 换团队共享默认值：编辑 scripts/heiman_ctl.py 的 DEFAULTS["primary"]，
#    或（可选）放一份 <SKILL>/config/install-sources.json
# 3) 环境变量
export HEIMAN_GIT_URL="<git-url>"
export HEIMAN_GIT_BRANCH="master"
# 4) 命令行显式指定
python scripts/heiman_ctl.py install --source "<git-url>"
python scripts/heiman_ctl.py --project "<项目根>" install
```

技能包**不需要** `config/install-sources.json`：脚本内置的默认地址已经够用，
缺这个文件不会报"找不到配置"。

自动查找顺序（完整版见 SKILL.md 的「安装源自动查找」章节）：
`--source` → `--project` → `HEIMAN_GIT_URL` → `HEIMAN_AGENT_HOME`/内置常见路径 →
本地克隆有界扫描 → `~/.heiman/agent.json` → 用户级配置 → 技能内置配置 → generated 候选。

需要固定来源的场景，直接设置 `HEIMAN_AGENT_HOME`，避免依赖自动探测。
扫描太慢可用 `HEIMAN_NO_SCAN=1` 关闭，或 `HEIMAN_SCAN_ROOTS="<dir1>;<dir2>"` 限定范围。

## 2. 端口被占用

**现象**：`start` 返回 `端口 127.0.0.1:1912 已被其他进程占用`。

**处理**：

```bash
# 换个端口启动
python scripts/heiman_ctl.py start --port 1913
```

或先停掉占用进程：

```bash
# Windows
netstat -ano | findstr :1912
taskkill /PID <PID> /F
# macOS / Linux
lsof -i :1912
kill <PID>
```

> 注意：换端口后需同步更新 `~/.heiman/config.json` 的 `server.url` 与 `backend/heiman/.env` 的 `SERVER_PORT`。

## 3. 启动后进程立即退出

**现象**：`start` 返回 `后端进程启动后立即退出`。

**排查**：

```bash
python scripts/heiman_ctl.py logs -n 120
```

常见原因：

| 日志特征 | 原因 | 处理 |
|----------|------|------|
| `ModuleNotFoundError` | 依赖未装全 | 重跑 `install --force` |
| `pydantic` 校验错误 | `.env` 字段类型不对 | 检查 `.env` 的 `SERVER_PORT` 等是否为合法值 |
| 端口 `Address already in use` | 端口冲突 | 见第 2 条 |
| `账号未登录` / `401` | 海曼云端 token 过期 | 见第 5 条 |

## 4. 健康检查超时但进程还在

首次启动需要登录海曼云端并拉取设备列表，可能耗时较长。

```bash
python scripts/heiman_ctl.py health
python scripts/heiman_ctl.py logs -n 60
```

若日志出现 `Manager initialization failed`，多为云端网络不通或凭据错误。

## 5. 海曼云端返回"账号未登录"

**现象**：日志里先出现 `Logged in successfully, user_id: ...`，紧接着
`get_home_list` 报 `401 账号未登录`；或 `heiman_snapshot.py` 取到 0 设备、服务进入
`Running in OFFLINE mode`。

**处理**：先用 AskUserQuestion 让用户选绑定方式（SKILL.md「第 1.8 步」），再按下述路径处理。

**路径 A（默认，与 `.env` 无关）**：

1. 引导用户打开 `http://127.0.0.1:1912`：未绑定时页面自动弹出登录对话框，
   或点**左侧边栏底部**账号区域 → 跳海曼官方授权页登录。
   OAuth 的 `client_id` 等参数是后端内置默认值，**不需要改 `.env`**。
2. 已绑定但 token 失效：`python scripts/heiman_ctl.py api POST /api/auth/logout`
   （清 token + 断 MQTT）→ 用户刷新页面重新绑定。

**路径 B（用户把账号密码交给 Agent，Agent 代写 `.env`）**：

```bash
python scripts/heiman_ctl.py env set --email "<用户邮箱>" --password "<用户密码>"
python scripts/heiman_ctl.py restart
python scripts/heiman_ctl.py env auth-url      # 取授权地址发给用户，这步不能省
```

`env set` 会自动删掉 `HEIMAN_APP_ID=your_app_id` 占位符（保留真实数值），
`env show` 输出脱敏。若重启后日志仍 `total=0`，按 5.1 自动回读真实 appId。

> **关键认知：路径 B 也不能免掉 OAuth。** 后端 `login()` 只用 `app_id` + `email` 查用户
> （`HEIMAN_PASSWORD` 后端根本不读），回包里没有 token，`get_home_list` 依旧 401。
> 所以「填了 .env 还是取不到数」是预期行为，不是故障——补一次浏览器授权即可。

**无头/远程场景兜底**（两条路径通用）——生成授权地址发给用户：

```bash
python scripts/heiman_ctl.py env auth-url
```

**验证**：

```bash
python scripts/heiman_ctl.py api GET /api/auth/token   # 期望 authenticated: true
python scripts/heiman_snapshot.py                      # 期望设备非空
```

### 5.1 陷阱一：`HEIMAN_APP_ID` 是模板占位符

`.env` 由模板生成，`HEIMAN_APP_ID` 的默认值是 `your_app_id` —— 恰好 11 个字符，
**长得像真值**，但必然查不到用户。

登录走的是 `POST /api-app/appUser/get/listByPage`，只用 **`appId` + `email`**（**不使用密码**）。
`appId` 是云端给"应用"分配的编号，用来在多租户用户表里定位你的账号。用变体请求可自证：

| 请求参数 | 返回 |
|---|---|
| `appId=your_app_id` + email | `total=0` ❌ |
| **仅 `email`**（不带 appId） | `total=1`，回包里带真实 `appId` ✅ |
| 空参 | 返回平台上全部用户 |

**推荐修法：先删掉这一行。** 源码里 `HeimanSettings.app_id` 的默认值就是 `"11"`，
`.env` 里这行的唯一作用是**覆盖默认值** —— 不写它反而会正确使用内置的 `11`。
也就是说这个字段是「照抄模板的人踩坑，删掉的人没事」。

**但删掉不一定够**。实测平台上共存着 **3 种 appId**（采样 1000 人）：

| appId | 占比 |
|---|---|
| `11` | 82.5% |
| `13` | 17.1% |
| `12` | 0.4% |

约 **1/6 的用户不属于 appId 11**，这些人必须填自己的值。所以正确的排查顺序是：

1. **确认 `HEIMAN_APP_ID` 整行不存在**（`install` 生成 `.env` 时已自动注释占位符；
   若看到真实数值则保留） → 重启 → 若 `Logged in successfully` 则结束（覆盖大多数）
2. **仍然 `total=0`** → 用「仅 email」查一次回读真实 appId，再填回 `.env`：

   ```python
   import asyncio, sys
   sys.path.insert(0, "<项目根>/backend/heiman/src")
   from heiman_mcp.client.heiman import HeimanClient
   async def m():
       c = HeimanClient(base_url="https://spapi.heiman.cn", token="")
       r = await c.get_user_list(page_size=1, page_number=1, email="<账号邮箱>")
       lst = (r.get("result") or {}).get("list") or []
       print("total:", (r.get("result") or {}).get("total"), "| appId:", lst[0].get("appId") if lst else None)
   asyncio.run(m())
   # 期望输出: total: 1 | appId: 11  ← 把这个数字填回 .env
   ```

3. 填回后重启验证。

> **结论：绝大多数用户不需要提供 app_id**（删掉那行即可）。只有当第 1 步失败时才需要查，
> 而且**不需要问用户要** —— 用上面的请求自动回读就行。
>
> 另：`.env` 里的密码在这个接口里根本不参与校验。
> 该接口无任何鉴权，空参会返回全部 8348 个用户，属服务端安全问题，不要对外暴露此服务。

### 5.2 陷阱二：email/password 拿不到 token，必须走 OAuth2

即使上面修好了、日志打印 `Logged in successfully`，`get_home_list` 仍会 401。
因为查用户接口**不返回 token**，客户端里 `self._access_token = user.get("token", "")` 是空的，
所有需要鉴权的接口自然全 401。

**真正能拿到 token 的路径是 OAuth2**。**默认让用户在 Web 界面完成**（打开
`http://127.0.0.1:1912` → 登录对话框 / 侧边栏底部账号区域 → 登录海曼账号），
无头/远程场景（或用户选了路径 B）由 Agent 生成授权地址：

```bash
# 1) 生成授权地址（服务需已启动）
python scripts/heiman_ctl.py env auth-url

# 2) 把返回的 authorize_url 发给用户 → 浏览器打开 → 用海曼账号登录
#    → /api/auth/heiman_redirect 回调换取 token
# 3) 日志应出现：Attempting MQTT connection with access_token=..., user_id=...
```

> `client_id` / `redirect_uri` 是项目 `settings.py` 的内置默认值，不是占位符，无需再配置。

**token 会持久化落库**（写在 `kv` 表的 `heiman_oauth_token` 键里，数据库默认
`~/.heiman/logs/heiman.db`）。验证一次即可，**之后重启服务无需再授权**：

```bash
python -c "import sqlite3;print([r[0] for r in sqlite3.connect(r'C:\Users\rd98\.heiman\logs\heiman.db').execute('SELECT key FROM kv')])"
# 期望输出: ['heiman_oauth_token']
```

授权成功后确认有数据：

```bash
python scripts/heiman_snapshot.py   # 应看到 homes / devices / sensors 非空
```

### 5.3 已知非阻塞问题

`/api/homes` 可能打日志 `Failed to save member ...: PersonRepo.create() got multiple
values for argument 'role'`。这只是**成员未落库**（`members_saved=0`），
接口本身仍返回 200，设备/房间数据不受影响，可忽略。

## 6. 换账号登录后设备列表为空（多家庭场景）

**现象**：接口返回 `success: true` 且 `data: []`（HTTP 200，不报错），设备/传感器全查不到。
若同时观察 `/api/homes`，还会看到 `home_id` 与之前**不一样**。

**根因**（源码位置：`client/heiman_api_client.py` 的 `get_devices()`）：

```python
if not home_id:
    homes = await self.get_home_list()
    if not homes:
        return {}
    home_id = homes[0].get("id", homes[0].get("homeId"))   # ← 永远选第 0 个
```

调用方未显式传 `home_id` 时，客户端**固定取 `homes[0]`**，没有持久化"上次选中的家庭"，
也不做多家庭让用户选择。因此账号下若有多个家庭，取到的可能就是**没有设备的那个**。

**为什么"换账号"会触发**：`_cleanup()` 会清掉 `self._user_id` / `_homes_cache` / `_devices_cache`，
新账号登录后 `_homes_cache` 重新拉取，`homes[0]` 的顺序由云端返回决定 —— 换了账号，
列表顺序变了，选中的家庭也跟着变。**与账号下家庭数量有关**：单家庭账号恒定命中，
多家庭账号则取决于排序，可能命中空家庭。

**另一个易混现象**：`get_devices(home_id=...)` 命中缓存后（TTL 300 秒）即使切了账号也可能
返回旧数据；反之切换瞬间缓存已清但云端列表未就绪，会**短暂返回空列表**（等待几秒重试即恢复）。

**处理**：

1. 先确认账号下有几个家庭、哪个有设备：
   ```bash
   python scripts/heiman_ctl.py api GET /api/homes
   python scripts/heiman_ctl.py api GET /api/identity/persons
   ```
   对比 `home_id` 与设备返回的 `home_id` 是否一致。
2. 显式指定家庭取数（绕过 `homes[0]`）：
   ```bash
   python scripts/heiman_ctl.py api GET "/api/devices?home_id=<目标家庭ID>"
   ```
3. 空列表若为切换瞬间，**等待 5–10 秒重试**，不要误判为服务故障。
4. 根治需改源码：在 `get_devices` 中改为读取持久化的上次家庭
   （`shared_state.get_last_home(user_id)` / `set_last_home`，键前缀 `heiman_last_home_`
   已存在但当前**未被 `get_devices` 使用**），或让前端/接口传入 `home_id`。

> 报告类输出前务必核对 `home_id` 一致性：安全指数会因取到空家庭而虚报为
> `online_rate=0`、扣 10 分，看起来像"设备全部离线"的严重故障，实为选错家庭。

## 7. 访问 `/` 返回 404

**原因**：静态资源目录计算错误（v2.1.0 已修复）。

**验证**：

```bash
python scripts/heiman_ctl.py api GET /api/admin/status
```

确认 `HEIMAN_STATIC_DIR` 指向 `<project>/backend/heiman/static`。技能脚本启动时会自动设置该变量。
若该目录下没有 `index.html`，说明前端未构建，需要：

```bash
cd web && pnpm install && pnpm build
```

## 8. 数据库 `no such table`

**原因**：旧版本数据库升级时未补齐缺失表（v2.1.0 已修复，启动时自动检测补齐）。

**处理**：先重启；仍失败则删除数据库重新初始化：

```bash
rm -f ~/.heiman/data/heiman.db
python scripts/heiman_ctl.py restart
```

> 删除前请确认可以接受历史数据丢失。

## 9. 源文件被企业加密软件加密（本机常见）

**现象**：用 `cat` / `head` / Read 读取项目里的 `.md` `.py` `.json` 文件时，内容以
`%TSD-Header-###%` 开头，是乱码（亿赛通等 DLP 透明加密）。

**影响**：只影响**读取**；Python 解释器、IDE 等白名单进程读取时会被透明解密，服务本身可正常运行。

**绕过方式**（需要读源码时）：

```bash
# 用 git 读取（git 对象未被加密）
git show HEAD:README.md
git show HEAD:backend/heiman/src/heiman/main.py

# 或整体导出明文副本
git archive HEAD | tar -x -C /tmp/heiman-src
```

## 10. Windows 特有注意事项

- 技能脚本用 Python 标准库实现，不依赖 bash，Windows 下可直接运行。
- 虚拟环境位于 `~/.heiman/venv`（不在项目目录内），避免企业加密软件影响 venv 中的 `.py` 文件。
- 后台启动使用 `DETACHED_PROCESS`，关闭终端不会杀掉服务；停止请用 `stop` 子命令而非直接关窗口。
- 若 `python` 不在 PATH，用绝对路径调用，例如 `"<Python 安装路径>/python.exe" scripts/heiman_ctl.py status`（Windows 也可用 `py -3.13` 启动器）。

## 11. 停止服务

```bash
python scripts/heiman_ctl.py stop
```

Windows 下通过 `taskkill /T /F` 终止进程树；macOS/Linux 先 `SIGTERM`，超时后 `SIGKILL`。

## 12. 完全重置

```bash
python scripts/heiman_ctl.py stop
rm -rf ~/.heiman          # 删除 venv、数据、日志、配置、自动克隆的源码
```

> 该操作不可逆，会删除数据库与配置。执行前请确认。

## 13. git 源探测全部失败（`git ls-remote` 报错）

**现象**：`source probe` 里每个地址都 `ok: false`，或 `install` 报「未能自动定位到可用的安装源」。

**排查**：

```bash
python scripts/heiman_ctl.py source probe        # 逐个看失败原因
python scripts/heiman_ctl.py where               # 确认 project_root 是否已被定位到
```

| 报错特征 | 原因 | 处理 |
|---|---|---|
| `Could not resolve host` / `Connection refused` | 网络不通或端口未开放 | 确认能访问该 git 服务；内网仓库先连 VPN |
| `Connection refused` 且端口 22 | SSH 未开放 | 改走 http/https 地址（本机内网仓库即如此） |
| `does not appear to be a git repository` | 地址路径写错 | 核对 org / repo 名，浏览器打开确认 |
| `Authentication failed` / `403` | 凭据缺失或过期 | 在 `primary` 里带 token，或配好 SSH key；`BatchMode=yes` 下不会交互提示 |
| `timeout` | 代理或防火墙拦截 | 配 `http_proxy` / `https_proxy`，或调大 `probe.timeout_seconds` |

**兜底**：确认地址无误但探测仍不通时，用 `--no-probe` 跳过探测直接克隆；
或先手工克隆到任意目录，再用 `--project <路径>` 指向它。

## 14. 克隆目标目录非空

**现象**：`source sync` / `install` 报 `克隆目标目录非空且不是 git 仓库`。

**处理**：换一个 `--dest`，或清空该目录后重试。已存在另一来源的副本时脚本会
**只复用不覆盖**，如需切换来源请先手动删除该目录。
