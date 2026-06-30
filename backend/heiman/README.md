# Heiman Agent

海曼传感器智能Agent，用于智能家居安全监控。

## 功能特性

- 支持烟雾传感器、温湿度传感器、一氧化碳传感器、水浸传感器
- 基于海曼HTTP协议采集传感器数据
- 事件分类与告警
- 规则引擎支持自定义规则
- RESTful API接口

## 技术栈

- Python 3.10+
- FastAPI
- SQLite
- HTTPX

## 安装

```bash
cd backend/heiman
pip install -e .
```

## 运行

```bash
heiman-backend
```

或

```bash
python -m heiman.main
```

## API接口

### 传感器

- `GET /sensors` - 获取所有传感器
- `GET /sensors/{did}` - 获取单个传感器
- `POST /sensors/data` - 推送传感器数据
- `GET /sensors/{did}/history` - 获取传感器历史数据

### 事件

- `GET /events` - 获取事件列表
- `GET /events/{event_id}` - 获取单个事件
- `POST /events/{event_id}/acknowledge` - 确认事件

### 规则

- `GET /rules` - 获取规则列表
- `POST /rules` - 创建规则
- `PUT /rules/{rule_id}` - 更新规则
- `DELETE /rules/{rule_id}` - 删除规则
- `POST /rules/{rule_id}/conditions` - 添加条件
- `POST /rules/{rule_id}/actions` - 添加动作

## 配置

复制 `.env.example` 为 `.env` 并修改配置项。

## 项目结构

```
backend/heiman/
├── src/heiman/
│   ├── adapter/          # 设备适配器
│   ├── classifier/       # 事件分类器
│   ├── client/           # 海曼API客户端
│   ├── collector/        # 数据收集器
│   ├── config/           # 配置管理
│   ├── database/         # 数据库模块
│   ├── router/           # API路由
│   ├── rule/             # 规则引擎
│   ├── schema/           # 数据模型
│   └── main.py           # 应用入口
├── pyproject.toml
├── .env
└── README.md
```