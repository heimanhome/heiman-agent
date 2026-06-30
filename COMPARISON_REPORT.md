# Heiman-Agent 与 Xiaomi-Miloco 项目对比分析报告

## 一、项目概述对比

### 1.1 项目定位

| 项目 | 定位 | 核心功能 | 技术栈 |
|------|------|----------|--------|
| **heiman-agent** | 海曼传感器智能Agent | 智能家居安全监控，专注于传感器数据采集与告警 | Python + FastAPI + SQLite + HTTPX |
| **xiaomi-miloco** | 小米智能家居感知和自动化服务器 | 全功能智能家居平台，包含感知引擎、身份识别、自动化规则等 | Python + FastAPI + SQLite + 小米IoT SDK |

### 1.2 架构复杂度对比

- **heiman-agent**: 轻量级架构，约15个核心模块，专注于传感器监控
- **xiaomi-miloco**: 复杂架构，约50+核心模块，包含感知引擎、身份识别、任务管理等高级功能

---

## 二、目录结构对比

### 2.1 heiman-agent 目录结构

```
heiman-agent/
├── backend/heiman/
│   ├── src/heiman/
│   │   ├── adapter/          # 设备适配器（传感器适配）
│   │   ├── classifier/       # 事件分类器
│   │   ├── client/           # 海曼API客户端
│   │   ├── collector/        # 数据收集器
│   │   ├── config/           # 配置管理
│   │   ├── database/         # 数据库模块（8个repo）
│   │   ├── router/           # API路由（12个router）
│   │   ├── rule/             # 规则引擎
│   │   ├── schema/           # 数据模型（5个schema）
│   │   ├── service/          # 服务层（3个service）
│   │   ├── middleware/       # 中间件
│   │   ├── node_monitor/     # 节点监控
│   │   ├── main.py           # 应用入口
│   │   ├── manager.py        # 服务管理器
│   │   └── mqtt_service.py   # MQTT服务
│   ├── static/               # 前端静态文件
│   ├── tests/                # 测试文件
│   └── pyproject.toml        # 项目配置
├── cli/                      # 命令行工具
├── knowledge/                # 知识库文档
├── plugins/                  # 插件系统
└── scripts/                  # 安装脚本
```

### 2.2 xiaomi-miloco 目录结构

```
xiaomi-miloco/
├── backend/miloco/
│   ├── src/miloco/
│   │   ├── admin/            # 系统管理（状态检查、配置管理）
│   │   ├── config/           # 配置管理（含schema.json）
│   │   ├── database/         # 数据库模块（9个repo + DAO）
│   │   ├── dispatch/         # Agent调度器
│   │   ├── home_profile/     # 家庭档案管理
│   │   ├── middleware/       # 中间件
│   │   ├── miot/             # 小米IoT集成（摄像头、设备控制）
│   │   ├── node_monitor/     # 节点监控（含内存分析）
│   │   ├── observability/    # 可观测性（性能监控、token统计）
│   │   ├── perception/       # 感知引擎（核心模块）
│   │   │   ├── collect/      # 数据采集（摄像头适配）
│   │   │   ├── engine/       # 感知引擎
│   │   │   │   ├── gate/     # 事件门控
│   │   │   │   ├── identity/ # 身份识别引擎
│   │   │   │   ├── input/    # 视频输入处理
│   │   │   │   └── omni/     # Omni感知模块
│   │   │   ├── inference/    # 推理引擎
│   │   │   └── models/       # ONNX模型文件
│   │   ├── person/           # 人员管理（含身份样本）
│   │   ├── rule/             # 规则引擎（含终止评估）
│   │   ├── schema/           # 数据模型
│   │   ├── task/             # 任务管理
│   │   ├── task_record/      # 任务记录管理
│   │   ├── utils/            # 工具函数
│   │   ├── main.py           # 应用入口
│   │   └── manager.py        # 服务管理器
│   ├── tests/                # 测试文件（含感知引擎测试）
│   └── pyproject.toml        # 项目配置
├── assets/                   # 资源文件（图片、文档）
├── .agents/                  # AI代理配置
├── .ci/                      # CI配置
├── .github/                  # GitHub配置
└── README.md                 # 项目文档
```

