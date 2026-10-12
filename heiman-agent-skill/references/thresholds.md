# 告警阈值与判定规则

## 一、分级与通用常量

来源：`ai/alert_analyzer.py:101-117`

| 常量 | 值 | 含义 |
|---|---|---|
| `_FREQUENT_ALERT_THRESHOLD` | 3 | 近期同类事件达到 3 次视为「频发」 |
| `_ANOMALY_HIGH` | 0.7 | ML 异常评分「高」线 |
| `_ANOMALY_MEDIUM` | 0.4 | ML 异常评分「中」线 |
| `_TEMP_DANGER` | 60.0 °C | 温度危险线（配合烟雾判火情） |
| `_TEMP_HIGH` | 45.0 °C | 温度高温线 |
| `_CO_DANGER` | 400 ppm | CO 危险线 |
| `_CO_HIGH` | 100 ppm | CO 高浓度线 |
| `_SMOKE_DANGER` | 500 ppm | 烟雾危险线 |
| `_SMOKE_HIGH` | 200 ppm | 烟雾高浓度线 |

告警内部使用四级：`critical` / `high` / `medium` / `low`；
对外事件级别枚举为 `info` / `warning` / `critical`（`schema/sensor.py:62-66`）。

规则默认冷却：`default_cooldown_minutes = 5`（`config/settings.py:45`）。

## 二、设备状态位判定（硬规则）

来源：`ai/anomaly_detector.py:177-219`、`classifier/event_classifier.py:27-39`

状态位为设备直报的硬信号，**优先级高于浓度判定**：

| 条件 | 判定 | 级别 |
|---|---|---|
| `gasState ∈ (1, 2)` 且设备为燃气 / CO 类 | 燃气泄漏报警 | `critical` |
| `waterState == 1` | 水浸报警 | `critical` |
| `tamperState == 1` | 防拆触发 | `warning` |
| `sensorLifeStatus == 1` | 传感器寿命到期 | `warning` |
| `battery < 20` 且状态正常 | 低电量事件 | — |

设备状态到事件的映射：`offline` → 离线事件 ｜ `alarm` → 告警事件 ｜
`warning` → 警告事件 ｜ `normal` → 正常事件。

## 三、一氧化碳（CO）

来源：`ai/alert_analyzer.py:429-510`

> **取值口径**：CO 浓度取自传感器对象的 `value`（`unit="ppm"`）；
> `gasState` 是**状态位**（0=正常, 1=报警, 2=故障），不是浓度——不要把 `1` 读成 `1 ppm`。
> 依据：`classifier/event_classifier.py`（用 `sensor_data.value` 作浓度）、
> `database/sensor_repo.py`（`gasState` 的 unit 为空）。

| 条件 | 级别 | 影响范围 |
|---|---|---|
| `co_ppm >= 400` | `critical` | building_wide |
| `100 <= co_ppm < 400` | `high` | building_wide |
| `co_ppm < 100` | `medium` | localized |

- **误报判定**：`co_ppm < 100` 且 ML 异常评分 `< 0.4` → 传感器可能受干扰
- **根因置信度**：`>=400` → 0.95 ｜ 异常评分 `>=0.7` → 0.85 ｜ 其余 → 0.6

## 四、烟雾

来源：`ai/alert_analyzer.py:284-403`

| 条件 | 级别 | 影响范围 |
|---|---|---|
| `smoke_ppm >= 500` **且** 温度 `>= 60 °C` | `critical`（疑似真实火情） | building_wide |
| ML 异常评分 `>= 0.7` 且非误报 | `high` | floor_wide |
| 误报 | `low` | localized |
| 其余 | `medium` | localized |

- **误报判定**：`smoke_ppm < 200` 且 ML 异常评分 `< 0.4`

## 五、水浸

来源：`ai/alert_analyzer.py:544-640`

