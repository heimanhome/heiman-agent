"""ONNX Runtime session utilities — centralised thread control."""

from __future__ import annotations

import logging
import platform

import onnxruntime as ort

_LOGGER = logging.getLogger(__name__)

_DEFAULT_NUM_THREADS = 4

_IS_APPLE_SILICON = (
    platform.system() == "Darwin" and platform.machine() == "arm64"
)


def _ort_version_ge(major: int, minor: int) -> bool:
    try:
        parts = ort.__version__.split(".")
        return (int(parts[0]), int(parts[1])) >= (major, minor)
    except (ValueError, IndexError):
        return False


def make_session(
    model_path: str,
    *,
    use_gpu: bool = False,
    num_threads: int | None = None,
) -> ort.InferenceSession:
    providers = ["CPUExecutionProvider"]
    available = ort.get_available_providers()
    if use_gpu and "CUDAExecutionProvider" in available:
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    elif _IS_APPLE_SILICON and "CoreMLExecutionProvider" in available:
        providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    elif _IS_APPLE_SILICON:
        _LOGGER.warning(
            "Apple Silicon detected but CoreMLExecutionProvider not in %s; "
            "falling back to CPU EP — KleidiAI workspace leak will reappear. "
            "Check onnxruntime wheel build options.",
            available,
        )

    opts = ort.SessionOptions()
    threads = num_threads if num_threads is not None else _DEFAULT_NUM_THREADS
    opts.intra_op_num_threads = threads
    opts.inter_op_num_threads = threads

    if _ort_version_ge(1, 25):
        opts.add_session_config_entry("mlas.disable_kleidiai", "1")

    _LOGGER.info("ORT session providers=%s for %s", providers, model_path)
    return ort.InferenceSession(model_path, sess_options=opts, providers=providers)