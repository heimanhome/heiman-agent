"""home_profile persistence — JSON file read/write + file lock + atomic write."""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

from heiman.home_profile.schema import CandidatesIndex, ProfileIndex
from heiman.config import get_settings

logger = __import__("logging").getLogger(__name__)


def home_profile_dir() -> Path:
    settings = get_settings()
    return Path(settings.directories.data_dir) / "home-profile"


def profile_json_path() -> Path:
    return home_profile_dir() / "profile.json"


def candidates_json_path() -> Path:
    return home_profile_dir() / "candidates.json"


def profile_md_path() -> Path:
    return home_profile_dir() / "profile.md"


def task_suggestions_path() -> Path:
    return home_profile_dir() / "task-suggestions.json"


def load_task_created_item_ids() -> set[str]:
    path = task_suggestions_path()
    if not path.exists():
        return set()
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return set()
    return {
        e["item_id"]
        for e in raw.get("entries", [])
        if e.get("status") == "created" and e.get("item_id")
    }


def _lock_path() -> Path:
    return home_profile_dir() / ".lock"


@contextlib.contextmanager
def file_lock() -> Iterator[None]:
    home_profile_dir().mkdir(parents=True, exist_ok=True)
    fd = os.open(str(_lock_path()), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def load_profile() -> ProfileIndex:
    path = profile_json_path()
    if not path.exists():
        return ProfileIndex()
    return ProfileIndex.model_validate_json(path.read_text("utf-8"))


def load_candidates() -> CandidatesIndex:
    path = candidates_json_path()
    if not path.exists():
        return CandidatesIndex()
    return CandidatesIndex.model_validate_json(path.read_text("utf-8"))


def save_profile(data: ProfileIndex) -> None:
    _atomic_write_text(
        profile_json_path(),
        json.dumps(data.model_dump(), ensure_ascii=False, indent=2),
    )


def save_candidates(data: CandidatesIndex) -> None:
    _atomic_write_text(
        candidates_json_path(),
        json.dumps(data.model_dump(), ensure_ascii=False, indent=2),
    )


def save_rendered_md(text: str) -> None:
    _atomic_write_text(profile_md_path(), text)


def read_rendered_md() -> str:
    path = profile_md_path()
    if not path.exists():
        return ""
    return path.read_text("utf-8")
