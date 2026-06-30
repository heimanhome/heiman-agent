import asyncio
import logging
import os
from typing import Dict, Optional, Any, List


logger = logging.getLogger(__name__)


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
            import onnxruntime as ort

            model_path = config.get("model_path", f"{model_name}.onnx")
            providers = ["CPUExecutionProvider"]

            if config.get("use_gpu", False):
                providers.insert(0, "CUDAExecutionProvider")

            session = ort.InferenceSession(model_path, providers=providers)

            return {
                "type": "onnx",
                "session": session,
                "providers": providers,
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
        try:
            import httpx

            model_name = model_info["model"]
            base_url = params.get("base_url", "http://localhost:11434")

            body = {
                "model": model_name,
                "prompt": prompt,
                "max_tokens": params.get("max_tokens", 512),
                "temperature": params.get("temperature", 0.7),
                "top_p": params.get("top_p", 0.9),
                "stream": False,
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{base_url}/api/generate",
                    json=body,
                )
                response.raise_for_status()
                result = response.json()

            return {
                "success": True,
                "response": result.get("response", ""),
                "usage": result.get("usage", {}),
            }
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

            import numpy as np
            input_ids = np.random.randint(0, 10000, (1, 128)).astype(np.int64)
            attention_mask = np.ones((1, 128), dtype=np.int64)

            outputs = session.run(None, {"input_ids": input_ids, "attention_mask": attention_mask})

            return {
                "success": True,
                "response": "ONNX inference completed",
                "output_shape": outputs[0].shape,
            }
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