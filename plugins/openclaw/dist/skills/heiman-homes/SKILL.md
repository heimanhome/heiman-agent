---
name: heiman-homes
description: 获取和管理家庭列表，支持查询家庭信息、获取当前选择家庭的设备列表。当用户询问"我有几个家庭"、"当前家庭有哪些设备"、"切换家庭"等问题时激活。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-25"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-homes

家庭管理，获取家庭列表、家庭详情和设备列表。

## 何时激活

| 意图 | 用户说了类似… |
| ---- | ------------- |
| **list** | "我有几个家庭" "查看所有家庭" "列出我的家庭" |
| **detail** | "家庭详情" "这个家庭有多少设备" "家庭成员" |
| **devices** | "当前家庭有哪些设备" "家庭设备列表" "家里有什么设备" |
| **select** | "切换到另一个家庭" "选择家庭" "切换家庭" |

## 核心工作流

### 步骤 1 · 获取家庭列表

```bash
heiman-cli home list
```

返回格式：
```json
{
  "homes": {
    "success": true,
    "data": [
      {
        "id": "home_001",
        "name": "我的家",
        "address": "北京市朝阳区",
        "members": [],
        "devices": 5,
        "createdAt": "2024-01-01T00:00:00Z"
      }
    ]
  }
}
```

### 步骤 2 · 获取家庭详情

```bash
heiman-cli home get <home_id>
```

返回格式：
```json
{
  "success": true,
  "data": {
    "id": "home_001",
    "name": "我的家",
    "address": "北京市朝阳区",
    "members": [
      {"id": "user_001", "name": "张三", "role": "owner", "avatar": "Z"}
    ],
    "devices": 5,
    "createdAt": "2024-01-01T00:00:00Z"
  }
}
```

### 步骤 3 · 获取指定家庭的设备列表

```bash
heiman-cli device list --home-id <home_id>
```

返回格式：
```json
{
  "devices": {
    "success": true,
    "data": [
      {
        "id": "device_001",
        "name": "客厅温湿度传感器",
        "type": "temperature",
        "status": "online",
        "value": 25.5,
        "unit": "°C",
        "room": "客厅",
        "battery": 100
      }
    ]
  }
}
```

## 默认行为

- **未指定家庭时**：返回第一个家庭作为默认当前家庭
- **当前家庭设备查询**：用户未指定家庭时，默认使用第一个家庭的 ID 查询设备

## 响应模板

| 查询类型 | 响应模板 |
| -------- | -------- |
| 家庭列表 | "您共有 {count} 个家庭：{names}" |
| 家庭详情 | "{name}（{address}），共有 {devices} 个设备，{members} 位成员" |
| 家庭设备 | "{home_name} 共有 {count} 个设备：{device_names}" |

## 示例

| 用户说 | 命令 |
| ------ | ---- |
| "我有几个家庭" | `heiman-cli home list` |
| "当前家庭有哪些设备" | `heiman-cli home list` → 获取第一个家庭 → `heiman-cli device list --home-id <home_id>` |
| "查看家庭详情" | `heiman-cli home get <home_id>` |
| "切换到第二个家庭" | 返回家庭列表让用户确认 → 使用新家庭 ID 查询设备 |

## 边界

- ✅ 获取家庭列表和详情
- ✅ 获取指定家庭的设备列表
- ✅ 默认使用第一个家庭作为当前家庭
- ❌ 不支持创建/修改/删除家庭（需通过海曼 App 操作）