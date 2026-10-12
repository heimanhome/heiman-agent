# 海曼设备数据模型

## 设备类型枚举（`sensor_type` / `type`）

`GET /api/sensors` 与 `GET /api/devices` 返回的 `sensor_type` / `type` 字段取值：

| 取值 | 中文 | 关键属性 | 状态语义 |
|------|------|----------|----------|
| `smoke` | 烟雾报警器 | `smokeState`, `temperature`, `battery` | 0=正常, 1=报警, 2=故障 |
| `co` | 一氧化碳报警器 | `value`（unit=`ppm`，浓度）, `gasState`（状态位）, `battery` | 浓度看 `value`；`gasState` 0=正常, 1=报警, 2=故障 |
| `temperature` | 温感 / 温湿度探测器 | `temperature`, `humidity` | 温度 °C；湿度 %（温感机型 `humidity` 为 null） |
| `plug` | 门磁探测器 | `contactState`, `tamperState`, `switchState` | 0=关门, 1=开门；`tamperState` 1=防拆 |
| `water` | 水浸传感器 | `waterState`, `battery` | 0=正常, 1=报警, 2=故障 |
| `gateway` | 无线级联网关 | — | 子设备的父节点，`parentId` 指向它 |

其他可能取值：`motion`（人体移动，`motionState`）、`switch`（开关类）。

## 通用字段（传感器对象）

| 字段 | 说明 |
|------|------|
| `did` | 设备唯一 ID（报告中需脱敏） |
| `name` | 设备名称，通常含房间信息 |
| `sensor_type` | 设备类型，见上表 |
| `product_id` | 产品 ID |
| `value` | 主测量值 |
| `unit` | 单位 |
| `status` | 传感器状态。实测取值：`normal`（正常）、`alarm`（告警）、`offline`（离线）。注意 `GET /api/devices` 的 `status` 用的是另一套：`online` / `offline`。两处不一致时以 `/api/sensors` 为准判断告警 |
| `battery` | 电量百分比；`-1` 表示不适用（如网关） |
| `rssi` / `signalLevel` | 信号强度；`-999` 表示无信号 |
| `room_id` / `room_name` | 房间（可能为 `"None"` 字符串或 null，需容错） |
| `home_id` | 所属家庭 |
| `timestamp` | 数据时间戳 ISO8601 |

## 各类型专有属性

| 属性 | 类型 | 适用设备 | 说明 |
|------|------|----------|------|
| `smokeState` | int | smoke | 烟雾状态 0/1/2 |
| `gasState` | int | co | 燃气/CO 状态位 0=正常, 1=报警, 2=故障 |
| `value` / `unit` | float / str | co 及环境类 | 主测量值；CO 的浓度即 `value`（`unit="ppm"`） |
| `waterState` | int | water | 水浸状态 0/1/2 |
| `contactState` | int | plug(门磁) | 0=关门, 1=开门 |
| `tamperState` | int | 多数 | 0=正常, 1=防拆告警 |
| `switchState` | int | 开关/门磁 | 开关状态 |
| `motionState` | int | motion | 人体移动 |
| `temperature` | float | smoke / temperature | 温度 °C |
| `humidity` | float | temperature(HT 机型) | 湿度 % |
| `sensorLifeStatus` | int/null | 部分 | 传感器寿命状态 |
| `alarmState` | int/null | 部分 | 通用告警位 |
| `co2` / `pm25` / `pm10` / `hcho` | float/null | 环境类 | 空气质量 |

> 未采到的字段返回 `null`，不要当作 0 处理。

> **门磁特别注意**：实测门磁探测器（HS2DS-R）可能出现 `value=2`、`status="alarm"`，
> 但 `contactState=0`（关门）、`tamperState=0`。此时 `status="alarm"` 来自 `value` 枚举，
> **不等于真实告警**。判定门窗开合请以 `contactState` 为准，并结合 `tamperState` 复核后再定级。

> **电量字段以哪个为准**：`GET /api/devices/{id}` 顶层 `battery` 可能不是真实电量（实测一台真实电量 `53%`
> 的门磁，此处仍返回 `100`，疑似未接线的默认值/占位值），
> 与 `properties.BatteryPercentage` 不一致（实测同一门磁为 `53`）。判断电量请以 `/api/sensors`
> 的 `battery` 或 `properties.BatteryPercentage` 为准，不要用 `/api/devices/{id}` 的顶层 `battery`。

> **`properties` 与 `deriveMetadata`**：`GET /api/devices/{id}` 的 `properties` 为快照值（字符串类型，
> 如 `"0"`）；`deriveMetadata[]` 为各属性的变更记录，每项含 `property` / `value` / `timestamp`（**毫秒**），
> 可用于推算属性最后变更时间。取值时注意 `properties` 里是字符串、`/api/sensors` 里是 int，比较前先归一化。

> **历史数据可能为空**：门磁等**事件驱动**设备（仅在开合/防拆变化时上报）调
> `GET /api/sensors/{did}/history?start_time=<now-24h>&limit=1000` 可能返回 `[]`，这是正常的，不代表服务异常。
> 只有周期性上报的传感器（温湿度、烟雾、CO）才有连续历史曲线。

## 设备层级

网关（`type=gateway`）是子设备的父节点：

- 网关自身 `parentId` 为 `null`；
- 子设备（门磁、烟雾、温感、CO、水浸等）的 `parentId` = 网关设备 ID；
- 网关 `battery` 为 `-1`，属正常，不要报低电量。

判断"设备离线"时，先看自身 `status`；网关离线通常意味着其下所有子设备也失联。

## 家庭 / 房间 / 成员

| 接口 | 主要字段 |
|------|----------|
| `GET /api/homes` | `id`, `name`, `address`, `members`, `devices`, `roomCount`, `memberCount` |
| `GET /api/rooms` | `id`, `name`, `homeId` |
| `GET /api/identity/persons` | `id`, `name`, `role`, `role_type`, `is_home_root`, `home_name`, `head_img_url` |

`GET /api/identity/persons` 的人员来自海曼云端家庭成员；`POST /api/identity/persons/sync` 可重新同步。

## 事件对象

| 字段 | 说明 |
|------|------|
| `id` | 事件 ID |
| `level` / `severity` | `critical` / `warning` / `info` |
| `type` | 事件类型，如 `SmokeAlarm`、`LowBattery` |
| `device_id` / `device_name` | 关联设备 |
| `created_at` | 发生时间 |
| `acknowledged` | 是否已确认 |

`GET /api/events/stats` 返回按级别/类型的聚合计数。
