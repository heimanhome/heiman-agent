# Heiman Connect SDK 依赖

## L1：它是什么

Heiman Connect SDK（`heimanconnect/`）是 Heiman Agent 访问海曼智能家居生态的底层库。它封装了 OAuth2 认证、海曼云 HTTP API、设备管理、传感器数据获取等核心能力，由海曼官方提供，以 Python wheel 形式分发。

**能力范围**

- **OAuth2 + 云端 API**：账号授权、设备列表、属性读写、动作触发、传感器数据获取
- **设备管理**：设备绑定/解绑、设备状态查询、设备信息获取
- **传感器数据**：烟雾、温湿度、一氧化碳、水浸等传感器数据的实时获取
- **事件订阅**：通过 MQTT 订阅设备事件，实时接收传感器状态变化
- **HTTP 客户端**：封装 HTTP 请求，统一错误处理和响应解析

---

## L2：我们怎么用

### 封装层

Heiman Agent 在 Heiman Connect SDK 之上有一层封装：`SensorDeviceAdapter`（`adapter/adapter_base.py`），对整个 Server 暴露统一的异步接口。Adapter 负责：

- token 生命周期管理（后台自动刷新）
- 内存缓存（设备列表、传感器数据）
- 设备状态维护（在线/离线）
- 传感器数据采集和转换

认证失败时，`SensorDeviceAdapter` 抛 `HeimanAuthException`（code=401）；调用失败时抛 `HeimanApiException`（code=500）。

详细使用方式见 [传感器监控](../02-features/sensor-monitoring.md)。

### 集成约束

- **OAuth 绑定要求**：所有 Cloud API 调用必须先完成海曼账号 OAuth2 授权（`heiman-cli account bind`）。未绑定时设备列表为空，感知无法启动。
- **网络依赖**：传感器数据获取依赖网络连接，网络断开时数据采集会失败，自动重试机制会在网络恢复后继续。
- **单进程约束**：SDK 部分子模块假设单进程运行，Heiman Agent 的 `workers=1` 约束正是为此而设。

### 已知限制

- 传感器数据更新频率依赖海曼云推送，最大同步间隔由 `SENSOR_SYNC_INTERVAL_SECONDS` 控制
- 设备在线判定依赖 SDK 内部状态，设备实际离线时状态可能未及时更新

### 出问题找谁

Heiman Connect SDK 由海曼官方团队维护。遇到 SDK 层问题（OAuth 接口变更、API 异常、数据获取失败）需向海曼技术支持反映。Heiman Agent 侧能做的是通过 `SensorDeviceAdapter` 封装层做隔离和降级。