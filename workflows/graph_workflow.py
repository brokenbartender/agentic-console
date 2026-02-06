from __future__ import annotations

import json
import sqlite3
import time
from typing import Callable, Dict, Any, List


class Checkpointer:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init()

    def _init(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS checkpoints (id TEXT PRIMARY KEY, state TEXT, updated_at REAL)"
        )
        conn.commit()
        conn.close()

    def save(self, key: str, state: Dict[str, Any]) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO checkpoints (id, state, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(state), time.time()),
        )
        conn.commit()
        conn.close()

    def load(self, key: str) -> Dict[str, Any] | None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT state FROM checkpoints WHERE id=?", (key,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except Exception:
            return None


class StateGraph:
    def __init__(self) -> None:
        self.nodes: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self.edges: Dict[str, List[str]] = {}

    def add_node(self, name: str, fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        self.nodes[name] = fn
        self.edges.setdefault(name, [])

    def add_edge(self, src: str, dst: str) -> None:
        self.edges.setdefault(src, []).append(dst)

    def run(self, start: str, state: Dict[str, Any], checkpointer: Checkpointer | None = None, key: str = "") -> Dict[str, Any]:
        current = start
        while True:
            fn = self.nodes.get(current)
            if not fn:
                break
            state = fn(state)
            if checkpointer and key:
                checkpointer.save(key, {"current": current, "state": state})
            nexts = self.edges.get(current, [])
            if not nexts:
                break
            current = nexts[0]
        return state
