"""输出工具：默认紧凑 JSON，--pretty 缩进输出。

后端 API 已直接返回部署时区带偏移的本地 ISO(如 ``2026-06-16T17:19:45+08:00``),
CLI 不再做二次本地化转换。
"""

import json
from typing import Any


def dump(data: Any, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)
    return json.dumps(data, ensure_ascii=False, default=str)


def print_result(data: Any, pretty: bool = False) -> None:
    print(dump(data, pretty))


def print_error(message: str) -> None:
    import sys
    print(dump({"error": message}), file=sys.stderr)