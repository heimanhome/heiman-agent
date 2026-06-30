---
name: heiman-edge-inference
description: 边缘计算推理服务，支持本地LLM推理、模型管理、量化优化。在本地设备上运行AI模型，保护隐私，降低延迟。
metadata:
  author: heiman
  version: "1.0"
  date: "2026-06-25"
  openclaw:
    requires:
      bins: ["heiman-cli"]
---

# heiman-edge-inference

边缘AI推理与模型管理。

## 何时激活

| 意图 | 用户说了类似… |
| ---- | ------------- |
| **local_inference** | "帮我分析一下" "本地推理" "智能分析" |
| **list_models** | "有哪些模型" "可用模型" "模型列表" |
| **quantize_model** | "优化模型" "模型压缩" "量化模型" |
| **ai_response** | "AI怎么说" "智能回答" "给我建议" |

## 核心工作流

### 本地推理

```bash
heiman-cli ai edge-infer --model-id <model_id> --prompt <prompt>
```

### 列出可用模型

```bash
heiman-cli ai edge-models --pretty
```

### 模型量化

```bash
heiman-cli ai quantize --model <model_name> --output <path> --bits <4|8>
```

## 支持的模型提供商

| 提供商 | 描述 | 配置要求 |
| ------ | ---- | -------- |
| **ollama** | 本地LLM运行时 | 需要安装Ollama |
| **transformers** | HuggingFace模型 | 需要安装transformers |
| **onnx** | ONNX格式模型 | 需要安装onnxruntime |

## 输出格式

### 推理结果

```
推理结果：
- 模型：qwen3:8b
- 响应：根据分析，建议您...
- 置信度：高
```

### 模型列表

```json
{
  "models": [
    {
      "id": "llm_default",
      "provider": "ollama",
      "config": {
        "model": "qwen3:8b",
        "base_url": "http://localhost:11434"
      }
    }
  ]
}
```

## 边界

- ✅ 本地推理、模型管理、量化优化
- ❌ 无法访问云端API → 需要网络连接
- ⚠️ 性能依赖：推理速度取决于设备性能

## 示例

用户："用AI分析一下家里的情况"

```bash
heiman-cli ai edge-infer --model-id llm_default --prompt "分析以下家庭状态并给出建议：温度26度，湿度60%，安全状态正常"
```

输出：
```json
{
  "success": true,
  "response": "当前环境舒适，安全状态良好。建议保持当前状态。",
  "usage": {}
}
```