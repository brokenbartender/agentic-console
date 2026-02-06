from __future__ import annotations

import os
import threading
from typing import Callable

from memory import MemoryStore
from metrics import Metrics
from task_queue import TaskQueue
from rag import RagStore
from graph_rag import GraphStore
from research_store import ResearchStore
from job_store import JobStore
from a2a import A2ABus
from a2a_network import A2ANetwork


class AgentEngine:
    def __init__(self, settings, on_message=None, log_cb: Callable[[str], None] | None = None) -> None:
        self.settings = settings
        self.log_cb = log_cb
        self.memory = MemoryStore(settings.memory_db, settings.embedding_dim)
        self.metrics = Metrics()
        self.task_queue = TaskQueue(settings.task_queue_size)
        self.rag = RagStore(self.memory)
        self.graph = GraphStore(self.memory._conn)
        self.research = ResearchStore(self.memory._conn)
        self.jobs = JobStore(self.memory._conn)
        self.a2a = A2ABus(self.memory)
        self.a2a_net = A2ANetwork(
            self.a2a,
            self.settings.a2a_host,
            self.settings.a2a_port,
            self.settings.a2a_shared_secret,
            self.settings.a2a_peers,
            on_message=on_message,
        )
        self._memory_prune_stop = threading.Event()

    def start_a2a(self) -> None:
        if str(self.settings.a2a_listen).lower() in ("1", "true", "yes", "on"):
            try:
                self.a2a_net.start()
                self._log(f"A2A network listening on http://{self.settings.a2a_host}:{self.settings.a2a_port}/a2a")
            except Exception:
                self._log("A2A network failed to start.")

    def _log(self, msg: str) -> None:
        if self.log_cb:
            self.log_cb(msg)


def run_headless(settings, on_message=None):
    engine = AgentEngine(settings, on_message=on_message, log_cb=print)
    engine.start_a2a()
    print("Headless engine running. Ctrl+C to exit.")
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        pass
