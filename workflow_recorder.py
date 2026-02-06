from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional


class WorkflowRecorder:
    def __init__(self, data_dir: str) -> None:
        self.data_dir = data_dir
        self.workflow_dir = os.path.join(data_dir, "workflows")
        os.makedirs(self.workflow_dir, exist_ok=True)
        self._active_name: Optional[str] = None
        self._steps: List[Dict] = []

    def start(self, name: str) -> None:
        self._active_name = name
        self._steps = []

    def stop(self) -> Optional[str]:
        if not self._active_name:
            return None
        payload = {
            "name": self._active_name,
            "created_at": time.time(),
            "steps": self._steps,
        }
        path = os.path.join(self.workflow_dir, f"{self._active_name}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        name = self._active_name
        self._active_name = None
        self._steps = []
        return name

    def record_step(self, command: str, status: str = "run") -> None:
        if not self._active_name:
            return
        self._steps.append({"type": "step", "command": command, "status": status, "ts": time.time()})

    def record_tool(self, name: str, args: str, status: str = "call") -> None:
        if not self._active_name:
            return
        self._steps.append({"type": "tool", "name": name, "args": args, "status": status, "ts": time.time()})

    def load(self, name: str) -> Optional[Dict]:
        path = os.path.join(self.workflow_dir, f"{name}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def list(self) -> List[str]:
        if not os.path.exists(self.workflow_dir):
            return []
        return sorted([os.path.splitext(p)[0] for p in os.listdir(self.workflow_dir) if p.endswith(".json")])
