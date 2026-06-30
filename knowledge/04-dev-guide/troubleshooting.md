# 故障排除指南

## 常见问题

### 1. 后端服务无法启动

**症状**：`heiman-cli service start` 失败

**排查步骤**：

1. 检查端口是否被占用：
   ```bash
   lsof -ti:1912
   ```

2. 查看日志：
   ```bash
   heiman-cli service logs
   ```

3. 检查 Python 解释器配置：
   ```bash
   heiman-cli config get server.python_bin
   ```

4. 验证配置文件：
   ```bash
   heiman-cli config show
   ```

**常见原因**：
- 端口 1912 被其他进程占用
- `server.python_bin` 未配置或指向无效路径
- 依赖包缺失

---

### 2. 传感器数据不更新

**症状**：Web界面显示的传感器数据长时间没有更新

**排查步骤**：

1. 检查后端健康状态：
   ```bash
   heiman-cli debug ping
   ```

2. 检查传感器连接状态：
   ```bash
   heiman-cli monitor sensors --pretty
   ```

3. 检查认证状态：
   ```bash
   heiman-cli auth status
   ```

4. 检查海曼云API连接：
   ```bash
   heiman-cli doctor
   ```

**常见原因**：
- OAuth2 token 过期，需要重新认证
- 网络连接问题，无法访问海曼云API
- 传感器设备离线

---

### 3. Web界面无法访问

**症状**：浏览器访问 `http://localhost:5173` 失败

**排查步骤**：

1. 检查前端开发服务器是否运行：
   ```bash
   cd web && pnpm dev
   ```

2. 检查后端API是否正常：
   ```bash
   curl http://localhost:1912/health
   ```

3. 检查 CORS 配置：
   - 确认后端 `settings.py` 中 `ALLOWED_ORIGINS` 包含前端地址

**常见原因**：
- 前端开发服务器未启动
- 后端服务未启动
- 端口被防火墙阻止

---

### 4. 认证失败

**症状**：登录页面跳转后提示认证失败

**排查步骤**：

1. 检查 OAuth2 配置：
   ```bash
   heiman-cli config show
   ```

2. 确认 `client_id` 和 `client_secret` 正确配置

3. 检查网络是否能访问海曼OAuth2服务：
   ```bash
   curl -I https://spfile.heiman.cn/applogin/sso.html
   ```

**常见原因**：
- OAuth2 客户端凭证错误
- 网络无法访问海曼云平台
- 重定向URI不匹配

---

### 5. 插件无法加载

**症状**：插件在日志中显示加载失败

**排查步骤**：

1. 检查插件文件是否存在：
   ```bash
   ls plugins/examples/
   ```

2. 检查插件配置：
   ```bash
   cat ~/.heiman/plugins/<plugin_name>.json
   ```

3. 检查插件依赖：
   ```bash
   pip list | grep <dependency>
   ```

**常见原因**：
- 插件文件缺失或路径错误
- 配置文件格式错误
- 缺少依赖包

---

### 6. 数据库连接失败

**症状**：后端启动时数据库连接错误

**排查步骤**：

1. 检查数据库文件权限：
   ```bash
   ls -la ~/.heiman/
   ```

2. 检查数据库文件是否存在：
   ```bash
   ls ~/.heiman/*.db
   ```

3. 尝试重置数据库：
   ```bash
   heiman-cli admin reset --confirm
   ```

**常见原因**：
- 数据库文件权限不足
- 数据库文件损坏
- 磁盘空间不足

---

### 7. CLI 命令报错

**症状**：执行 CLI 命令时出现错误

**排查步骤**：

1. 检查 CLI 版本：
   ```bash
   heiman-cli version
   ```

2. 检查 Python 版本：
   ```bash
   python --version
   ```

3. 更新 CLI：
   ```bash
   pip install -e cli/
   ```

---

## 日志查看

### 后端日志

```bash
# 查看最后 50 行
heiman-cli service logs

# 持续跟踪日志
heiman-cli service logs -f

# 查看指定行数
heiman-cli service logs -n 100
```

### CLI 日志

```bash
# 启用调试模式
heiman-cli config set debug true

# 查看 CLI 日志
cat ~/.heiman/log/heiman-cli.log
```

## 常用诊断命令

```bash
# 环境诊断
heiman-cli doctor

# 系统状态
heiman-cli admin status

# 资源监控
heiman-cli monitor resources

# 传感器状态
heiman-cli monitor sensors

# 事件统计
heiman-cli event stats
```

## 联系支持

如果以上方法无法解决问题，请提供以下信息联系支持：

1. 操作系统版本
2. Python 版本
3. 完整的错误日志
4. `heiman-cli doctor` 输出
5. `heiman-cli config show` 输出（敏感信息请脱敏）