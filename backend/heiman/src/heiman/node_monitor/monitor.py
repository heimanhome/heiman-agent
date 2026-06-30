from __future__ import annotations

import sys
import threading
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager


class Lifecycle:
    REGISTERED = "REGISTERED"
    STARTING = "STARTING"
    READY = "READY"
    RUNNING_START = "RUNNING_START"
    RUNNING_END = "RUNNING_END"
    STALLED = "STALLED"
    FAILED = "FAILED"

    @property
    def is_unhealthy(self):
        return self in (self.FAILED, self.STALLED)

    @property
    def is_dormant(self):
        return self == self.REGISTERED


class NodeKind:
    SOURCE = "SOURCE"
    WINDOW = "WINDOW"
    SERVICE = "SERVICE"
    EVENT = "EVENT"


class NodeName:
    SENSOR = "sensor"
    COLLECTOR = "collector"
    CLASSIFIER = "classifier"
    RULE_ENGINE = "rule_engine"
    API_CLIENT = "api_client"


class RollingCounter:
    def __init__(self, window_s: float = 60.0):
        self._window_s = window_s
        self._success_times: list[float] = []
        self._failure_times: list[float] = []
        self._input_counts: list[tuple[float, int]] = []
        self._output_counts: list[tuple[float, int]] = []

    def record_success(self, latency_ms: float = 0.0, window_ms: float = 0.0, now: float | None = None):
        ts = now if now is not None else time.monotonic()
        self._success_times.append(ts)

    def record_failure(self, now: float | None = None):
        ts = now if now is not None else time.monotonic()
        self._failure_times.append(ts)

    def record_input(self, n: int = 1, now: float | None = None):
        ts = now if now is not None else time.monotonic()
        self._input_counts.append((ts, n))

    def record_output(self, n: int = 1, now: float | None = None):
        ts = now if now is not None else time.monotonic()
        self._output_counts.append((ts, n))

    def trim(self, now: float):
        cutoff = now - self._window_s
        self._success_times = [t for t in self._success_times if t >= cutoff]
        self._failure_times = [t for t in self._failure_times if t >= cutoff]
        self._input_counts = [(t, n) for t, n in self._input_counts if t >= cutoff]
        self._output_counts = [(t, n) for t, n in self._output_counts if t >= cutoff]

    def success_count(self):
        return len(self._success_times)

    def failure_count(self):
        return len(self._failure_times)

    def total_count(self):
        return self.success_count() + self.failure_count()

    def failure_rate(self):
        total = self.total_count()
        if total == 0:
            return None
        return self.failure_count() / total


class NodeState:
    __slots__ = (
        "name", "kind", "watchdog_s", "registered_at", "started_at",
        "last_progress_at", "lifecycle", "stalled_since", "last_error",
        "rolling", "stage_rollings", "detail"
    )

    def __init__(self, name: str, kind: str, watchdog_s: float = 0):
        self.name = name
        self.kind = kind
        self.watchdog_s = watchdog_s
        self.registered_at = time.monotonic()
        self.started_at = None
        self.last_progress_at = None
        self.lifecycle = Lifecycle.REGISTERED
        self.stalled_since = None
        self.last_error = None
        self.rolling = RollingCounter()
        self.stage_rollings: dict[str, RollingCounter] = {}
        self.detail: dict = {}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "watchdog_s": self.watchdog_s,
            "lifecycle": self.lifecycle,
            "last_progress_at": self.last_progress_at,
            "last_error": self.last_error,
            "detail": self.detail,
            "rolling": {
                "success": self.rolling.success_count(),
                "failure": self.rolling.failure_count(),
                "total": self.rolling.total_count(),
            },
        }


class TrackHandle:
    __slots__ = ("_state", "_window_ms", "_input_n", "_output_n", "_skip_rolling")

    def __init__(self, state: NodeState | None = None):
        self._state = state
        self._window_ms: float = 0.0
        self._input_n: int = 0
        self._output_n: int = 0
        self._skip_rolling: bool = False

    def add_input(self, n: int = 1) -> None:
        self._input_n += n

    def add_output(self, n: int = 1) -> None:
        self._output_n += n

    def add_window_ms(self, ms: float) -> None:
        self._window_ms += ms

    def skip_rolling(self) -> None:
        self._skip_rolling = True


