# 故障排查

先用自检命令缩小范围：

```bash
python scripts/heiman_ctl.py doctor
python scripts/heiman_ctl.py status
python scripts/heiman_ctl.py logs -n 120
```

## 1. 找不到项目根目录

**现象**：`install` / `start` 返回 `未找到 heiman-agent 项目根目录`。

**处理**：按优先级指定路径

```bash
python scripts/heiman_ctl.py --project "<项目根>" install
# 或
export HEIMAN_AGENT_HOME="<项目根>"
```

自动探测顺序：`--project` → `HEIMAN_AGENT_HOME` → `~/.heiman/agent.json` → 内置常见安装路径候选。
建议在需要固定的场景直接设置 `HEIMAN_AGENT_HOME`，避免依赖自动探测。

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

**现象**：接口返回 `账号未登录` 或 401。

**原因**：OAuth token 过期或 `HEIMAN_EMAIL` / `HEIMAN_PASSWORD` 未填写。

**处理**：

1. 编辑 `backend/heiman/.env`，确认：
   ```
   HEIMAN_API_URL=https://spapi.heiman.cn
   HEIMAN_APP_ID=11
   HEIMAN_EMAIL=<你的海曼账号>
   HEIMAN_PASSWORD=<你的海曼密码>
   ```
2. 重启服务：`python scripts/heiman_ctl.py restart`
3. 验证云端连通性：
   ```bash
   python scripts/heiman_ctl.py cli admin heiman-test
   python scripts/heiman_ctl.py api GET /api/auth/token
   ```
4. 仍失败时，通过 Web 界面 `http://127.0.0.1:1912/` 重新登录一次（浏览器 OAuth 流程）。

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
rm -rf ~/.heiman          # 删除 venv、数据、日志、配置
```

> 该操作不可逆，会删除数据库与配置。执行前请确认。
