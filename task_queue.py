from __future__ import annotations

import queue
import threading
from typing import Callable


class TaskQueue:
    def __init__(self, max_size: int = 100) -> None:
        self._queue = queue.Queue(maxsize=max_size)
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def enqueue(self, fn: Callable[[], None]) -> None:
        self._queue.put(fn)

    def enqueue_and_wait(self, fn: Callable[[], None]) -> None:
        done = threading.Event()

        def wrapped():
            try:
                fn()
            finally:
                done.set()

        self._queue.put(wrapped)
        done.wait()

    def _run(self) -> None:
        while True:
            fn = self._queue.get()
            try:
                fn()
            finally:
                self._queue.task_done()
