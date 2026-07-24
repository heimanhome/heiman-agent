import asyncio
import logging
import os
from typing import Dict, Optional, Any, List

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    """粗略估算文本的 token 数：英文 ~4 字符/token，中文 ~1.5 字符/token"""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def _record_token_usage(model: str, usage: dict, usage_type: str = "edge",
                         prompt_text: str = "", response_text: str = "") -> None:
    try:
        from heiman.database.token_usage_repo import get_token_usage_repo
        repo = get_token_usage_repo()
        # Ollama 原生 API 返回 prompt_eval_count/eval_count，OpenAI 兼容端点返回 prompt_tokens/completion_tokens
        prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens", usage.get("prompt_eval_count", 0)))
        completion_tokens = usage.get("completion_tokens", usage.get("output_tokens", usage.get("eval_count", 0)))

        # 兜底：如果 API 没返回 token 数，用文本长度估算
        if prompt_tokens <= 0 and prompt_text:
            prompt_tokens = _estimate_tokens(prompt_text)
            logger.debug(f"[TOKEN] Estimated edge prompt tokens: {prompt_tokens}")
        if completion_tokens <= 0 and response_text:
            completion_tokens = _estimate_tokens(response_text)
            logger.debug(f"[TOKEN] Estimated edge completion tokens: {completion_tokens}")

        # 始终记录
        repo.record_usage(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            usage_type=usage_type,
        )
        logger.info(
            "[TOKEN] Recorded edge usage: model=%s, prompt=%d, completion=%d",
            model, prompt_tokens, completion_tokens,
        )
    except Exception as e:
        logger.warning(f"[TOKEN] Failed to record edge token usage: {e}")


def _check_token_quota(model: str = "", usage_type: str = "edge", estimated_tokens: int = 1000) -> bool:
    try:
        from heiman.database.token_usage_repo import get_token_usage_repo
        repo = get_token_usage_repo()
        quota_status = repo.check_quota(model, usage_type, estimated_tokens)

        if quota_status["will_exceed"]:
            logger.warning(
                "[TOKEN] Edge inference quota exceeded: model=%s, usage=%d/%d",
                model,
                quota_status["daily_usage"],
                quota_status["daily_limit"],
            )
            return False

        if quota_status["at_warning"]:
            logger.warning(
                "[TOKEN] Edge inference quota warning: model=%s, usage=%d/%d (%.1f%%)",
                model,
                quota_status["daily_usage"],
                quota_status["daily_limit"],
                (quota_status["daily_usage"] / quota_status["daily_limit"]) * 100,
            )

        return True
    except Exception as e:
        logger.warning(f"[TOKEN] Failed to check edge inference quota: {e}")
        return True


