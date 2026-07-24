"""全局 LLM 信号量，确保 Ollama 同一时间只有一个请求在执行。

本地 Ollama 是单线程推理，多个并发请求只会排队竞争 GPU/CPU，
反而更慢。用 asyncio.Semaphore(1) 在上层排队更可控。
"""

import asyncio
import logging

_logger = logging.getLogger(__name__)

_ai_semaphore: asyncio.Semaphore | None = None


def get_ai_semaphore() -> asyncio.Semaphore:
    """获取或创建全局 AI 信号量（单例）。"""
    global _ai_semaphore
    if _ai_semaphore is None:
        _ai_semaphore = asyncio.Semaphore(1)
        _logger.info("[LLM_Semaphore] Global AI semaphore initialized (concurrency=1)")
    return _ai_semaphore
