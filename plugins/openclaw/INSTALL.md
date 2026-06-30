# OpenClaw 海曼插件安装指南

本文档提供在本地环境中为OpenClaw安装海曼Agent插件的详细步骤和操作指南。

## 📋 前置要求

### 系统要求
- **操作系统**: macOS 12+ / Ubuntu 20.04+ / Windows 10+ (WSL2)
- **Node.js**: >= 18.0.0
- **pnpm**: >= 8.0.0 (推荐)
- **OpenClaw**: >= 1.0.0

### 检查环境
```bash
# 检查Node.js版本
node --version
# 要求: v18.0.0 或更高

# 检查pnpm版本
pnpm --version
# 要求: 8.0.0 或更高

# 检查OpenClaw
openclaw --version
# 要求: 1.0.0 或更高
```

### 安装缺失工具
```bash
# 安装pnpm (如果未安装)
npm install -g pnpm

# 安装OpenClaw (如果未安装)
# 参考: https://openclaw.dev/docs/installation
```

---

## 🚀 安装步骤

### 方式一：从源码安装（推荐开发者）

#### 1. 克隆或定位项目
```bash
# 如果项目在其他位置，使用以下命令
cd /Users/haiman/Documents/trae_projects/heiman-agent/plugins/openclaw

# 或克隆仓库
git clone https://github.com/your-org/heiman-agent.git
cd heiman-agent/plugins/openclaw
```

#### 2. 安装依赖
```bash
# 安装项目依赖
pnpm install

# 预期输出:
#  Packages: +103
#  +++++++++++++++++++++++++++++++++++++++++++++++++++++
#  Done in 6.1s
```

#### 3. 构建插件
```bash
# 构建生产版本
pnpm run build

# 预期输出:
#  > @heiman/openclaw-plugin@1.0.0 build
#  > tsc
#  ✓ Build complete
```

#### 4. 运行测试（可选）
```bash
# 运行所有测试
pnpm test

# 运行测试并查看覆盖率
pnpm run test:coverage

# 预期输出:
#  ✓ tests/heiman.test.ts (3 tests)
#  ✓ tests/backend.test.ts (3 tests)
#  ✓ tests/tools.test.ts (3 tests)
#  Test Files  3 passed (3)
#  Tests       9 passed (9)
```

#### 5. 链接到OpenClaw
```bash
# 创建插件目录（如果不存在）
mkdir -p ~/.openclaw/plugins

# 创建软链接
ln -sf "$(pwd)" ~/.openclaw/plugins/heiman-agent

# 验证链接
ls -la ~/.openclaw/plugins/heiman-agent
```

### 方式二：复制安装（适用于生产环境）

#### 1. 构建并打包
```bash
cd plugins/openclaw

# 构建
pnpm run build

# 打包dist目录和必要文件
mkdir -p dist-plugin
cp -r dist dist-plugin/
cp -r skills dist-plugin/
cp openclaw.plugin.json dist-plugin/
```

#### 2. 复制到OpenClaw插件目录
```bash
# 复制插件到OpenClaw目录
cp -r dist-plugin ~/.openclaw/plugins/heiman-agent

# 重命名目录（如果需要）
mv ~/.openclaw/plugins/dist-plugin ~/.openclaw/plugins/heiman-agent
```

---

## ⚙️ 插件配置

### 1. 编辑OpenClaw配置
```bash
# 打开OpenClaw配置文件
nano ~/.openclaw/config.json
```

### 2. 添加插件配置
```json
{
  "plugins": {
    "entries": {
      "heiman-openclaw-plugin": {
        "enabled": true,
        "config": {
          "debug": false,
          "backend_url": "http://localhost:1912",
          "notifySessionKey": "main"
        }
      }
    }
  }
}
```

### 3. 配置说明

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `debug` | boolean | `false` | 启用调试模式，输出详细日志 |
| `backend_url` | string | `http://localhost:1912` | Heiman Agent后端API地址 |
| `notifySessionKey` | string | `main` | 通知目标session key |

### 4. 环境变量配置（可选）

也可以通过环境变量配置：
```bash
export HEIMAN_BACKEND_URL=http://localhost:1912
export HEIMAN_DEBUG=false
```

---

## ✅ 验证安装