---

## 三、功能模块对比

### 3.1 核心功能对比表

| 功能模块 | heiman-agent | xiaomi-miloco | 状态 |
|----------|--------------|---------------|------|
| **传感器监控** | ✅ 完整实现 | ❌ 无此功能 | heiman特有 |
| **事件分类** | ✅ 简单实现 | ✅ 复杂实现（有意义事件） | miloco更完善 |
| **规则引擎** | ✅ 基础实现 | ✅ 完整实现（含终止评估） | miloco更完善 |
| **摄像头管理** | ❌ 无此功能 | ✅ 完整实现（WebSocket流） | heiman缺失 |
| **身份识别** | ❌ 无此功能 | ✅ 完整实现（Tier A/C样本） | heiman缺失 |
| **陌生人池** | ❌ 无此功能 | ✅ 完整实现 | heiman缺失 |
| **家庭档案** | ✅ 基础实现 | ✅ 完整实现（Markdown渲染） | miloco更完善 |
| **人员管理** | ✅ 基础CRUD | ✅ 完整实现（含样本管理） | miloco更完善 |
| **任务管理** | ✅ 基础实现 | ✅ 完整实现（含记录、进度） | miloco更完善 |
| **任务记录** | ✅ 基础实现 | ✅ 完整实现（含派生量计算） | miloco更完善 |
| **设备控制** | ❌ 无此功能 | ✅ 完整实现（小米IoT） | heiman缺失 |
| **场景触发** | ❌ 无此功能 | ✅ 完整实现 | heiman缺失 |
| **可观测性** | ✅ 基础实现 | ✅ 完整实现（性能监控、token统计） | miloco更完善 |
| **系统管理** | ❌ 无此功能 | ✅ 完整实现（状态检查、配置管理） | heiman缺失 |
| **感知引擎** | ❌ 无此功能 | ✅ 完整实现（实时感知） | heiman缺失 |
| **Omni感知** | ❌ 无此功能 | ✅ 完整实现（多模态感知） | heiman缺失 |
| **视频处理** | ❌ 无此功能 | ✅ 完整实现（视频分割、帧提取） | heiman缺失 |
| **音频处理** | ❌ 无此功能 | ✅ 完整实现（音频流） | heiman缺失 |
| **WebSocket** | ❌ 无此功能 | ✅ 完整实现（视频/音频流） | heiman缺失 |
| **SSE推送** | ❌ 无此功能 | ✅ 完整实现（事件推送） | heiman缺失 |
| **插件系统** | ✅ 完整实现 | ❌ 无此功能 | heiman特有 |
| **CLI工具** | ✅ 完整实现 | ✅ 完整实现 | 两者都有 |
| **知识库** | ✅ 完整实现 | ❌ 无此功能 | heiman特有 |

---

## 四、API设计对比

### 4.1 heiman-agent API端点

#### 传感器相关
- `GET /api/sensors` - 获取所有传感器
- `GET /api/sensors/{did}` - 获取单个传感器
- `POST /api/sensors/data` - 推送传感器数据
- `GET /api/sensors/{did}/history` - 获取传感器历史数据

#### 事件相关
- `GET /api/events` - 获取事件列表
- `GET /api/events/{event_id}` - 获取单个事件
- `POST /api/events/{event_id}/acknowledge` - 确认事件

#### 规则相关
- `GET /api/rules` - 获取规则列表
- `POST /api/rules` - 创建规则
- `PUT /api/rules/{rule_id}` - 更新规则
- `DELETE /api/rules/{rule_id}` - 删除规则
- `POST /api/rules/{rule_id}/conditions` - 添加条件
- `POST /api/rules/{rule_id}/actions` - 添加动作

#### 其他
- 家庭管理、人员管理、任务管理等基础CRUD接口

### 4.2 xiaomi-miloco API端点（关键新增）

