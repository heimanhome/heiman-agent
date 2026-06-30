# Heiman Agent Plugins

海曼智能家居Agent插件系统，包含多种插件实现和OpenClaw集成。

## 目录结构

```
plugins/
├── base/                    # 基础插件抽象
│   ├── __init__.py
│   └── plugin_base.py       # 插件基类定义
├── examples/                # 插件示例
│   ├── alert_plugin.py       # 告警插件
│   ├── email_alert_plugin.py # 邮件告警插件
│   ├── log_plugin.py         # 日志插件
│   ├── mqtt_plugin.py        # MQTT插件
│   └── webhook_plugin.py     # Webhook插件
└── openclaw/                # OpenClaw插件
    ├── src/                  # TypeScript源码
    ├── dist/                 # 编译输出
    ├── skills/               # Skill定义
    ├── tests/                # 单元测试
    └── ...
```

## 插件类型

### 1. 基础插件 (base/)
提供插件抽象基类，用于Python环境下的插件开发。

### 2. 示例插件 (examples/)
展示各种插件类型的实现示例：
- `alert_plugin.py` - 基础告警
- `email_alert_plugin.py` - 邮件告警
- `log_plugin.py` - 日志记录
- `mqtt_plugin.py` - MQTT消息
- `webhook_plugin.py` - Webhook回调

### 3. OpenClaw插件 (openclaw/)
与OpenClaw平台集成的现代化插件系统。

## OpenClaw插件开发

### 目录结构
```
openclaw/
├── src/
│   ├── config.ts           # 插件配置
│   ├── index.ts            # 插件入口
│   ├── hooks/              # Hook系统
│   ├── services/           # 服务层
│   ├── tools/              # 工具定义
│   ├── utils/              # 工具函数
│   ├── webhooks/           # Webhook处理
│   └── mock/               # Mock SDK
├── skills/                  # Skill定义
│   ├── heiman-sensors/     # 传感器查询
│   ├── heiman-events/      # 事件管理
│   └── heiman-rules/       # 规则控制
├── tests/                  # 单元测试
├── dist/                   # 编译输出
├── openclaw.plugin.json    # 插件配置
├── package.json
└── tsconfig.json
```

### 可用Skills

| Skill | 描述 | 触发场景 |
|-------|------|----------|
| heiman-sensors | 传感器数据查询 | "查看温度"、"传感器状态" |
| heiman-events | 事件管理 | "查看告警"、"确认报警" |
| heiman-rules | 规则控制 | "启用规则"、"查看自动化" |

## 安装指南

### 前置要求
- Node.js >= 18.0.0
- pnpm >= 8.0.0
- OpenClaw >= 1.0.0

### 安装步骤

1. **安装依赖**
```bash
cd plugins/openclaw
pnpm install
```

2. **构建插件**
```bash
pnpm run build
```

3. **链接到OpenClaw**
```bash
# 创建软链接到OpenClaw插件目录
ln -s $(pwd) ~/.openclaw/plugins/heiman-agent

# 或复制到插件目录
cp -r . ~/.openclaw/plugins/heiman-agent
```

4. **配置插件**
在OpenClaw配置文件 `~/.openclaw/config.json` 中添加：
```json
{
  "plugins": {
    "entries": {
      "heiman-openclaw-plugin": {
        "enabled": true,
        "config": {
          "debug": false,
          "backend_url": "http://localhost:1912"
        }
      }
    }
  }
}
```

5. **启动验证**
```bash
# 重启OpenClaw
openclaw restart

# 查看插件状态
openclaw plugin list
```

## 开发指南

### 本地开发
```bash
# 进入插件目录
cd plugins/openclaw

# 安装依赖
pnpm install

# 开发模式（监听文件变化自动重载）
pnpm run dev

# 运行测试
pnpm test

# 构建生产版本
pnpm run build
```

### 调试技巧
1. 启用调试模式：
```json
{
  "config": {
    "debug": true
  }
}
```

2. 查看日志：
```bash
openclaw logs -f heiman-agent
```

### 添加新Skill

1. 在 `skills/` 目录下创建新目录
2. 添加 `SKILL.md` 文件
3. 实现相关工具函数
4. 注册到插件入口

## 相关资源

- [海曼HTTP协议文档](../../knowledge/03-api/api-reference.md)
- [插件开发指南](../../knowledge/04-dev-guide/plugin-development.md)
- [提示词定义](../../knowledge/07-prompts/smart-home-agent.md)

## License

MIT
