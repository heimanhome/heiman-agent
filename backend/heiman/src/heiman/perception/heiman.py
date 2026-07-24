import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from collections.abc import Awaitable


logger = logging.getLogger(__name__)


@dataclass
class HeimanContext:
    home_id: str
    timestamp: float
    persons: List[Dict] = field(default_factory=list)
    events: List[Dict] = field(default_factory=list)
    device_states: List[Dict] = field(default_factory=list)
    environment: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HeimanOutput:
    response: str = ""
    matched_rules: List[Dict] = field(default_factory=list)
    suggestions: List[Dict] = field(default_factory=list)
    speeches: List[Dict] = field(default_factory=list)
    identity_assignments: List[Dict] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HeimanConfig:
    model: str = "qwen3:8b"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    max_completion_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    timeout: float = 30.0


class HeimanLayer:
    def __init__(self, config: Optional[HeimanConfig] = None):
        self.config = config or HeimanConfig()
        self._llm_client = None

    async def run(self, context: HeimanContext, query: Optional[str] = None) -> HeimanOutput:
        prompt = self._build_prompt(context, query)
        raw_response = await self._call_llm(prompt)
        output = self._parse_response(raw_response)
        return output

    async def run_stream(
        self,
        context: HeimanContext,
        query: Optional[str] = None,
        on_chunk: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> HeimanOutput:
        prompt = self._build_prompt(context, query)
        buffer = ""
        
        async for chunk in self._call_llm_stream(prompt):
            buffer += chunk
            if on_chunk:
                await on_chunk(chunk)
        
        return self._parse_response(buffer)

    def _build_prompt(self, context: HeimanContext, query: Optional[str]) -> str:
        parts = []
        
        parts.append("你是一个智能家庭助手，负责分析家庭状态并提供智能建议。")
        parts.append("")
        parts.append("=== 当前家庭上下文 ===")
        
        if context.persons:
            persons_str = ", ".join([f"{p['name']}({p.get('role', '')})" for p in context.persons])
            parts.append(f"当前在家人员：{persons_str}")
        
        if context.environment:
            env_str = ", ".join([f"{k}: {v}" for k, v in context.environment.items()])
            parts.append(f"环境状态：{env_str}")
        
        if context.device_states:
            online_count = sum(1 for d in context.device_states if d.get("status") == "online")
            parts.append(f"设备状态：{online_count}/{len(context.device_states)} 台在线")
        
        if context.events:
            recent_events = context.events[-5:]
            events_str = "; ".join([f"{e.get('type')}@{e.get('location', '')}" for e in recent_events])
            parts.append(f"最近事件：{events_str}")
        
        parts.append("")
        
        if query:
            parts.append(f"用户问题：{query}")
        else:
            parts.append("请分析当前家庭状态并提供智能建议。")
        
        parts.append("")
        parts.append("请输出详细的分析报告，包括：")
        parts.append("1. 当前状态总结")
        parts.append("2. 检测到的异常（如果有）")
        parts.append("3. 智能建议")
        parts.append("4. 推荐的操作")
        
        return "\n".join(parts)

    async def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """使用 OpenAI 兼容 API 调用 LLM（标准 /v1/chat/completions 端点）"""
        try:
            from openai import AsyncOpenAI

            from heiman.ai.llm_semaphore import get_ai_semaphore

            # 确保 base_url 以 /v1 结尾（OpenAI 兼容端点）
            base_url = self.config.base_url.rstrip("/")
            if not base_url.endswith("/v1"):
                base_url += "/v1"

            client = AsyncOpenAI(
                api_key=self.config.api_key or "ollama",
                base_url=base_url,
            )

            messages = [{"role": "user", "content": prompt}]

            sem = get_ai_semaphore()
            async with sem:
                response = await client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    max_tokens=self.config.max_completion_tokens,
                    temperature=self.config.temperature,
                )

            response_text = response.choices[0].message.content.strip() if response.choices else ""

            usage = {}
            if hasattr(response, 'usage') and response.usage:
                usage = {
                    "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0) or 0,
                    "completion_tokens": getattr(response.usage, 'completion_tokens', 0) or 0,
                    "total_tokens": getattr(response.usage, 'total_tokens', 0) or 0,
                }

            return {"response": response_text, "usage": usage}
        except ImportError:
            logger.warning("openai package not installed, using fallback")
            return {
                "response": "智能分析服务暂时不可用，请稍后重试。",
                "usage": {},
            }
        except Exception as e:
            logger.warning(f"Heiman LLM call failed: {e}, using fallback")
            return {
                "response": "智能分析服务暂时不可用，请稍后重试。",
                "usage": {},
            }

    async def _call_llm_stream(self, prompt: str):
        """使用 OpenAI 兼容 API 进行流式调用"""
        try:
            from openai import AsyncOpenAI

            from heiman.ai.llm_semaphore import get_ai_semaphore

            # 确保 base_url 以 /v1 结尾（OpenAI 兼容端点）
            base_url = self.config.base_url.rstrip("/")
            if not base_url.endswith("/v1"):
                base_url += "/v1"

            client = AsyncOpenAI(
                api_key=self.config.api_key or "ollama",
                base_url=base_url,
            )

            messages = [{"role": "user", "content": prompt}]

            sem = get_ai_semaphore()
            async with sem:
                stream = await client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    max_tokens=self.config.max_completion_tokens,
                    temperature=self.config.temperature,
                    stream=True,
                )
                async for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
        except ImportError:
            logger.warning("openai package not installed, streaming unavailable")
            yield "智能分析服务暂时不可用，请稍后重试。"
        except Exception as e:
            logger.warning(f"Heiman LLM stream failed: {e}")
            yield "智能分析服务暂时不可用，请稍后重试。"

    def _parse_response(self, raw: Dict[str, Any]) -> HeimanOutput:
        if isinstance(raw, dict):
            response_text = raw.get("response", raw.get("content", ""))
        else:
            response_text = str(raw)
        
        return HeimanOutput(
            response=response_text,
            suggestions=self._extract_suggestions(response_text),
            usage=raw.get("usage", {}) if isinstance(raw, dict) else {},
        )

    def _extract_suggestions(self, text: str) -> List[Dict]:
        suggestions = []
        
        suggestion_keywords = ["建议", "应该", "需要", "推荐", "可以"]
        
        for line in text.split("\n"):
            for keyword in suggestion_keywords:
                if keyword in line:
                    suggestions.append({
                        "event": "analysis",
                        "action": line.strip(),
                        "confidence": 0.7,
                    })
                    break
        
        return suggestions

    async def batch_run(self, contexts: List[HeimanContext]) -> List[HeimanOutput]:
        results = []
        for context in contexts:
            result = await self.run(context)
            results.append(result)
        return results