class EdgeInferenceEngine:
    def __init__(self):
        self._models: Dict[str, Any] = {}
        self._providers = {
            "ollama": self._init_ollama,
            "transformers": self._init_transformers,
            "onnx": self._init_onnx,
        }

    async def initialize(self, models: Optional[List[Dict]] = None):
        if models:
            for model_config in models:
                await self.load_model(model_config)

    async def load_model(self, config: Dict):
        model_id = config.get("id", config.get("name", "unknown"))
        provider = config.get("provider", "ollama")
        model_name = config.get("model", "qwen3:8b")

        init_fn = self._providers.get(provider)
        if init_fn:
            try:
                model = await init_fn(model_name, config)
                self._models[model_id] = {
                    "model": model,
                    "config": config,
                    "provider": provider,
                }
                logger.info(f"Loaded model {model_id} via {provider}")
            except Exception as e:
                logger.error(f"Failed to load model {model_id}: {e}")
        else:
            logger.warning(f"Unknown provider: {provider}")

    async def _init_ollama(self, model_name: str, config: Dict) -> Any:
        return {"type": "ollama", "model": model_name, "config": config}

    async def _init_transformers(self, model_name: str, config: Dict) -> Any:
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

            device = config.get("device", "cpu")
            quantized = config.get("quantized", False)

            if quantized:
                model_name = f"{model_name}-quantized"

            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                device_map="auto" if device == "gpu" else "cpu",
                load_in_4bit=config.get("load_in_4bit", False),
                load_in_8bit=config.get("load_in_8bit", False),
            )

            return {
                "type": "transformers",
                "tokenizer": tokenizer,
                "model": model,
                "pipeline": pipeline(
                    "text-generation",
                    model=model,
                    tokenizer=tokenizer,
                    device=0 if device == "gpu" else -1,
                ),
            }
        except ImportError:
            logger.warning("transformers not installed")
            raise
        except Exception as e:
            logger.error(f"Failed to load transformers model: {e}")
            raise

    async def _init_onnx(self, model_name: str, config: Dict) -> Any:
        try:
            from heiman.perception.inference import make_session

            model_path = config.get("model_path", f"{model_name}.onnx")
            use_gpu = config.get("use_gpu", False)
            num_threads = config.get("num_threads", None)

            session = make_session(model_path, use_gpu=use_gpu, num_threads=num_threads)

            input_info = []
            for inp in session.get_inputs():
                input_info.append({
                    "name": inp.name,
                    "shape": inp.shape,
                    "type": inp.type,
                })

            output_names = [output.name for output in session.get_outputs()]

            return {
                "type": "onnx",
                "session": session,
                "input_info": input_info,
                "output_names": output_names,
            }
        except ImportError:
            logger.warning("onnxruntime not installed")
            raise
        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
            raise

    async def infer(self, model_id: str, prompt: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        model_info = self._models.get(model_id)
        if not model_info:
            return {"error": f"Model {model_id} not found"}

        model_name = model_info.get("model", model_id)
        if not _check_token_quota(model_name, usage_type="edge"):
            logger.warning("[EDGE] Token quota exceeded for model: %s", model_name)
            return {"success": False, "error": "Token quota exceeded"}

        provider = model_info["provider"]
        params = params or {}

        if provider == "ollama":
            return await self._infer_ollama(model_info, prompt, params)
        elif provider == "transformers":
            return await self._infer_transformers(model_info, prompt, params)
        elif provider == "onnx":
            return await self._infer_onnx(model_info, prompt, params)

        return {"error": f"Unknown provider: {provider}"}

    async def _infer_ollama(self, model_info: Dict, prompt: str, params: Dict) -> Dict[str, Any]:
        """使用 OpenAI 兼容 API 调用 Ollama（标准 /v1/chat/completions 端点）"""
        try:
            from openai import AsyncOpenAI

            from heiman.ai.llm_semaphore import get_ai_semaphore

            model_name = model_info["model"]
            base_url = params.get("base_url", "http://localhost:11434/v1")

            # 确保 base_url 以 /v1 结尾（OpenAI 兼容端点）
            base_url = base_url.rstrip("/")
            if not base_url.endswith("/v1"):
                base_url += "/v1"

            client = AsyncOpenAI(
                api_key="ollama",
                base_url=base_url,
            )

            messages = [{"role": "user", "content": prompt}]
            max_tokens = params.get("max_tokens", 512)
            temperature = params.get("temperature", 0.7)

            sem = get_ai_semaphore()
            async with sem:
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

            response_text = response.choices[0].message.content.strip() if response.choices else ""

            # 提取 usage 信息
            usage = {}
            if hasattr(response, 'usage') and response.usage:
                usage = {
                    "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0) or 0,
                    "completion_tokens": getattr(response.usage, 'completion_tokens', 0) or 0,
                    "total_tokens": getattr(response.usage, 'total_tokens', 0) or 0,
                }

            logger.info(
                "[EDGE] Ollama usage: model=%s, prompt=%d, completion=%d, total=%d",
                model_name,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                usage.get("total_tokens", 0),
            )

            _record_token_usage(model_name, usage, prompt_text=prompt, response_text=response_text)

            return {
                "success": True,
                "response": response_text,
                "usage": usage,
            }
        except ImportError:
            logger.warning("openai package not installed, edge inference unavailable")
            return {"success": False, "error": "openai package not installed"}
        except Exception as e:
            logger.error(f"Ollama inference failed: {e}")
            return {"success": False, "error": str(e)}

    async def _infer_transformers(self, model_info: Dict, prompt: str, params: Dict) -> Dict[str, Any]:
        try:
            pipeline = model_info["pipeline"]
            tokenizer = model_info["tokenizer"]

            inputs = tokenizer(prompt, return_tensors="pt")
            outputs = pipeline(
                prompt,
                max_length=params.get("max_tokens", 512),
                num_return_sequences=1,
                temperature=params.get("temperature", 0.7),
                do_sample=True,
            )

            response = outputs[0]["generated_text"].replace(prompt, "").strip()

            return {
                "success": True,
                "response": response,
            }
        except Exception as e:
            logger.error(f"Transformers inference failed: {e}")
            return {"success": False, "error": str(e)}

    async def _infer_onnx(self, model_info: Dict, prompt: str, params: Dict) -> Dict[str, Any]:
        try:
            session = model_info["session"]
            input_info = model_info.get("input_info", [])
            output_names = model_info.get("output_names", None)

            import numpy as np

            inputs = {}
            for inp in input_info:
                input_name = inp["name"]
                input_shape = inp["shape"]
                input_type = inp["type"]

                if input_name in params:
                    inputs[input_name] = np.array(params[input_name], dtype=np.float32)
                else:
                    dtype_map = {
                        "tensor(float)": np.float32,
                        "tensor(int64)": np.int64,
                        "tensor(int32)": np.int32,
                    }
                    dtype = dtype_map.get(input_type, np.float32)
                    shape = tuple(d if d > 0 else 1 for d in input_shape)
                    inputs[input_name] = np.zeros(shape, dtype=dtype)

            outputs = session.run(output_names, inputs)

            result = {"success": True, "outputs": []}
            for i, output in enumerate(outputs):
                result["outputs"].append({
                    "index": i,
                    "shape": output.shape,
                    "dtype": str(output.dtype),
                    "data": output.tolist() if output.size < 100 else "large_array",
                })

            return result
        except Exception as e:
            logger.error(f"ONNX inference failed: {e}")
            return {"success": False, "error": str(e)}

    async def list_models(self) -> List[Dict]:
        return [
            {
                "id": model_id,
                "provider": info["provider"],
                "config": info["config"],
            }
            for model_id, info in self._models.items()
        ]

    async def unload_model(self, model_id: str):
        if model_id in self._models:
            del self._models[model_id]
            logger.info(f"Unloaded model: {model_id}")


class QuantizationService:
    @staticmethod
    async def quantize_model(model_name: str, output_path: str, bits: int = 4):
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import prepare_model_for_kbit_training

            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                load_in_4bit=bits == 4,
                load_in_8bit=bits == 8,
                device_map="auto",
            )

            model.save_pretrained(output_path)
            tokenizer.save_pretrained(output_path)

            logger.info(f"Model quantized to {bits} bits and saved to {output_path}")
            return {"success": True, "output_path": output_path}
        except ImportError:
            logger.warning("transformers or peft not installed")
            return {"success": False, "error": "Required packages not installed"}
        except Exception as e:
            logger.error(f"Quantization failed: {e}")
            return {"success": False, "error": str(e)}