#### MIoT集成（小米IoT）
- `POST /api/miot/authorize` - 小米账号授权
- `GET /api/miot/status` - 检查绑定状态
- `POST /api/miot/bind` - 绑定小米账号
- `POST /api/miot/unbind` - 解绑小米账号
- `GET /api/miot/camera_list` - 获取摄像头列表
- `GET /api/miot/device_list` - 获取设备列表
- `POST /api/miot/devices/{did}/control` - 控制设备
- `GET /api/miot/devices/{did}/status` - 获取设备状态
- `POST /api/miot/scenes/{scene_id}/trigger` - 触发场景
- `WebSocket /api/miot/ws/video_stream` - 视频流WebSocket
- `WebSocket /api/miot/ws/audio_stream` - 音频流WebSocket

#### 感知引擎
- `GET /api/perception/engine/status` - 获取引擎状态
- `POST /api/perception/engine/start` - 启动感知引擎
- `POST /api/perception/engine/stop` - 停止感知引擎
- `POST /api/perception/perceive` - 主动感知查询
- `GET /api/perception/logs` - 查询感知日志
- `GET /api/perception/devices` - 列出感知设备

#### 有意义事件
- `GET /api/events` - 列出有意义事件
- `GET /api/events/{event_id}/clip/{device_id}` - 获取事件视频片段
- `GET /api/events/stream` - SSE实时推送事件

#### 身份识别与样本管理
- `POST /api/identity/persons/{person_id}/samples` - 登记Tier A样本
- `POST /api/identity/persons/{person_id}/samples/batch` - 批量登记样本
- `POST /api/identity/persons/{person_id}/extract` - 从图片/视频抽取样本
- `GET /api/identity/persons/{person_id}/samples` - 列出样本文件
- `GET /api/identity/persons/{person_id}/sample/{tier}/{filename}` - 读取样本图
- `GET /api/identity/persons/{person_id}/samples/montage` - 样本拼接图
- `POST /api/identity/register/preview` - 注册预览（两步走第1步）
- `POST /api/identity/register/commit` - 注册提交（两步走第2步）
- `POST /api/identity/persons/merge` - 合并人员
- `POST /api/identity/persons/{person_id}/split` - 拆分人员

#### 陌生人池（Tier U）
- `GET /api/identity/pool/status` - 陌生人池状态
- `GET /api/identity/pool/fetch` - 获取注册候选
- `POST /api/identity/pool/dump` - 池快照（调试）
- `POST /api/identity/pool/cluster-split` - 拆分误合并cluster
- `POST /api/identity/register/from-cluster` - 从cluster注册

#### 家庭档案
- `GET /api/home-profile/entries` - 列出档案条目
- `POST /api/home-profile/candidates:write` - 写候选条目
- `POST /api/home-profile/profile:write` - 写正式条目
- `POST /api/home-profile/commit` - 提交档案
- `POST /api/home-profile/subject:reassign` - 重新分配主体
- `GET /api/home-profile/rendered` - 获取渲染后的档案（Markdown）
- `POST /api/home-profile/import` - 导入历史数据
- `POST /api/home-profile/reset` - 重置档案

#### 任务记录管理
- `POST /api/tasks/{task_id}/link` - 添加cron链接
- `POST /api/tasks/{task_id}/record` - 初始化记录
- `GET /api/tasks/{task_id}/record` - 获取活跃记录
- `PATCH /api/tasks/{task_id}/record` - 更新记录
- `POST /api/tasks/{task_id}/record/compute` - 计算派生量
- `GET /api/tasks/{task_id}/record/archives` - 列出归档记录
- `POST /api/tasks/{task_id}/record/progress/increment` - 增加进度
- `POST /api/tasks/{task_id}/record/event/append` - 追加事件
- `POST /api/tasks/{task_id}/record/session/start` - 开始会话
- `POST /api/tasks/{task_id}/record/session/end` - 结束会话

#### Admin管理
- `GET /api/admin/status` - 系统状态检查
- `GET /api/admin/token-usage` - Token用量统计
- `GET /api/admin/token-usage/daily` - 每日聚合统计
- `GET /api/admin/token-usage/buckets` - 时间桶聚合统计
- `POST /api/admin/token-usage/clear` - 清空Token用量
- `GET /api/admin/debug` - Debug开关状态
- `POST /api/admin/debug` - 设置Debug开关
- `POST /api/admin/debug/log-pack` - 打包日志
- `GET /api/admin/omni-config` - 读取Omni配置
- `PUT /api/admin/omni-config` - 保存Omni配置
- `POST /api/admin/omni-config/activate` - 切换配置
- `POST /api/admin/omni-config/delete` - 删除配置
- `POST /api/admin/omni-config/test` - 测试配置连通性
- `POST /api/admin/omni-config/models` - 拉取可用模型列表