| 条件 | 级别 | 影响范围 |
|---|---|---|
| ML 异常评分 `>= 0.7` | `high` | floor_wide |
| 误报 | `low` | localized |
| 其余 | `medium` | localized |

- **误报判定**：ML 异常评分 `< 0.4` **且** 电量 `> 50 %`
  （若 24h 内触发 `>= 3` 次，提示「可能是安装位置潮湿」）
- **交叉验证**：同房间存在其他水传感器时，置信度提升至 0.75

> 其余分析类型（防拆 L640-710、温度 L706、离线 L791、门磁 L854、人体移动 L941、通用 L1016）
> 的 `estimated_scope` **固定为 `localized`**，不随级别变化。

## 六、防拆

来源：`ai/alert_analyzer.py:640-710`

| 条件 | 级别 |
|---|---|
| ML 异常评分 `>= 0.7` 且非误报 | `high` |
| 行为识别为 `cleaning` / `maintenance` / `moving` | `low`（误报） |
| 其余 | `medium` |

## 七、设备离线与电池

来源：`ai/anomaly_detector.py:56-61,108`、`ai/alert_analyzer.py:805-825`

| 条件 | 判定 |
|---|---|
| 电量 `<= 20 %` | 触发「低电量」异常（`anomaly_detector.py:108`） |
| 电量 `<= 10 %` | 离线归因为「电量过低」，`medium` |
| 信号 `<= -90 dBm` | 离线归因为「信号极弱」，`medium` |
| ML 异常评分 `>= 0.7` | 离线归因为「可能被破坏 / 移除」，`high` |
| 其余离线 | 归因为「网络波动或设备休眠」，`low` |
| **离线阈值** | `offline_threshold_minutes = 60`（即 **60 分钟**） |

> 网关设备 `battery == -1` 表示市电供电，不参与电池判定。
> `rssi == -999` 表示无信号读数，按「未知」处理，不得判为弱信号。

## 八、环境异常线

来源：`ai/anomaly_detector.py:56-61`、`ai/anomaly_detector_v2.py:104-158`

| 通道 | 明显异常（obvious） | 环境异常线 |
|---|---|---|
| 温度 | `> 38 °C` 或 `< 8 °C` | `< 15 °C` 或 `> 35 °C` |
| 湿度 | `> 92 %` 或 `< 8 %` | `< 20 %` 或 `> 80 %` |
| 电量 | `< 10 %`（`< 5 %` 升级为紧急） | — |
| CO₂ | — | `> 1500 ppm` |
| PM2.5 | — | `> 75 μg/m³` |

综合异常判定：`if_score < -0.15`，或命中任一「明显异常」类型。

## 九、环境舒适度

来源：`ai/comfort_evaluator.py:66-88,280-285`

### 温度（基准 24 °C）

| 区间 | 等级 |
|---|---|
| 22–26 °C | excellent |
| 20–28 °C | good |
| 18–30 °C | fair |
| 其余 | poor |

### 湿度（基准 50 %）

| 区间 | 等级 |
|---|---|
| 40–60 % | excellent |
| 30–70 % | good |
| 20–80 % | fair |
| 其余 | poor |

### CO₂ / PM2.5 / 甲醛（HCHO）

| 通道 | excellent | good | fair | poor |
|---|---|---|---|---|
| CO₂（ppm） | ≤ 600 | ≤ 1000 | ≤ 1500 | ≤ 2000 |
| PM2.5（μg/m³） | ≤ 35 | ≤ 75 | ≤ 150 | ≤ 350 |
| HCHO（mg/m³） | ≤ 0.03 | ≤ 0.08 | ≤ 0.10 | ≤ 0.20 |

综合舒适度评分 `0–100`，等级划分：
`>= 85` excellent ｜ `>= 70` good ｜ `>= 40` fair ｜ `< 40` poor。

## 十、夜间判定

来源：`ai/anomaly_detector.py:256`

