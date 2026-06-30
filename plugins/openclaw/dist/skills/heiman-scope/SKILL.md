---
name: heiman-scope
description: 感知范围控制 — 管理 heiman 感知哪些家庭、哪些传感器。用户说「只用/不用某家庭」「让 heiman 感知/别感知 某家庭或传感器」「屏蔽某传感器/把某传感器从感知里去掉」「哪些家庭在用」时激活。注意区分：开关传感器设备本身（开机/关机/电源/录制）走 heiman-devices。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-scope

感知范围控制管理。

## 何时激活

| 意图 | 用户说了类似… |
| ---- | ------------- |
| **add** | "添加家庭" "让 heiman 感知这个家" "启用传感器" |
| **remove** | "移除家庭" "别感知这个家" "屏蔽传感器" |
| **list** | "哪些家庭在用" "查看感知范围" "有哪些传感器" |
| **enable** | "启用感知" "打开传感器" "开始监控" |
| **disable** | "禁用感知" "关闭传感器" "停止监控" |

## 核心工作流

### 家庭管理

```bash
# 添加家庭
heiman-cli scope home add --name <name> --location <location>

# 移除家庭
heiman-cli scope home remove --name <name>

# 列出所有家庭
heiman-cli scope home list

# 启用/禁用家庭感知
heiman-cli scope home enable --name <name>
heiman-cli scope home disable --name <name>
```

### 传感器管理

```bash
# 添加传感器到感知范围
heiman-cli scope sensor add --did <did> --room <room>

# 从感知范围移除传感器
heiman-cli scope sensor remove --did <did>

# 列出所有感知中的传感器
heiman-cli scope sensor list

# 启用/禁用传感器感知
heiman-cli scope sensor enable --did <did>
heiman-cli scope sensor disable --did <did>
```

### 传感器类别

| 类别 | 描述 | 示例 |
| ---- | ---- | ---- |
| **motion** | 人体传感器 | 人体红外、毫米波雷达 |
| **contact** | 门窗传感器 | 门窗磁、门磁开关 |
| **environmental** | 环境传感器 | 温湿度、空气质量、光照 |
| **security** | 安防传感器 | 烟雾报警器、燃气报警器、水浸传感器 |
| **camera** | 摄像头 | 智能摄像头 |

## 感知范围配置

### 按房间配置

```bash
# 配置房间传感器
heiman-cli scope room configure --name <room> --sensors <did1>,<did2>

# 查看房间配置
heiman-cli scope room get --name <room>
```

### 按场景配置

| 场景 | 推荐传感器 |
| ---- | ---------- |
| **安防模式** | 门窗传感器、人体传感器、摄像头 |
| **节能模式** | 温湿度传感器、人体传感器 |
| **健康模式** | 环境传感器、空气质量传感器 |

## 异常处理

| 异常 | 处理 | 回复 |
| ---- | ---- | ---- |
| 家庭不存在 | 提示用户先添加 | "该家庭不存在，请先添加" |
| 传感器不存在 | 提示用户检查设备 | "未找到该传感器，请检查设备" |
| 传感器已在范围内 | 提示用户 | "该传感器已在感知范围内" |
| 禁用后影响任务 | 提示用户相关任务将失效 | "禁用后，相关的自动化任务将暂停" |

## 边界

- ✅ 管理感知范围（哪些设备参与感知）
- ❌ 控制设备本身（开关、录制等）→ 走 `heiman-devices`
- ⚠️ 禁用感知会影响相关自动化任务

## 示例

### 添加家庭

用户："让 heiman 感知新家"

```bash
heiman-cli scope home add --name "新家" --location "北京市朝阳区"
```

### 屏蔽传感器

用户："别感知厨房的摄像头"

```bash
heiman-cli scope sensor disable --did <厨房摄像头 DID>
```
