import logging
import os
from typing import Optional, Dict, List, Any
from enum import Enum

logger = logging.getLogger(__name__)

def _record_token_usage(model: str, usage: dict, usage_type: str = "api") -> None:
    try:
        from heiman.database.token_usage_repo import get_token_usage_repo
        repo = get_token_usage_repo()
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        if prompt_tokens > 0 or completion_tokens > 0:
            repo.record_usage(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                usage_type=usage_type,
            )
            logger.debug(f"[TOKEN] Recorded usage: model={model}, prompt={prompt_tokens}, completion={completion_tokens}")
    except Exception as e:
        logger.warning(f"[TOKEN] Failed to record token usage: {e}")


class LlmProvider(Enum):
    OPENAI = "openai"
    DASHSCOPE = "dashscope"
    OLLAMA = "ollama"


class LlmClient:
    def __init__(self, provider: str = "ollama", api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.provider = LlmProvider(provider.lower())
        self.api_key = api_key or os.environ.get("LLM_API_KEY")
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        if self._client:
            return self._client

        try:
            if self.provider == LlmProvider.OPENAI:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url or "https://api.openai.com/v1",
                )
            elif self.provider == LlmProvider.DASHSCOPE:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                )
            elif self.provider == LlmProvider.OLLAMA:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key="ollama",
                    base_url=self.base_url or "http://localhost:11434/v1",
                )
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
        except ImportError:
            logger.warning("openai package not installed, using fallback mode")
            self._client = None

        return self._client

    def generate(self, prompt: str, context: Optional[Dict] = None, model: str = "qwen2:7b") -> str:
        client = self._get_client()
        if not client:
            return self._fallback_generate(prompt, context)

        try:
            system_prompt = """你是一个智能家居AI助手，帮助用户分析家庭传感器数据并提供智能建议。
            请用简洁、友好的语言回答，提供具体的行动建议。
            如果数据不足，请明确说明。"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]

            if context:
                context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
                messages.insert(-1, {"role": "system", "content": f"上下文数据:\n{context_str}"})

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=500,
            )

            if hasattr(response, 'usage'):
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }
                _record_token_usage(model, usage)

            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return self._fallback_generate(prompt, context)

    def summarize(self, events: List[Dict], model: str = "qwen2:7b") -> str:
        client = self._get_client()
        if not client:
            return self._fallback_summarize(events)

        try:
            events_str = "\n".join(
                f"- [{e.get('timestamp', '')}] {e.get('type', '')}: {e.get('message', '')}"
                for e in events
            )

            prompt = f"""请总结以下智能家居事件，用简洁的自然语言描述今天发生的主要活动和状态变化。

事件列表:
{events_str}

请提供一个清晰的摘要，包括：
1. 主要活动时间线
2. 异常情况（如果有）
3. 环境状态变化"""

            return self.generate(prompt, model=model)
        except Exception as e:
            logger.error(f"LLM summarization failed: {e}")
            return self._fallback_summarize(events)

    def classify(self, data: Dict, categories: List[str]) -> str:
        client = self._get_client()
        if not client:
            return self._fallback_classify(data, categories)

        try:
            data_str = "\n".join(f"- {k}: {v}" for k, v in data.items())
            categories_str = ", ".join(categories)

            prompt = f"""请将以下传感器数据分类到最合适的类别。

数据:
{data_str}

可选类别: {categories_str}

请只返回一个最合适的类别名称。"""

            response = self.generate(prompt)
            return response.strip()
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return self._fallback_classify(data, categories)

    def suggest_action(self, context: Dict) -> str:
        client = self._get_client()
        if not client:
            return self._fallback_suggest_action(context)

        try:
            context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())

            prompt = f"""基于以下家庭状态，请提供智能建议。

当前状态:
{context_str}

请提供具体的、可操作的建议，包括：
1. 当前需要关注的事项
2. 建议采取的行动
3. 预期效果"""

            return self.generate(prompt)
        except Exception as e:
            logger.error(f"LLM suggestion failed: {e}")
            return self._fallback_suggest_action(context)

    def _fallback_generate(self, prompt: str, context: Optional[Dict] = None) -> str:
        logger.info("Using fallback mode for LLM generation")
        return "AI分析服务暂不可用，请稍后重试。"

    def _fallback_summarize(self, events: List[Dict]) -> str:
        if not events:
            return "暂无事件记录。"

        recent_events = events[-5:]
        summary_lines = []

        for e in recent_events:
            timestamp = e.get("timestamp", "")[:16]
            event_type = e.get("type", "未知")
            message = e.get("message", "")
            summary_lines.append(f"{timestamp} {event_type}: {message}")

        return "\n".join(summary_lines)

    def _fallback_classify(self, data: Dict, categories: List[str]) -> str:
        if "temperature" in data or "humidity" in data:
            return "环境"
        if "motion" in data or "door" in data:
            return "安全"
        if "switch" in data:
            return "设备控制"
        return categories[0] if categories else "其他"

    def _fallback_suggest_action(self, context: Dict) -> str:
        suggestions = []

        if context.get("temperature"):
            temp = context["temperature"]
            if temp > 28:
                suggestions.append("温度较高，建议开启空调。")
            elif temp < 18:
                suggestions.append("温度较低，建议开启暖气。")

        if context.get("humidity"):
            humidity = context["humidity"]
            if humidity > 70:
                suggestions.append("湿度较高，建议通风或除湿。")
            elif humidity < 30:
                suggestions.append("湿度较低，建议使用加湿器。")

        if context.get("co2") and context["co2"] > 1000:
            suggestions.append("CO2浓度较高，建议开窗通风。")

        if context.get("door_open"):
            suggestions.append("检测到门打开，请注意安全。")

        if not suggestions:
            suggestions.append("当前家庭状态正常，无需特别操作。")

        return "\n".join(suggestions)