### 1. 重启OpenClaw
```bash
# 重启OpenClaw服务
openclaw restart

# 或使用开发模式
openclaw dev
```

### 2. 检查插件状态
```bash
# 列出已安装插件
openclaw plugin list

# 预期输出:
# ✓ heiman-openclaw-plugin (enabled)
```

### 3. 查看插件日志
```bash
# 实时查看插件日志
openclaw logs -f heiman-agent

# 预期输出:
# [heiman] Initializing Heiman Agent OpenClaw Plugin
# [heiman] Registering Heiman services
# [heiman] Registering Heiman hooks
# [heiman] Heiman Agent OpenClaw Plugin initialized successfully
```

### 4. 测试插件功能
```bash
# 使用CLI测试后端连接
heiman-cli health

# 预期输出:
# ✓ Backend connected
# ✓ API version: v1.0.0
```

---

## 🛠️ 常见问题排查

### 问题1: 插件无法加载
```
错误: Plugin heiman-openclaw-plugin failed to load
```

**解决方案**:
1. 检查TypeScript编译是否成功
```bash
pnpm run build
```

2. 检查插件文件是否存在
```bash
ls -la ~/.openclaw/plugins/heiman-agent/dist/
```

3. 查看详细错误日志
```bash
openclaw logs heiman-agent 2>&1 | tail -50
```

### 问题2: 后端连接失败
```
错误: connect ECONNREFUSED 127.0.0.1:1912
```

**解决方案**:
1. 确保后端服务正在运行
```bash
# 启动后端服务
cd backend/heiman
python -m heiman

# 或使用CLI
heiman-cli service start
```

2. 检查后端URL配置
```bash
# 确认配置正确
openclaw config get plugins.entries.heiman-openclaw-plugin.config.backend_url
```

### 问题3: Skills无法加载
```
错误: Skills directory not found
```

**解决方案**:
1. 确保skills目录存在
```bash
ls -la ~/.openclaw/plugins/heiman-agent/skills/
```

2. 重新复制skills目录
```bash
cp -r skills ~/.openclaw/plugins/heiman-agent/
```

### 问题4: 权限问题
```
错误: EACCES: permission denied
```

**解决方案**:
```bash
# 修复插件目录权限
chmod -R 755 ~/.openclaw/plugins/heiman-agent

# 如果使用软链接，修复源目录权限
chmod -R 755 /Users/haiman/Documents/trae_projects/heiman-agent/plugins/openclaw
```

---

## 🔧 开发调试

### 启用调试模式
在配置中设置 `debug: true`:
```json
{
  "plugins": {
    "entries": {
      "heiman-openclaw-plugin": {
        "config": {
          "debug": true
        }
      }
    }
  }
}
```

### 使用开发模式
```bash
# 启动OpenClaw开发模式
openclaw dev --reload

# 监听源码变化自动重载
cd plugins/openclaw
pnpm run dev
```

### 调试工具
```bash
# 查看所有插件日志
openclaw logs

# 查看特定插件日志
openclaw logs heiman-agent

# 实时跟踪日志
openclaw logs -f heiman-agent

# 导出日志
openclaw logs --export heiman-agent.log
```

---

## 📦 卸载插件

### 临时禁用
编辑 `~/.openclaw/config.json`，将 `enabled` 设置为 `false`:
```json
{
  "plugins": {
    "entries": {
      "heiman-openclaw-plugin": {
        "enabled": false
      }
    }
  }
}
```

### 完全卸载
```bash
# 停止OpenClaw
openclaw stop

# 删除插件目录
rm -rf ~/.openclaw/plugins/heiman-agent

# 删除软链接（如果有）
rm -f ~/Documents/trae_projects/heiman-agent/plugins/openclaw

# 重启OpenClaw
openclaw start
```

---

## 📚 相关资源

- [OpenClaw 官方文档](https://openclaw.dev/docs)
- [海曼Agent后端文档](../backend/README.md)
- [插件开发指南](../knowledge/04-dev-guide/plugin-development.md)
- [提示词文档](../knowledge/07-prompts/smart-home-agent.md)

---

## 🤝 技术支持

如遇到问题，请通过以下方式获取帮助：

1. 查看 [常见问题排查](#-常见问题排查) 部分
2. 查看 [GitHub Issues](https://github.com/your-org/heiman-agent/issues)
3. 联系技术支持团队