class NodeMonitor:
    _instance: NodeMonitor | None = None
    _init_lock = threading.Lock()

    def __init__(self) -> None:
        self._states: dict[str, NodeState] = {}
        self._warned_missing: set[str] = set()

    @classmethod
    def get_instance(cls) -> NodeMonitor:
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, name: str, kind: str, watchdog_s: float = 0) -> None:
        if name in self._states:
            return
        self._states[name] = NodeState(name, kind, watchdog_s)

    def _warn_missing(self, method: str, name: str) -> None:
        if name in self._warned_missing:
            return
        self._warned_missing.add(name)
        _stderr(f"[node_monitor] {method}: node {name!r} not registered")

    @asynccontextmanager
    async def track_async(self, name: str, stage: str = "default") -> AsyncIterator[TrackHandle]:
        state = self._states.get(name)
        if state is None:
            self._warn_missing("track_async", name)
            yield TrackHandle()
            return

        handle = TrackHandle(state)
        entered_lifecycle = state.lifecycle
        t0 = time.monotonic()

        try:
            self._enter_track(state, entered_lifecycle, stage)
        except Exception:
            _stderr(f"[node_monitor] _enter_track failed for {name}")
            yield handle
            return

        exc_to_raise: BaseException | None = None
        try:
            yield handle
        except BaseException as e:
            exc_to_raise = e

        try:
            self._exit_track(state, entered_lifecycle, handle, t0, exc_to_raise, stage)
        except Exception:
            _stderr(f"[node_monitor] _exit_track failed for {name}")

        if exc_to_raise is not None:
            raise exc_to_raise

    @contextmanager
    def track(self, name: str, stage: str = "default") -> Iterator[TrackHandle]:
        state = self._states.get(name)
        if state is None:
            self._warn_missing("track", name)
            yield TrackHandle()
            return

        handle = TrackHandle(state)
        entered_lifecycle = state.lifecycle
        t0 = time.monotonic()

        try:
            self._enter_track(state, entered_lifecycle, stage)
        except Exception:
            _stderr(f"[node_monitor] _enter_track failed for {name}")
            yield handle
            return

        exc_to_raise: BaseException | None = None
        try:
            yield handle
        except BaseException as e:
            exc_to_raise = e

        try:
            self._exit_track(state, entered_lifecycle, handle, t0, exc_to_raise, stage)
        except Exception:
            _stderr(f"[node_monitor] _exit_track failed for {name}")

        if exc_to_raise is not None:
            raise exc_to_raise

    def _enter_track(self, state: NodeState, lifecycle: str, stage: str) -> None:
        now = time.monotonic()
        if lifecycle == Lifecycle.REGISTERED:
            state.started_at = now
            state.lifecycle = Lifecycle.STARTING
            return

        if lifecycle in (Lifecycle.READY, Lifecycle.RUNNING_START, Lifecycle.RUNNING_END, Lifecycle.STALLED):
            state.last_progress_at = now
            state.lifecycle = Lifecycle.RUNNING_START

    def _exit_track(
        self,
        state: NodeState,
        entered_lifecycle: str,
        handle: TrackHandle,
        t0: float,
        exc: BaseException | None,
        stage: str,
    ) -> None:
        now = time.monotonic()
        elapsed_ms = (now - t0) * 1000

        if entered_lifecycle == Lifecycle.REGISTERED:
            if exc is None:
                state.lifecycle = Lifecycle.READY
            else:
                state.lifecycle = Lifecycle.FAILED
                state.last_error = repr(exc)
            return

        if entered_lifecycle not in (Lifecycle.READY, Lifecycle.RUNNING_START, Lifecycle.RUNNING_END, Lifecycle.STALLED):
            return

        state.lifecycle = Lifecycle.RUNNING_END
        state.last_progress_at = now

        if handle._skip_rolling:
            return

        stage_rc = state.stage_rollings.setdefault(stage, RollingCounter())

        if handle._input_n:
            state.rolling.record_input(handle._input_n, now=now)
            stage_rc.record_input(handle._input_n, now=now)
        if handle._output_n:
            state.rolling.record_output(handle._output_n, now=now)
            stage_rc.record_output(handle._output_n, now=now)

        if exc is not None:
            state.last_error = repr(exc)
            state.rolling.record_failure(now=now)
            stage_rc.record_failure(now=now)
            return

        state.rolling.record_success(
            latency_ms=elapsed_ms,
            window_ms=handle._window_ms,
            now=now,
        )
        stage_rc.record_success(
            latency_ms=elapsed_ms,
            window_ms=handle._window_ms,
            now=now,
        )

    def set_lifecycle(self, name: str, life: str, error: str | None = None) -> None:
        state = self._states.get(name)
        if state is None:
            self._warn_missing("set_lifecycle", name)
            return
        old = state.lifecycle
        state.lifecycle = life
        if error:
            state.last_error = error

    def set_detail(self, name: str, **fields) -> None:
        state = self._states.get(name)
        if state is None:
            self._warn_missing("set_detail", name)
            return
        state.detail.update(fields)

    def snapshot(self) -> list[dict]:
        return [s.to_dict() for s in self._states.values()]

    def snapshot_one(self, name: str) -> dict | None:
        state = self._states.get(name)
        if state is None:
            return None
        return state.to_dict()

    def get_state(self, name: str) -> NodeState | None:
        return self._states.get(name)

    def iter_states(self) -> list[NodeState]:
        return list(self._states.values())


def get_monitor() -> NodeMonitor:
    return NodeMonitor.get_instance()


def _stderr(msg: str) -> None:
    try:
        print(msg, file=sys.stderr, flush=True)
    except Exception:
        pass