#### 可观测性
- `GET /api/observability/metrics` - 性能指标
- `GET /api/observability/traces` - 调用链追踪
- `GET /api/observability/events` - 事件追踪
- `GET /api/observability/agent-runs` - Agent运行记录

---

## 五、数据模型对比

### 5.1 heiman-agent 数据模型

#### 数据库仓库（8个）
- `connector.py` - 数据库连接器
- `event_repo.py` - 事件仓库
- `kv_repo.py` - KV仓库
- `log_repo.py` - 日志仓库
- `model_repo.py` - 模型仓库
- `person_repo.py` - 人员仓库
- `rule_repo.py` - 规则仓库
- `sensor_repo.py` - 传感器仓库
- `task_repo.py` - 任务仓库
- `task_record_repo.py` - 任务记录仓库

#### Schema模型（5个）
- `observability.py` - 可观测性模型
- `person.py` - 人员模型
- `rule.py` - 规则模型
- `sensor.py` - 传感器模型
- `task.py` - 任务模型

### 5.2 xiaomi-miloco 数据模型

#### 数据库仓库（9个 + DAO）
- `connector.py` - 数据库连接器
- `kv_repo.py` - KV仓库
- `meaningful_events_dao.py` - 有意义事件DAO
- `perception_repo.py` - 感知仓库
- `person_repo.py` - 人员仓库
- `rule_repo.py` - 规则仓库
- `task_repo.py` - 任务仓库
- `task_record_repo.py` - 任务记录仓库（含rollover）
- `token_usage_repo.py` - Token用量仓库

#### Schema模型（多个）
- `common_schema.py` - 公共模型
- 各模块独立schema文件（person、rule、task、perception等）

---

## 六、缺失功能清单

### 6.1 高优先级缺失功能（建议优先实现）

#### 1. 摄像头管理与视频流处理
- **功能名称**: 摄像头管理 + WebSocket视频流
- **在 xiaomi-miloco 中的位置**: 
  - `/backend/miloco/src/miloco/miot/router.py` (摄像头管理API)
  - `/backend/miloco/src/miloco/miot/ws.py` (WebSocket流管理)
  - `/backend/miloco/src/miloco/miot/camera_handler.py` (摄像头处理)
- **功能描述**: 
  - 摄像头列表管理、在线状态检查
  - WebSocket实时视频流推送
  - 视频片段录制（mp4格式）
  - 首帧看门狗机制
- **优先级**: **高**
- **实现建议**: 
  1. 先实现摄像头列表管理和在线状态检查
  2. 实现WebSocket视频流推送（参考miot/ws.py）
  3. 添加视频片段录制功能
  4. 实现首帧看门狗机制防止连接卡死

#### 2. 身份识别引擎
- **功能名称**: 身份识别 + 样本管理
- **在 xiaomi-miloco 中的位置**: 
  - `/backend/miloco/src/miloco/perception/engine/identity/` (整个identity目录)
  - `/backend/miloco/src/miloco/person/router.py` (人员管理API)
- **功能描述**: 
  - Tier A样本登记（用户上传）
  - Tier C样本累积（系统自动）
  - 样本提取（从图片/视频）
  - 样本选择算法（pHash + ReID）
  - 人员合并/拆分功能
  - 样本拼接图生成
- **优先级**: **高**
- **实现建议**: 
  1. 先实现基础的Tier A样本登记（单图上传）
  2. 实现样本提取功能（从图片）
  3. 添加样本选择算法（pHash去重）
  4. 实现批量登记和样本拼接图
  5. 最后实现人员合并/拆分功能

