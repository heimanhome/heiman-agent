"""CLI 配置管理 (``$HEIMAN_HOME/config.json``)。

- 结构与后端配置对齐
- 优先级：环境变量 (``HEIMAN_*`` / ``HEIMAN_SERVER__*``) > ``$HEIMAN_HOME/config.json`` > 默认值。
- Token 由 heiman 后端 bootstrap 写入 ``server.token``，CLI 不应覆盖。
"""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


def heiman_home() -> Path:
    """返回 ``$HEIMAN_HOME``，未设置则落回 ``~/.heiman``。"""
    if env := os.environ.get("HEIMAN_HOME"):
        return Path(env).expanduser()
    return Path.home() / ".heiman"


def config_file() -> Path:
    """返回 ``$HEIMAN_HOME/config.json``。"""
    return heiman_home() / "config.json"


_SCHEMA_PATHS: dict[str, tuple[type, Any, str]] = {
    "debug": (bool, False, "是否启用调试模式"),
    "server.url": (str, "http://127.0.0.1:1912", "Heiman Agent 后端 HTTP Base URL"),
    "server.tls_verify": (bool, False, "访问后端时是否校验 TLS 证书"),
    "server.python_bin": (str, "", "启动 heiman-backend 的 Python 解释器绝对路径"),
}


def atomic_write(path: Path, data: dict) -> None:
    """原子写：临时文件 + ``os.replace``。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_raw() -> dict[str, Any]:
    path = config_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    _validate_structure(data)
    return data


def _dict_paths() -> set[str]:
    out: set[str] = set()
    for path in _SCHEMA_PATHS:
        parts = path.split(".")
        for i in range(1, len(parts)):
            out.add(".".join(parts[:i]))
    return out


def _validate_structure(data: dict[str, Any]) -> None:
    for path in _dict_paths():
        cur: Any = data
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                break
            cur = cur[part]
        else:
            if not isinstance(cur, dict):
                raise ValueError(
                    f"config.json 结构错误: 期望 {path!r} 为对象(object), "
                    f"实际为 {type(cur).__name__}。请检查 {config_file()}"
                )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _get_nested(data: dict[str, Any], path: str) -> Any:
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _UNSET
        cur = cur[part]
    return cur


def _set_nested(data: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur = data
    for part in parts[:-1]:
        node = cur.get(part)
        if not isinstance(node, dict):
            node = {}
            cur[part] = node
        cur = node
    cur[parts[-1]] = value


_UNSET: Any = object()


def _defaults() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path, (_, default, _desc) in _SCHEMA_PATHS.items():
        _set_nested(out, path, default)
    return out


def _coerce(path: str, raw: str) -> Any:
    if path not in _SCHEMA_PATHS:
        raise ValueError(
            f"unknown config path: {path} (known: {', '.join(sorted(_SCHEMA_PATHS))})"
        )
    pytype = _SCHEMA_PATHS[path][0]
    if pytype is bool:
        low = raw.strip().lower()
        if low in ("true", "1", "yes", "on"):
            return True
        if low in ("false", "0", "no", "off"):
            return False
        raise ValueError(f"{path} 需要 bool 值，收到 {raw!r}")
    if pytype is int:
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"{path} 需要整数，收到 {raw!r}") from exc
    if pytype is float:
        try:
            return float(raw)
        except ValueError as exc:
            raise ValueError(f"{path} 需要浮点数，收到 {raw!r}") from exc
    return raw


_ENV_PREFIX = "HEIMAN_"
_ENV_NESTED_DELIM = "__"


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(config)
    for key, raw_value in os.environ.items():
        if not key.startswith(_ENV_PREFIX):
            continue
        if key in ("HEIMAN_HOME",):
            continue
        suffix = key[len(_ENV_PREFIX) :].lower()
        parts = suffix.split(_ENV_NESTED_DELIM)
        path = ".".join(parts)
        if path not in _SCHEMA_PATHS:
            continue
        try:
            value = _coerce(path, raw_value)
        except ValueError:
            continue
        _set_nested(out, path, value)
    return out


def load_config() -> dict[str, Any]:
    raw_file = _read_raw()
    merged = _deep_merge(_defaults(), raw_file)
    merged = _apply_env_overrides(merged)
    return merged


def show_config() -> dict[str, Any]:
    merged = load_config()
    return merged


def get_value(path: str) -> Any:
    merged = load_config()
    value = _get_nested(merged, path)
    if value is _UNSET:
        raise KeyError(path)
    return value


def set_value(path: str, raw_value: str) -> Any:
    return set_values([(path, raw_value)])[path]


def set_values(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    if not pairs:
        return {}
    resolved: dict[str, Any] = {}
    for path, raw in pairs:
        if path not in _SCHEMA_PATHS:
            raise ValueError(
                f"unknown config path: {path} "
                f"(known: {', '.join(sorted(_SCHEMA_PATHS))})"
            )
        resolved[path] = _coerce(path, raw)
    raw_file = _read_raw()
    for path, value in resolved.items():
        _set_nested(raw_file, path, value)
    atomic_write(config_file(), raw_file)
    return resolved


def known_paths() -> list[str]:
    return sorted(_SCHEMA_PATHS)


def describe(path: str) -> str:
    if path not in _SCHEMA_PATHS:
        raise KeyError(path)
    return _SCHEMA_PATHS[path][2]
