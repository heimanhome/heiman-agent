---
name: heiman-perception
description: 调用传感器获取环境数据、查看摄像头画面、或回顾近期事件来判断——在干嘛、有什么动静、是否有人说话/吵闹、刚才/最近发生了什么；通过传感器数据核实设备的开关状态（如开着/关着、亮着/灭着），尤其在拿不到设备上报状态时。读不出画面看不见的具体数值（温度、湿度、音量等）。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-perception

感知查询与事件分析。

## 何时激活

| 意图 | 用户说了类似… |
| ---- | ------------- |
| **check_activity** | "家里有人吗" "谁在家" "客厅在干嘛" |
| **review_event** | "刚才发生了什么" "看看最近的记录" "回顾一下" |
| **verify_status** | "灯开着吗" "门关了吗" "窗户关了吗" |
| **detect_anomaly** | "有异常吗" "有没有动静" "出什么事了" |

## 核心工作流

### 活动检测

```bash
# 检测指定房间活动
heiman-cli perception activity --room <room>

# 检测全屋活动
heiman-cli perception activity --all

# 检测指定区域
heiman-cli perception activity --zone <zone>
```

### 事件回顾

```bash
# 获取最近事件
heiman-cli perception events --limit <n>

# 获取指定时间范围事件
heiman-cli perception events --start <time> --end <time>

# 获取指定类型事件
heiman-cli perception events --type <type>
```

### 状态验证

```bash
# 验证设备状态
heiman-cli perception verify --did <did> --property <prop>

# 验证场景状态
heiman-cli perception verify-scene --scene <name>
```

## 事件类型

| 类型 | 描述 | 示例 |
| ---- | ---- | ---- |
| **motion** | 人体移动 | 有人进入房间 |
| **door** | 门窗状态 | 门打开/关闭 |
| **window** | 窗户状态 | 窗户打开/关闭 |
| **sound** | 声音检测 | 大声喧哗、异常噪音 |
| **alarm** | 安防告警 | 烟雾、燃气泄漏、水浸 |
| **person** | 人员识别 | 识别到家庭成员/陌生人 |

## 感知设备

| 设备类型 | 功能 | 示例 |
| -------- | ---- | ---- |
| **人体传感器** | 检测人体移动 | 红外传感器、毫米波雷达 |
| **门窗传感器** | 检测门窗状态 | 门磁、窗磁 |
| **声音传感器** | 检测声音 | 麦克风、声控传感器 |
| **摄像头** | 画面识别 | 智能摄像头 |
| **安防传感器** | 异常检测 | 烟雾报警器、燃气报警器 |

## 输出格式

### 活动检测结果

```
客厅活动状态：
- 有人员活动
- 最近活动时间：10分钟前
- 活动类型：正常活动
```

### 事件列表

```
最近事件：
1. [2分钟前] 客厅有人进入
2. [15分钟前] 厨房窗户打开
3. [30分钟前] 卧室灯关闭
```

### 状态验证结果

```
客厅灯状态验证：
- 传感器检测：灯亮着
- 设备上报：灯开着
- 状态一致：是
```

## 异常处理

| 异常 | 处理 | 回复 |
| ---- | ---- | ---- |
| 设备离线 | 提示用户 | "传感器离线，无法检测" |
| 无事件记录 | 提示用户 | "暂无事件记录" |
| 状态不一致 | 提示用户 | "检测状态与设备上报不一致，请检查" |

## 边界

- ✅ 检测活动、回顾事件、验证状态
- ❌ 无法读取具体数值（温度、湿度等）→ 走 `heiman-devices`
- ⚠️ 隐私保护：仅在用户授权范围内执行感知

## 示例

### 检测活动

用户："家里有人吗"

```bash
heiman-cli perception activity --all
```

输出：
```
家庭活动状态：
- 客厅：有人员活动
- 卧室：无人
- 厨房：无人
```

### 事件回顾

用户："刚才发生了什么"

```bash
heiman-cli perception events --limit 5
```