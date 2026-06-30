---
name: heiman-sensors
description: 查询海曼传感器数据，包括温度、湿度、烟雾、一氧化碳和水浸传感器的实时状态和历史数据
metadata:
  author: heiman
  version: "2.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# 传感器查询 Skill

## 概述
用于查询和管理海曼智能家居传感器的数据，包括温度、湿度、烟雾、一氧化碳和水浸传感器。

## 触发场景

| 意图类型 | 用户表述示例 | 触发条件 |
|----------|-------------|----------|
| **查询全部** | "查看所有传感器" "传感器状态" | 关键词：传感器、全部、所有 |
| **查询单个** | "客厅温度多少" "湿度是多少" | 关键词：温度、湿度 + 位置 |
| **查询类型** | "所有温度传感器" "烟雾传感器状态" | 关键词：类型 + 传感器 |
| **历史数据** | "温度历史数据" "最近的湿度变化" | 关键词：历史、变化、趋势 |

## 设备类型映射

### 设备类型定义
```json
{
  "types": {
    "Smoke": {
      "name": "烟雾报警器",
      "properties": ["SmokeSensorState", "BatteryPercentage", "TamperState"],
      "unit": null,
      "thresholds": {
        "normal": 0,
        "alarm": 1,
        "fault": 2
      }
    },
    "CO": {
      "name": "一氧化碳报警器",
      "properties": ["coValue", "CONC", "BatteryPercentage", "TamperState"],
      "unit": "ppm",
      "thresholds": {
        "normal": [0, 35],
        "warning": [35, 50],
        "danger": [50, 100]
      }
    },
    "TH": {
      "name": "温湿度传感器",
      "properties": ["CurrentTemperature", "CurrentHumidity"],
      "units": {"temperature": "°C", "humidity": "%"},
      "comfort": {
        "temperature": [18, 26],
        "humidity": [40, 60]
      }
    },
    "Door": {
      "name": "门磁传感器",
      "properties": ["ContactState", "TamperState"],
      "states": {"open": 1, "closed": 0}
    },
    "Water": {
      "name": "水浸传感器",
      "properties": ["WaterSensorState", "BatteryPercentage"],
      "states": {"normal": 0, "alarm": 1, "fault": 2}
    }
  }
}
```

## 执行命令

### 1. 获取所有传感器
```bash
heiman-cli sensor list
```

**输出格式**:
```
设备ID                    | 名称                 | 类型   | 状态   | 值
------------------------ | -------------------- | ------ | ------ | ------
sn_001                   | 烟雾报警器-客厅      | Smoke  | 在线   | 正常
sn_002                   | 温湿度传感器-卧室    | TH     | 在线   | 24°C, 55%
sn_003                   | 门磁传感器-阳台      | Door   | 离线   | 关门
```

### 2. 获取单个传感器详情
```bash
heiman-cli sensor info <device_id>
```

**输出示例**:
```json
{
  "device_id": "sn_001",
  "device_name": "烟雾报警器-客厅",
  "device_type": "Smoke",
  "room": "客厅",
  "status": "online",
  "properties": {
    "SmokeSensorState": 0,
    "BatteryPercentage": 85,
    "TamperState": 0
  },
  "last_update": "2026-06-24T10:30:00+08:00"
}
```

### 3. 获取传感器历史数据
```bash
heiman-cli sensor history <device_id> [--hours 24] [--format json|table]
```

### 4. 按类型过滤传感器
```bash
heiman-cli sensor list --type <type>
# 类型: smoke, co, th, door, water
```

## 响应模板

### 正常状态响应
```
✅ {设备名称}
   类型: {设备类型}
   状态: {在线/离线}
   数据: {主要数据值}
   更新: {最后更新时间}
```

### 告警状态响应
```
🚨 {设备名称} - {告警类型}
   类型: {设备类型}
   状态: {告警/异常}
   数据: {告警数据值}
   建议: {处理建议}
```

### 离线状态响应
```
⚠️ {设备名称} - 设备离线
   类型: {设备类型}
   离线时长: {X小时X分钟}
   建议: 检查设备电源和网络连接
```

## 异常处理

### 设备离线
**处理方式**: 在响应中标注离线状态和时长

**回复模板**:
```
❌ 无法获取{设备名称}数据
   原因: 设备当前离线（已离线{X}小时）
   建议:
   1. 检查设备是否正常工作
   2. 确认设备是否在通信范围内
   3. 检查设备电池电量
```

### 数据获取失败
**处理方式**: 重试一次，失败后返回错误信息

**回复模板**:
```
❌ 获取{设备名称}数据失败
   原因: {错误原因}
   建议: 请稍后重试，或联系技术支持
```

### 设备不存在
**处理方式**: 返回空结果，提示用户检查设备ID

**回复模板**:
```
❌ 未找到设备: {设备ID}
   建议: 请确认设备ID是否正确
```

## 实用示例

### 示例1: 查询所有传感器
**用户**: "查看所有传感器状态"

**Agent执行**:
1. 调用 `heiman-cli sensor list`
2. 按状态分类展示
3. 生成总结

**响应**:
```
🏠 家庭传感器概览

📊 设备状态:
   • 在线: 4台
   • 离线: 1台

🔍 详细信息:
   1. 烟雾报警器-客厅    ✅ 正常
   2. 温湿度传感器-卧室  ✅ 24°C, 55%
   3. 门磁传感器-阳台    ⚠️ 离线

总体状态: 良好
```

### 示例2: 查询特定传感器
**用户**: "客厅温度多少？"

**Agent执行**:
1. 识别位置：客厅
2. 调用 `heiman-cli sensor list --type th`
3. 查找客厅温湿度传感器
4. 返回数据

**响应**:
```
🌡️ 客厅温湿度传感器

   温度: 24.5°C (舒适)
   湿度: 55% (舒适)

   状态: 在线
   更新: 10分钟前

💡 建议: 环境舒适，无需调节
```

### 示例3: 历史数据查询
**用户**: "这周温度有什么变化？"

**Agent执行**:
1. 调用 `heiman-cli sensor history <device_id> --hours 168` (7天)
2. 分析数据趋势
3. 生成趋势报告

**响应**:
```
📈 温度趋势分析（过去7天）

   今日平均: 24.5°C
   上周平均: 22.3°C
   变化: +2.2°C

   最高: 28°C (6月22日)
   最低: 20°C (6月20日)

💡 建议: 本周温度略有上升，注意适时通风
```

## 约束条件

### 数据限制
- 单次查询最多返回100条历史记录
- 历史数据默认保留30天
- 实时数据延迟不超过1分钟

### 权限限制
- 仅可查询授权家庭下的设备
- 不可跨家庭访问设备数据

### 频率限制
- 实时查询: 10次/分钟
- 历史查询: 5次/分钟
- 批量查询: 3次/分钟

## 参考资料

- [设备数据模型](../references/device-model.md)
- [API协议规范](../references/api-protocol.md)
- [告警阈值定义](../references/thresholds.md)