夜间 = 本地时间 `hour < 6` 或 `hour >= 22`，即 **22:00–06:00**。
门磁在该时段开启计为「夜间异常」。

## 十一、严重级别映射（输出用）

| 级别 | 触发来源 | 处理方式 |
|------|----------|----------|
| `critical` | 燃气 / 水浸状态位、烟雾危险 + 高温、CO ≥ 400 ppm | 立即通知，不等待用户请求 |
| `high` | CO 100–400 ppm、漏水（异常高分）、防拆（异常高分） | 汇总进报告，优先提示 |
| `medium` | 低浓度告警、电量过低离线、一般拆动 | 汇总进报告 |
| `low` | 误报类（安装位置潮湿、清洁触碰、网络波动） | 简述即可 |

> 机器值 `critical` / `high` / `medium` / `low` 与 `info` / `warning` / `critical`
> **一律不翻译**，展示文案按提问语言走映射（见 `SKILL.md`「第 3.5 步」）。

### 影响范围（`impact_assessment.estimated_scope`）

来源：`ai/alert_analyzer.py`（CO L452-466 ｜ 烟雾 L325-340 ｜ 水浸 L575-586 ｜ 其余固定 L398/509/627）

| 机器值 | 中文 | English | 出现场景 |
|---|---|---|---|
| `building_wide` | 整栋 | building-wide | CO ≥ 100 ppm；烟雾 critical |
| `floor_wide` | 整层 | floor-wide | 烟雾 high；水浸 high |
| `localized` | 局部 | localized | 其余全部情形 |

> 同为机器值，**一律不翻译**，展示文案按上表按语言切换。
> 注意：这是**定级结论**（写死在源代码里的字面量），不是按房间拓扑推算的结果；
> 同一条 `impact_assessment` 中真正按空间推算的是 `affected_rooms`（本房间 + 相邻房间）。

## 附录：与脚本常量的一致性

| 项 | 脚本常量 | 后端来源 | 状态 |
|---|---|---|---|
| CO 危险线 | `CO_DANGER = 400` | `alert_analyzer._CO_DANGER = 400` | ✅ 一致 |
| CO 高浓度线 | `CO_HIGH = 100` | `alert_analyzer._CO_HIGH = 100` | ✅ 一致 |
| 电量低 | `BATTERY_LOW = 20` | `anomaly_detector.battery_low_threshold = 20` | ✅ 一致 |
| 电量紧急 | `BATTERY_CRITICAL = 10` | `alert_analyzer` 离线归因 `battery <= 10` | ✅ 一致 |
| 离线阈值 | `OFFLINE_THRESHOLD_MINUTES = 60` | `anomaly_detector.offline_threshold_minutes = 60` | ✅ 一致 |
| CO 浓度取值 | 读 `value`(unit=ppm) | `event_classifier` 用 `sensor_data.value` | ✅ 一致 |
| 燃气状态位 | 读 `gasState`（0/1/2） | `anomaly_detector.py:177` `gasState in (1, 2)` | ✅ 一致 |
| 历史窗口参数 | 换算为 `start_time` + `limit` | `router/sensor_router.py` 无 `hours`，只有 `start_time`/`end_time`/`limit` | ✅ 一致 |

> - 脚本的 CO 判定为两档：`>=400` critical ｜ `>=100` warning，分别对应后端 `critical` / `high`。
>   后端更低的 `medium` 档（CO 已触发但 `<100`）仅出现在其后端告警分析链路内，脚本不建模。
> - 脚本的离线判定直接采用后端返回的 `status` 字段；`OFFLINE_THRESHOLD_MINUTES` 为口径对齐保留常量，当前未被脚本引用。
> - 电量档位的边界符号脚本用 `<`（`<20` warning / `<10` critical）；后端本身并存 `<=20`（`anomaly_detector`）
>   与 `<20`（`event_classifier`）两种写法，故此处以**数值一致**为准，不追求边界符号一致。

