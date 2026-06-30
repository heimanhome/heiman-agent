from __future__ import annotations

import collections
import logging
import os
import threading
import time

import psutil

logger = logging.getLogger(__name__)

RESOURCE_MONITOR_INTERVAL = 60
MEMORY_RING_MAXLEN = 3 * 24 * 60


class ResourceMonitor:
    def __init__(self, db_path: str, log_dir: str):
        self._db_path = db_path
        self._log_dir = log_dir
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._data: dict = {}
        self._lock = threading.Lock()
        self._psutil_proc = psutil.Process()
        self._memory_ring: collections.deque[dict] = collections.deque(
            maxlen=MEMORY_RING_MAXLEN
        )

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="resource-monitor", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def get_data(self) -> dict:
        with self._lock:
            return dict(self._data)

    def get_memory_latest(self) -> dict | None:
        with self._lock:
            if not self._memory_ring:
                return None
            return dict(self._memory_ring[-1])

    def get_memory_series(
        self, window_seconds: int = 3600, bucket_seconds: int = 60
    ) -> dict:
        with self._lock:
            if not self._memory_ring:
                return {"buckets": [], "count": 0}

            now = time.time()
            cutoff = now - window_seconds
            recent = [s for s in self._memory_ring if s["ts"] >= cutoff]

            if not recent:
                return {"buckets": [], "count": 0}

            buckets: dict[int, list[dict]] = {}
            for s in recent:
                bucket_ts = int(s["ts"] // bucket_seconds) * bucket_seconds
                if bucket_ts not in buckets:
                    buckets[bucket_ts] = []
                buckets[bucket_ts].append(s)

            result = []
            for bucket_ts in sorted(buckets.keys()):
                items = buckets[bucket_ts]
                rss_vals = [i.get("rss_mb", 0) for i in items if "rss_mb" in i]
                cpu_vals = [i.get("cpu_pct", 0) for i in items if "cpu_pct" in i]
                result.append({
                    "ts": bucket_ts,
                    "rss_mb_avg": round(sum(rss_vals) / len(rss_vals), 1) if rss_vals else 0,
                    "rss_mb_max": max(rss_vals) if rss_vals else 0,
                    "cpu_pct_avg": round(sum(cpu_vals) / len(cpu_vals), 1) if cpu_vals else 0,
                    "samples": len(items),
                })

            return {"buckets": result, "count": len(result)}

    def _run(self) -> None:
        try:
            self._psutil_proc.cpu_percent(interval=0)
        except Exception:
            pass
        self._collect()
        while not self._stop_event.wait(timeout=RESOURCE_MONITOR_INTERVAL):
            self._collect()

    def _collect(self) -> None:
        snapshot: dict = {"ts": time.time()}

        proc = self._psutil_proc
        try:
            snapshot["cpu_pct"] = proc.cpu_percent(interval=0)
        except Exception:
            pass
        try:
            mem = proc.memory_info()
            snapshot["rss_mb"] = round(mem.rss / (1024 * 1024), 1)
            snapshot["vms_mb"] = round(mem.vms / (1024 * 1024), 1)
        except Exception:
            pass
        try:
            snapshot["fd"] = proc.num_fds()
        except Exception:
            pass
        try:
            snapshot["threads"] = proc.num_threads()
        except Exception:
            pass

        try:
            sys_mem = psutil.virtual_memory()
            snapshot["sys_mem_total_mb"] = round(sys_mem.total / (1024 * 1024), 1)
            snapshot["sys_mem_available_mb"] = round(sys_mem.available / (1024 * 1024), 1)
            snapshot["sys_mem_percent"] = sys_mem.percent
        except Exception:
            pass

        try:
            sys_cpu = psutil.cpu_percent(interval=0)
            snapshot["sys_cpu_pct"] = sys_cpu
        except Exception:
            pass

        try:
            if os.path.exists(self._db_path):
                snapshot["db_size_mb"] = round(
                    os.path.getsize(self._db_path) / (1024 * 1024), 2
                )
        except Exception:
            pass

        try:
            total_log = 0
            log_count = 0
            if os.path.isdir(self._log_dir):
                for f in os.listdir(self._log_dir):
                    fp = os.path.join(self._log_dir, f)
                    if os.path.isfile(fp):
                        total_log += os.path.getsize(fp)
                        log_count += 1
            snapshot["log_size_mb"] = round(total_log / (1024 * 1024), 2)
            snapshot["log_files"] = log_count
        except Exception:
            pass

        try:
            disk = psutil.disk_usage(self._db_path if os.path.exists(self._db_path) else "/")
            snapshot["disk_total_mb"] = round(disk.total / (1024 * 1024), 1)
            snapshot["disk_used_mb"] = round(disk.used / (1024 * 1024), 1)
            snapshot["disk_free_mb"] = round(disk.free / (1024 * 1024), 1)
            snapshot["disk_percent"] = disk.percent
        except Exception:
            pass

        with self._lock:
            self._data = snapshot
            self._memory_ring.append(dict(snapshot))