---
name: heiman-identity
description: 家庭成员档案 CRUD —— 创建/列出/重命名/删除成员。**身份样本注册(给某人录脸/录身形)走 heiman-identity-register,本 skill 不做。**
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-24"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-identity

家庭成员身份管理。

## 何时激活

| 意图 | 用户说了类似… |
| ---- | ------------- |
| **create** | "添加家庭成员" "注册新成员" "把爸爸加进来" |
| **list** | "有哪些家庭成员" "列出所有成员" "看看谁在" |
| **rename** | "改名字" "重命名" "豆豆改名叫小明" |
| **delete** | "删除成员" "移除爸爸" "把奶奶删掉" |

## 核心工作流

### 创建成员

```bash
heiman-cli person create --name <name> --role <role> [--avatar <url>]
```

| 参数 | 说明 | 示例 |
| ---- | ---- | ---- |
| `--name` | 成员名称 | "豆豆"、"爸爸" |
| `--role` | 角色关系 | "爸爸"、"妈妈"、"儿子"、"女儿" |
| `--avatar` | 头像 URL（可选） | 照片链接 |

### 列出成员

```bash
# 列出所有成员
heiman-cli person list

# 获取指定成员详情
heiman-cli person get --name <name>
```

### 重命名成员

```bash
heiman-cli person rename --name <old_name> --new-name <new_name>
```

### 删除成员

```bash
heiman-cli person delete --name <name>
```

> **注意**：删除成员会同时删除相关的档案记录和任务，需二次确认。

## 角色规范

| 角色 | 说明 |
| ---- | ---- |
| **爸爸** | 父亲 |
| **妈妈** | 母亲 |
| **儿子** | 儿子 |
| **女儿** | 女儿 |
| **爷爷** | 祖父 |
| **奶奶** | 祖母 |
| **外公** | 外祖父 |
| **外婆** | 外祖母 |
| **其他** | 自定义角色 |

## 异常处理

| 异常 | 处理 | 回复 |
| ---- | ---- | ---- |
| 成员已存在 | 询问是否更新或使用不同名称 | "已存在同名成员，是否更新信息？" |
| 成员不存在 | 提示用户先创建 | "未找到该成员，请先添加" |
| 删除确认 | 二次确认后执行 | "确定要删除 xxx 吗？删除后无法恢复" |

## 边界

- ❌ 身份样本注册（录脸/录身形）→ 走 `heiman-identity-register`
- ❌ 删除成员需二次确认
- ✅ 支持创建、查询、更新、删除操作

## 示例

### 创建成员

用户："添加爸爸"

```bash
heiman-cli person create --name "爸爸" --role "爸爸"
```

### 列出成员

用户："有哪些家庭成员"

```bash
heiman-cli person list
```

输出：
```
家庭成员列表：
1. 爸爸 - 角色：爸爸
2. 妈妈 - 角色：妈妈
3. 豆豆 - 角色：儿子
```
