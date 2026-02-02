from __future__ import annotations

import threading
import time


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters = {}
        self._timers = {}

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def set_timer(self, name: str, seconds: float) -> None:
        with self._lock:
            self._timers[name] = seconds

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "timers": dict(self._timers),
                "timestamp": time.time(),
            }
