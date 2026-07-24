import logging
import os
import threading
from typing import Optional, Dict, List, Any
from enum import Enum

logger = logging.getLogger(__name__)

def _estimate_tokens(text: str) -> int:
    """粗略估算文本的 token 数：英文 ~4 字符/token，中文 ~1.5 字符/token"""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def _record_token_usage(model: str, usage: dict, usage_type: str = "api",
                         prompt_text: str = "", response_text: str = "") -> None:
    try:
        from heiman.database.token_usage_repo import get_token_usage_repo
        repo = get_token_usage_repo()
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens_from_usage = usage.get("total_tokens", 0)

        # 兜底：如果 API 没返回 token 数（Ollama 常见），用文本长度估算
        if prompt_tokens <= 0 and prompt_text:
            prompt_tokens = _estimate_tokens(prompt_text)
            logger.debug(f"[TOKEN] Estimated prompt tokens: {prompt_tokens}")
        if completion_tokens <= 0 and response_text:
            completion_tokens = _estimate_tokens(response_text)
            logger.debug(f"[TOKEN] Estimated completion tokens: {completion_tokens}")

        # 始终记录（即使为 0 也记录一次请求，便于统计请求次数）
        repo.record_usage(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            usage_type=usage_type,
        )
        logger.debug(
            "[TOKEN] Recorded usage: model=%s, prompt=%d, completion=%d, total=%d",
            model, prompt_tokens, completion_tokens,
            total_tokens_from_usage or prompt_tokens + completion_tokens,
        )
    except Exception as e:
        logger.warning(f"[TOKEN] Failed to record token usage: {e}")


def _check_token_quota(model: str = "", usage_type: str = "api", estimated_tokens: int = 1000) -> bool:
    try:
        from heiman.database.token_usage_repo import get_token_usage_repo
        repo = get_token_usage_repo()
        quota_status = repo.check_quota(model, usage_type, estimated_tokens)

        if quota_status["will_exceed"]:
            logger.warning(
                "[TOKEN] Quota exceeded: model=%s, usage=%d/%d",
                model,
                quota_status["daily_usage"],
                quota_status["daily_limit"],
            )
            return False

        if quota_status["at_warning"]:
            logger.warning(
                "[TOKEN] Quota warning: model=%s, usage=%d/%d (%.1f%%)",
                model,
                quota_status["daily_usage"],
                quota_status["daily_limit"],
                (quota_status["daily_usage"] / quota_status["daily_limit"]) * 100,
            )

        return True
    except Exception as e:
        logger.warning(f"[TOKEN] Failed to check quota: {e}")
        return True


class LlmProvider(Enum):
    OPENAI = "openai"
    DASHSCOPE = "dashscope"
    OLLAMA = "ollama"


class LlmClient:
    # 类级锁，确保多个 LlmClient 实例不会同时向 Ollama 发请求
    _ollama_lock: threading.Lock = threading.Lock()

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

        if not _check_token_quota(model):
            logger.warning("[LLM] Token quota exceeded, using fallback")
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

            # 类级锁确保 Ollama 同一时间只有一个请求
            with LlmClient._ollama_lock:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=500,
                )

            response_text = response.choices[0].message.content.strip()

            # 获取 usage 信息，Ollama 的 OpenAI 兼容端点可能不返回完整 usage
            usage = {}
            if hasattr(response, 'usage') and response.usage:
                usage = {
                    "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0) or 0,
                    "completion_tokens": getattr(response.usage, 'completion_tokens', 0) or 0,
                    "total_tokens": getattr(response.usage, 'total_tokens', 0) or 0,
                }
                logger.debug(
                    "[LLM] API usage response: model=%s, prompt=%s, completion=%s, total=%s",
                    model,
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                    usage.get("total_tokens"),
                )

            # 始终记录 token（即使 usage 为空也会用文本长度估算）
            _record_token_usage(model, usage, prompt_text=prompt, response_text=response_text)

            return response_text
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

    def classify(self, data: Dict, categories: List[str], model: str = "qwen2:7b") -> str:
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

            response = self.generate(prompt, model=model)
            return response.strip()
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return self._fallback_classify(data, categories)

    def suggest_action(self, context: Dict, model: str = "qwen2:7b") -> str:
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

            return self.generate(prompt, model=model)
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
