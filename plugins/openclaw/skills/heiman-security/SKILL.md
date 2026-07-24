---
name: heiman-security
description: 家庭安防管理：设备安全状态检查、隐私数据保护、Token 用量监控、安全告警联动。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-07-23"
  openclaw:
    requires:
      bins: ["curl", "heiman-cli"]
---

# heiman-security

家庭安防与隐私保护管理，覆盖安全状态检查、数据匿名化、Token 用量监控。

## 何时激活

| 意图 | 用户说了类似… |
| ---- | ------------- |
| **privacy_check** | "隐私状态" "数据安全" "谁在看我的数据" "匿名化" |
| **token_usage** | "Token 用了多少" "API 配额" "还剩多少额度" "每天花多少" |
| **energy_check** | "能耗统计" "用电报告" "省电建议" "能源优化" |

## 核心工作流

### 隐私状态检查

```bash
curl -s http://localhost:1912/api/ai/privacy/status
```

### 数据匿名化

```bash
curl -s -X POST http://localhost:1912/api/ai/privacy/anonymize \
  -H "Content-Type: application/json" \
  -d '{"scope": "sensors"}'
```

### Token 用量查询

```bash
curl -s http://localhost:1912/api/ai/token/usage
curl -s http://localhost:1912/api/ai/token/quota
curl -s http://localhost:1912/api/ai/token/daily
```

### 设置 Token 配额

```bash
curl -s -X POST http://localhost:1912/api/ai/token/quota \
  -H "Content-Type: application/json" \
  -d '{"daily_limit": 10000, "monthly_limit": 300000}'
```

### 能源统计

```bash
curl -s "http://localhost:1912/api/ai/energy/stats?home_id={home_id}"
curl -s "http://localhost:1912/api/ai/energy/report?home_id={home_id}"
curl -s "http://localhost:1912/api/ai/energy/optimization?home_id={home_id}"
```

## 输出格式

### 隐私状态

```json
{
  "success": true,
  "data": {
    "anonymization_enabled": false,
    "data_retention_days": 90,
    "sensitive_fields_protected": true,
    "last_anonymized": null
  }
}
```

### Token 用量

```json
{
  "success": true,
  "data": {
    "today": { "used": 2340, "remaining": 7660 },
    "this_month": { "used": 45000, "remaining": 255000 },
    "quotas": { "daily": 10000, "monthly": 300000 }
  }
}
```

### 能源统计

```json
{
  "success": true,
  "data": {
    "today_consumption_kwh": 12.5,
    "week_consumption_kwh": 85.3,
    "estimated_monthly_kwh": 340.0,
    "peak_hours": ["18:00-20:00"],
    "top_consumers": [
      { "device": "客厅空调", "consumption": 4.2 }
    ]
  }
}
```

## 异常处理

| 异常 | 处理 |
| ---- | ---- |
| Token 配额即将用尽 | 提醒用户当前用量百分比和建议调整配额 |
| 匿名化失败 | 检查数据范围参数，确认数据源可用 |

## 边界

- ✅ 隐私状态查看、数据匿名化
- ✅ Token 用量与配额管理
- ✅ 能源统计与优化建议
- ❌ 不执行数据删除（仅匿名化）
- ⚠️ 匿名化操作不可逆，执行前提示确认
- ⚠️ Token 配额设置后立即生效

## 示例

用户："看看我这个月用了多少 Token"

```bash
curl -s http://localhost:1912/api/ai/token/usage
```

用户："帮我看看家里用电情况，有没有优化空间"

```bash
curl -s "http://localhost:1912/api/ai/energy/stats?home_id=default"
curl -s "http://localhost:1912/api/ai/energy/optimization?home_id=default"
```
