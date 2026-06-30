"""Log pack module - package logs and trace data for debugging."""

import logging
import zipfile
from datetime import datetime
from pathlib import Path

from heiman.config import get_settings

logger = logging.getLogger(__name__)

MAX_PACK_SIZE_MB = 500
MAX_PACK_COUNT = 2


class LogPackSizeExceeded(Exception):
    """Raised when log pack size exceeds limit."""

    def __init__(self, info: dict):
        self.info = info
        super().__init__(f"Log pack size exceeded: {info}")


def _scan_sizes(log_dir: Path, db_path: Path) -> dict:
    """Scan sizes of log files and database."""
    sizes = {}
    total = 0

    if log_dir.exists():
        for f in log_dir.iterdir():
            if f.is_file():
                size_mb = f.stat().st_size / (1024 * 1024)
                sizes[f.name] = round(size_mb, 2)
                total += size_mb

    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        sizes["heiman.db"] = round(size_mb, 2)
        total += size_mb

    sizes["_total_mb"] = round(total, 2)
    return sizes


def _rotate_old_packs(pack_dir: Path) -> None:
    """Keep only the latest MAX_PACK_COUNT packs."""
    packs = sorted(pack_dir.glob("log-pack-*.zip"), reverse=True)
    for old_pack in packs[MAX_PACK_COUNT:]:
        try:
            old_pack.unlink()
            logger.info("Removed old log pack: %s", old_pack.name)
        except OSError:
            logger.warning("Failed to remove old pack: %s", old_pack.name)


def build_log_pack() -> dict:
    """Build a log pack zip file.

    Returns pack info dict with filename, size, and file count.
    Raises LogPackSizeExceeded if total size exceeds MAX_PACK_SIZE_MB.
    """
    settings = get_settings()
    log_dir = settings.logging.log_dir
    db_path = log_dir.parent / "heiman.db"
    pack_dir = log_dir.parent / "packs"
    pack_dir.mkdir(parents=True, exist_ok=True)

    sizes = _scan_sizes(log_dir, db_path)
    total_mb = sizes.get("_total_mb", 0)

    if total_mb > MAX_PACK_SIZE_MB:
        raise LogPackSizeExceeded({
            "total_mb": total_mb,
            "limit_mb": MAX_PACK_SIZE_MB,
            "breakdown": {k: v for k, v in sizes.items() if k != "_total_mb"},
        })

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    pack_name = f"log-pack-{timestamp}.zip"
    pack_path = pack_dir / pack_name

    file_count = 0
    with zipfile.ZipFile(pack_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if log_dir.exists():
            for f in log_dir.iterdir():
                if f.is_file():
                    zf.write(f, arcname=f"logs/{f.name}")
                    file_count += 1

        if db_path.exists():
            zf.write(db_path, arcname="heiman.db")
            file_count += 1

        info_content = f"""Heiman Agent Log Pack
Generated: {datetime.now().isoformat()}
Log directory: {log_dir}
Database: {db_path}
Files included: {file_count}
Total size: {total_mb:.2f} MB
"""
        zf.writestr("PACK_INFO.txt", info_content)
        file_count += 1

    pack_size_mb = pack_path.stat().st_size / (1024 * 1024)

    _rotate_old_packs(pack_dir)

    logger.info("Log pack created: %s (%.2f MB, %d files)", pack_name, pack_size_mb, file_count)

    return {
        "filename": pack_name,
        "size_mb": round(pack_size_mb, 2),
        "file_count": file_count,
        "path": str(pack_path),
    }
