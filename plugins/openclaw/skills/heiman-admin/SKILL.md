---
name: heiman-admin
description: Heiman 系统运维：连通性 / 设备缓存 / 感知成本统计。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-admin

Heiman 智能家居系统运维管理。

## 何时激活

| 意图 | 用户说了类似… |
| ---- | ------------- |
| **connectivity** | "检查设备连接" "网络状态" "哪个设备离线了" |
| **cache** | "刷新设备缓存" "清理缓存" "重新加载设备" |
| **cost** | "感知成本统计" "本月用了多少" "统计报告" |
| **status** | "系统状态" "服务状态" "诊断" |

## 核心工作流

### 连通性检查

```bash
# 检查所有设备连接状态
heiman-cli admin connectivity check

# 检查指定设备连接状态
heiman-cli admin connectivity check --did <did>

# 重新连接离线设备
heiman-cli admin connectivity reconnect --did <did>
```

### 设备缓存管理

```bash
# 刷新设备列表缓存
heiman-cli admin cache refresh

# 清理指定设备缓存
heiman-cli admin cache clear --did <did>

# 清理所有缓存
heiman-cli admin cache clear --all
```

### 感知成本统计

```bash
# 获取今日统计
heiman-cli admin cost today

# 获取本周统计
heiman-cli admin cost week

# 获取本月统计
heiman-cli admin cost month

# 获取指定时间段统计
heiman-cli admin cost range --start <date> --end <date>
```

### 系统状态诊断

```bash
# 完整系统诊断
heiman-cli admin status

# 检查服务状态
heiman-cli admin status --service

# 检查设备状态
heiman-cli admin status --devices

# 检查网络状态
heiman-cli admin status --network
```

## 输出格式

### 连通性报告

```
设备连接状态报告：
- 在线：15 台
- 离线：2 台（客厅空调、卧室灯）
- 异常：0 台
```

### 成本统计报告

```
本月感知成本统计：
- 传感器调用：12,345 次
- 摄像头识别：2,345 次
- 语音交互：567 次
- 总费用：¥12.34
```

### 系统状态报告

```
系统状态：
- 服务状态：正常运行
- 数据库状态：正常
- 网络延迟：25ms
- 设备总数：17 台
```

## 异常处理

| 异常 | 处理 |
| ---- | ---- |
| 设备离线 | 建议用户检查电源和网络，或尝试重新连接 |
| 服务异常 | 建议用户重启服务或联系技术支持 |
| 缓存问题 | 自动执行缓存清理并刷新 |

## 边界

- ❌ 不执行危险操作（如格式化、删除数据等）
- ✅ 仅提供诊断信息和建议
- ⚠️ 涉及敏感操作需用户确认
