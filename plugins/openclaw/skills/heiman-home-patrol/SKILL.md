---
name: heiman-home-patrol
description: heiman-home-patrol 定时任务的内部例程，仅由该任务调用。负责定期巡检家庭安全状态，检查异常并触发相应处理。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-home-patrol

家庭安全巡检定时任务。

## 何时激活

仅由 heiman-home-patrol 定时任务调用，不对外暴露。

## 核心工作流

### 步骤 1 · 安全检查

```bash
# 检查门窗状态
heiman-cli patrol doors
heiman-cli patrol windows

# 检查燃气泄漏
heiman-cli patrol gas

# 检查烟雾报警
heiman-cli patrol smoke

# 检查水浸情况
heiman-cli patrol water

# 检查设备安全
heiman-cli patrol devices
```

### 步骤 2 · 异常处理

发现异常时触发相应处理：

| 异常类型 | 处理方式 |
| -------- | -------- |
| **门窗未关** | 通过 heiman-notify 通知用户 |
| **燃气泄漏** | 立即触发 L1 危险通知，关闭燃气阀 |
| **烟雾报警** | 立即触发 L1 危险通知，检查火源 |
| **水浸报警** | 立即触发 L1 危险通知，关闭水源 |
| **设备异常** | 通过 heiman-notify 通知用户 |

### 步骤 3 · 巡检报告

生成巡检报告：

```json
{
  "patrol_time": "2026-06-24T10:00:00Z",
  "status": "normal",
  "checks": [
    {"item": "doors", "status": "closed"},
    {"item": "windows", "status": "closed"},
    {"item": "gas", "status": "safe"},
    {"item": "smoke", "status": "safe"},
    {"item": "water", "status": "dry"},
    {"item": "devices", "status": "normal"}
  ],
  "issues": []
}
```

## 巡检项目

| 项目 | 检查内容 |
| ---- | -------- |
| **doors** | 所有门是否关闭 |
| **windows** | 所有窗户是否关闭 |
| **gas** | 燃气浓度是否正常 |
| **smoke** | 是否有烟雾 |
| **water** | 是否有水浸 |
| **devices** | 关键设备是否在线 |

## 异常级别

| 级别 | 异常类型 | 处理优先级 |
| ---- | -------- | ---------- |
| **L1** | 燃气泄漏、烟雾、水浸 | 立即处理，多渠道通知 |
| **L2** | 门窗未关 | 通知用户，等待响应 |
| **L3** | 设备离线 | 记录日志，下次巡检重试 |

## 边界

- ✅ 仅由定时任务调用
- ✅ 自动执行安全检查
- ✅ 发现异常自动通知
- ❌ 不直接响应用户查询