#### 3. 陌生人池（Tier U）
- **功能名称**: 陌生人池管理
- **在 xiaomi-miloco 中的位置**: 
  - `/backend/miloco/src/miloco/perception/engine/identity/tier_u.py`
  - `/backend/miloco/src/miloco/person/router.py` (pool相关API)
- **功能描述**: 
  - 陌生人cluster管理
  - cluster候选提取
  - cluster拆分功能
  - 从cluster注册人员
- **优先级**: **高**
- **实现建议**: 
  1. 先实现陌生人池基础结构（cluster管理）
  2. 实现cluster候选提取功能
  3. 添加cluster拆分功能
  4. 实现从cluster注册人员的流程

#### 4. 感知引擎核心
- **功能名称**: 实时感知引擎
- **在 xiaomi-miloco 中的位置**: 
  - `/backend/miloco/src/miloco/perception/` (整个perception目录)
  - `/backend/miloco/src/miloco/perception/engine/` (引擎核心)
- **功能描述**: 
  - 实时感知引擎启动/停止
  - 事件门控（audio/visual gate）
  - Omni感知模块（多模态）
  - 感知日志管理
  - 有意义事件生成
- **优先级**: **高**
- **实现建议**: 
  1. 先实现感知引擎基础框架（启动/停止）
  2. 实现事件门控机制
  3. 添加Omni感知模块（需要AI模型集成）
  4. 实现有意义事件生成和持久化
  5. 最后实现感知日志管理

#### 5. 小米IoT集成
- **功能名称**: 小米IoT设备控制
- **在 xiaomi-miloco 中的位置**: 
  - `/backend/miloco/src/miloco/miot/` (整个miot目录)
  - `/backend/miloco/src/miloco/miot/client.py` (MIoT客户端)
  - `/backend/miloco/src/miloco/miot/service.py` (MIoT服务)
- **功能描述**: 
  - 小米账号OAuth授权
  - 设备列表获取
  - 设备属性控制
  - 场景触发
  - 设备状态查询
  - MIPS订阅（实时事件）
- **优先级**: **高**
- **实现建议**: 
  1. 先实现小米账号OAuth授权流程
  2. 实现设备列表获取和状态查询
  3. 添加设备属性控制功能
  4. 实现场景触发功能
  5. 最后实现MIPS订阅（需要小米SDK）

### 6.2 中优先级缺失功能

#### 6. 家庭档案增强
- **功能名称**: 家庭档案Markdown渲染
- **在 xiaomi-miloco 中的位置**: 
  - `/backend/miloco/src/miloco/home_profile/` (整个目录)
  - `/backend/miloco/src/miloco/home_profile/render.py` (渲染逻辑)
- **功能描述**: 
  - 档案条目管理（候选/正式）
  - Markdown渲染
  - 主体重新分配
  - 档案导入/重置
- **优先级**: **中**
- **实现建议**: 
  1. 扩展现有家庭管理功能
  2. 实现候选/正式条目分离
  3. 添加Markdown渲染功能
  4. 实现档案导入/重置

#### 7. 任务记录增强
- **功能名称**: 任务记录派生量计算
- **在 xiaomi-miloco 中的位置**: 
  - `/backend/miloco/src/miloco/task_record/` (整个目录)
  - `/backend/miloco/src/miloco/task_record/rollover.py` (日滚动)
- **功能描述**: 
  - 派生量计算（progress/duration/event）
  - 日滚动机制
  - 归档记录管理
  - 跨窗口聚合
- **优先级**: **中**
- **实现建议**: 
  1. 扩展现有任务记录功能
  2. 实现派生量计算逻辑
  3. 添加日滚动机制
  4. 实现归档记录管理

#### 8. 可观测性增强
- **功能名称**: 性能监控 + Token统计
- **在 xiaomi-miloco 中的位置**: 
  - `/backend/miloco/src/miloco/observability/` (整个目录)
  - `/backend/miloco/src/miloco/admin/router.py` (token统计API)
- **功能描述**: 
  - 性能指标采集
  - Token用量统计
  - Agent运行记录
  - 调用链追踪
  - 时间桶聚合
- **优先级**: **中**
- **实现建议**: 
  1. 扩展现有可观测性功能
  2. 实现Token用量统计
  3. 添加性能指标采集
  4. 实现调用链追踪

