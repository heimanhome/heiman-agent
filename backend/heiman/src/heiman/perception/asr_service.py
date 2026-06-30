import asyncio
import logging
import os
from typing import Dict, Optional, Any, List


logger = logging.getLogger(__name__)


class ASRService:
    SUPPORTED_PROVIDERS = ["whisper", "baidu", "aliyun", "mock"]

    def __init__(self, provider: str = "mock", config: Optional[Dict] = None):
        self.provider = provider.lower()
        self.config = config or {}
        self._running = False
        self._model = None

        if self.provider not in self.SUPPORTED_PROVIDERS:
            logger.warning(f"Unsupported ASR provider: {provider}, using mock")
            self.provider = "mock"

    async def initialize(self):
        if self.provider == "whisper":
            await self._init_whisper()
        elif self.provider == "baidu":
            await self._init_baidu()
        elif self.provider == "aliyun":
            await self._init_aliyun()

        self._running = True
        logger.info(f"ASR service initialized with provider: {self.provider}")

    async def _init_whisper(self):
        try:
            import whisper
            model_name = self.config.get("model", "base")
            self._model = whisper.load_model(model_name)
            logger.info(f"Whisper model loaded: {model_name}")
        except ImportError:
            logger.warning("Whisper not installed, falling back to mock")
            self.provider = "mock"
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            self.provider = "mock"

    async def _init_baidu(self):
        try:
            from aip import AipSpeech
            self._client = AipSpeech(
                self.config["app_id"],
                self.config["api_key"],
                self.config["secret_key"],
            )
            logger.info("Baidu ASR client initialized")
        except ImportError:
            logger.warning("baidu-aip not installed, falling back to mock")
            self.provider = "mock"
        except KeyError:
            logger.warning("Baidu ASR config incomplete, falling back to mock")
            self.provider = "mock"

    async def _init_aliyun(self):
        try:
            from aliyunsdkcore.client import AcsClient
            self._client = AcsClient(
                self.config["access_key_id"],
                self.config["access_key_secret"],
                self.config.get("region_id", "cn-shanghai"),
            )
            logger.info("Aliyun ASR client initialized")
        except ImportError:
            logger.warning("aliyun-python-sdk-core not installed, falling back to mock")
            self.provider = "mock"
        except KeyError:
            logger.warning("Aliyun ASR config incomplete, falling back to mock")
            self.provider = "mock"

    async def recognize(self, audio_data: bytes, format: str = "wav") -> Dict[str, Any]:
        if not self._running:
            await self.initialize()

        if self.provider == "whisper":
            return await self._recognize_whisper(audio_data)
        elif self.provider == "baidu":
            return await self._recognize_baidu(audio_data, format)
        elif self.provider == "aliyun":
            return await self._recognize_aliyun(audio_data, format)
        else:
            return await self._recognize_mock(audio_data)

    async def _recognize_whisper(self, audio_data: bytes) -> Dict[str, Any]:
        try:
            import tempfile
            import whisper

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name

            result = self._model.transcribe(temp_path)
            os.unlink(temp_path)

            return {
                "success": True,
                "text": result["text"],
                "segments": [
                    {
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": seg["text"],
                    }
                    for seg in result.get("segments", [])
                ],
                "confidence": 0.9,
                "language": result.get("language", "zh"),
            }
        except Exception as e:
            logger.error(f"Whisper recognition failed: {e}")
            return {"success": False, "error": str(e)}

    async def _recognize_baidu(self, audio_data: bytes, format: str) -> Dict[str, Any]:
        try:
            result = self._client.asr(
                audio_data,
                format,
                16000,
                {
                    "dev_pid": 1537,
                },
            )

            if result.get("err_no") == 0:
                return {
                    "success": True,
                    "text": "".join(result["result"]),
                    "confidence": 0.85,
                    "language": "zh",
                }
            else:
                return {"success": False, "error": result.get("err_msg", "Unknown error")}
        except Exception as e:
            logger.error(f"Baidu ASR failed: {e}")
            return {"success": False, "error": str(e)}

    async def _recognize_aliyun(self, audio_data: bytes, format: str) -> Dict[str, Any]:
        try:
            from aliyunsdkcore.request import CommonRequest

            request = CommonRequest()
            request.set_method("POST")
            request.set_domain("nls-meta.cn-shanghai.aliyuncs.com")
            request.set_version("2019-02-28")
            request.set_action_name("CreateTask")

            request.add_body_params("AppKey", self.config.get("app_key", ""))
            request.add_body_params("FileUrl", self.config.get("file_url", ""))
            request.add_body_params("Version", "4.0")
            request.add_body_params("EnableWords", False)

            response = self._client.do_action_with_exception(request)
            return {
                "success": True,
                "text": str(response),
                "confidence": 0.85,
                "language": "zh",
            }
        except Exception as e:
            logger.error(f"Aliyun ASR failed: {e}")
            return {"success": False, "error": str(e)}

    async def _recognize_mock(self, audio_data: bytes) -> Dict[str, Any]:
        mock_responses = [
            "回家了",
            "开灯",
            "关灯",
            "调温度",
            "打开空调",
            "关闭电视",
            "早上好",
            "晚安",
            "检测一下安全",
            "我出门了",
        ]

        import random
        return {
            "success": True,
            "text": random.choice(mock_responses),
            "confidence": 0.7 + random.random() * 0.3,
            "language": "zh",
        }

    async def stream_recognize(self, audio_stream) -> List[Dict[str, Any]]:
        results = []
        async for chunk in audio_stream:
            result = await self.recognize(chunk)
            if result.get("success"):
                results.append(result)
        return results


class MicrophoneCollector(BaseCollector):
    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._asr_service = None
        self._asr_provider = config.config.get("asr_provider", "mock")
        self._asr_config = config.config.get("asr_config", {})

    async def start(self):
        await super().start()
        self._asr_service = ASRService(self._asr_provider, self._asr_config)
        await self._asr_service.initialize()

        asyncio.create_task(self._collection_loop())

    async def stop(self):
        await super().stop()

    async def _collection_loop(self):
        while self._running:
            try:
                result = await self._asr_service.recognize(b"mock_audio_data")

                if result.get("success"):
                    event_data = {
                        "type": "audio_event",
                        "location": self.config.config.get("location", "unknown"),
                        "sound_detected": True,
                        "speech_detected": True,
                        "content": result["text"],
                        "confidence": result.get("confidence", 0.0),
                        "language": result.get("language", "zh"),
                        "timestamp": asyncio.get_event_loop().time(),
                    }

                    if self._callback:
                        await self._callback(event_data)

            except Exception as e:
                logger.error(f"Microphone collection error: {e}")

            await asyncio.sleep(self.config.interval)