#### 9. Admin管理模块
- **功能名称**: 系统管理 + 配置管理
- **在 xiaomi-miloco 中的位置**: 
  - `/backend/miloco/src/miloco/admin/router.py`
  - `/backend/miloco/src/miloco/admin/log_pack.py`
- **功能描述**: 
  - 系统状态检查
  - Omni模型配置管理
  - Debug开关管理
  - 日志打包功能
  - 配置测试连通性
- **优先级**: **中**
- **实现建议**: 
  1. 创建admin模块目录
  2. 实现系统状态检查API
  3. 添加Omni配置管理
  4. 实现Debug开关和日志打包

#### 10. SSE实时推送
- **功能名称**: SSE事件推送
- **在 xiaomi-miloco 中的位置**: 
  - `/backend/miloco/src/miloco/perception/events_router.py`
- **功能描述**: 
  - SSE实时推送有意义事件
  - 支持query token认证
  - 客户端断开清理
- **优先级**: **中**
- **实现建议**: 
  1. 添加sse-starlette依赖
  2. 实现SSE事件推送端点
  3. 添加query token认证支持

### 6.3 低优先级缺失功能

#### 11. 视频处理增强
- **功能名称**: 视频分割 + 帧提取
- **在 xiaomi-miloco 中的位置**: 
  - `/backend/miloco/src/miloco/perception/engine/input/video_splitter.py`
- **功能描述**: 
  - 视频帧采样
  - 视频分割处理
- **优先级**: **低**
- **实现建议**: 
  1. 添加视频处理依赖（cv2）
  2. 实现视频帧采样功能

#### 12. 音频处理
- **功能名称**: 音频流处理
- **在 xiaomi-miloco 中的位置**: 
  - `/backend/miloco/src/miloco/miot/ws.py` (audio_stream_manager)
- **功能描述**: 
  - WebSocket音频流推送
  - 音频处理
- **优先级**: **低**
- **实现建议**: 
  1. 实现音频WebSocket流
  2. 添加音频处理逻辑

#### 13. Agent调度器
- **功能名称**: Agent事件调度
- **在 xiaomi-miloco 中的位置**: 
  - `/backend/miloco/src/miloco/dispatch/dispatcher.py`
- **功能描述**: 
  - Agent事件调度
  - Agent运行管理
- **优先级**: **低**
- **实现建议**: 
  1. 实现Agent调度器基础框架
  2. 添加事件分发逻辑

#### 14. 终止评估器
- **功能名称**: 规则终止评估
- **在 xiaomi-miloco 中的位置**: 
  - `/backend/miloco/src/miloco/rule/terminate_evaluator.py`
- **功能描述**: 
  - 规则终止条件评估
  - 任务完成检测
- **优先级**: **低**
- **实现建议**: 
  1. 扩展规则引擎
  2. 实现终止评估逻辑

---

## 七、实现路径建议

### 7.1 第一阶段：基础功能完善（1-2个月）

**目标**: 实现核心缺失功能，使heiman-agent具备基本的智能家居感知能力

**优先实现**:
1. 摄像头管理基础功能（列表、状态）
2. 身份识别基础功能（Tier A样本登记）
3. 小米IoT基础集成（授权、设备列表）
4. Admin管理模块（系统状态）

### 7.2 第二阶段：感知引擎集成（2-3个月）

**目标**: 实现感知引擎核心，使heiman-agent具备实时感知能力

**优先实现**:
1. 感知引擎框架（启动/停止）
2. WebSocket视频流推送
3. 身份识别增强（样本提取、选择算法）
4. 陌生人池基础功能

### 7.3 第三阶段：高级功能集成（3-4个月）

**目标**: 实现高级功能，使heiman-agent具备完整的智能家居平台能力

**优先实现**:
1. Omni感知模块（AI模型集成）
2. 有意义事件生成
3. SSE实时推送
4. 家庭档案增强
5. 任务记录增强

### 7.4 第四阶段：优化与完善（持续）

**目标**: 优化性能，完善细节功能

**优先实现**:
1. 可观测性增强
2. 视频处理增强
3. 音频处理
4. Agent调度器
5. 终止评估器

---

## 八、技术依赖对比

### 8.1 heiman-agent 主要依赖
- FastAPI（Web框架）
- SQLite（数据库）
- HTTPX（HTTP客户端）
- MQTT（消息队列）
- 基础Python库

### 8.2 xiaomi-miloco 主要依赖（新增）
- sse-starlette（SSE推送）
- cv2（视频处理）
- numpy（数值计算）
- ONNX Runtime（模型推理）
- 小米IoT SDK（设备集成）
- pHash（图像哈希）
- DeepSORT（目标跟踪）
- HumanReID（人体重识别）

---

## 九、总结

### 9.1 关键差异总结

1. **功能范围**: heiman-agent专注于传感器监控，xiaomi-miloco是全功能智能家居平台
2. **感知能力**: heiman-agent无感知引擎，xiaomi-miloco有完整的实时感知系统
3. **身份识别**: heiman-agent无身份识别功能，xiaomi-miloco有完整的身份管理系统
4. **IoT集成**: heiman-agent仅支持海曼传感器，xiaomi-miloco支持小米IoT生态
5. **视频处理**: heiman-agent无视频处理能力，xiaomi-miloco有完整的视频流处理系统
6. **架构复杂度**: heiman-agent轻量级，xiaomi-miloco复杂多模块

### 9.2 实现建议总结

**高优先级功能**（建议优先实现）:
1. 摄像头管理与WebSocket视频流
2. 身份识别引擎
3. 陌生人池管理
4. 感知引擎核心
5. 小米IoT集成

**中优先级功能**（建议后续实现）:
1. 家庭档案增强
2. 任务记录增强
3. 可观测性增强
4. Admin管理模块
5. SSE实时推送

**低优先级功能**（可选实现）:
1. 视频处理增强
2. 音频处理
3. Agent调度器
4. 终止评估器

### 9.3 技术挑战

1. **AI模型集成**: Omni感知需要集成AI模型（需要API Key和模型配置）
2. **小米IoT SDK**: 需要小米IoT SDK集成（可能需要授权）
3. **视频处理**: 需要视频处理技术栈（cv2、ONNX等）
4. **实时性能**: WebSocket和SSE需要高性能实时处理
5. **身份识别算法**: 需要实现复杂的身份识别算法（pHash、ReID等）

---

## 十、附录

### 10.1 文件路径参考

**heiman-agent 关键文件**:
- 主入口: `/backend/heiman/src/heiman/main.py`
- 管理器: `/backend/heiman/src/heiman/manager.py`
- 传感器路由: `/backend/heiman/src/heiman/router/sensor_router.py`
- 事件路由: `/backend/heiman/src/heiman/router/event_router.py`
- 规则路由: `/backend/heiman/src/heiman/router/rule_router.py`

**xiaomi-miloco 关键文件**:
- 主入口: `/backend/miloco/src/miloco/main.py`
- 管理器: `/backend/miloco/src/miloco/manager.py`
- MIoT路由: `/backend/miloco/src/miloco/miot/router.py`
- 感知路由: `/backend/miloco/src/miloco/perception/router.py`
- 身份路由: `/backend/miloco/src/miloco/person/router.py`
- Admin路由: `/backend/miloco/src/miloco/admin/router.py`

### 10.2 技术栈对比表

| 技术栈 | heiman-agent | xiaomi-miloco |
|--------|--------------|---------------|
| Web框架 | FastAPI | FastAPI |
| 数据库 | SQLite | SQLite |
| HTTP客户端 | HTTPX | HTTPX + 小米SDK |
| 视频处理 | 无 | cv2 + ONNX |
| 音频处理 | 无 | 有 |
| AI模型 | 无 | ONNX Runtime |
| SSE推送 | 无 | sse-starlette |
| WebSocket | 无 | 有 |
| 消息队列 | MQTT | MQTT + MIPS |
| 身份识别 | 无 | pHash + ReID + DeepSORT |

---

**报告生成时间**: 2026-06-24  
**分析范围**: heiman-agent vs xiaomi-miloco 全项目对比  
**报告版本**: v1.0