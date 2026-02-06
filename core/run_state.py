from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List

from memory import MemoryStore


def list_run_dirs(base: str) -> List[str]:
    if not os.path.isdir(base):
        return []
    dirs = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
    dirs.sort(reverse=True)
    return dirs


def load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def summarize_run(run_dir: str) -> Dict[str, Any]:
    plan = load_json(os.path.join(run_dir, "plan.json"))
    report = load_json(os.path.join(run_dir, "report.json"))
    return {
        "run_id": os.path.basename(run_dir),
        "goal": plan.get("goal", ""),
        "status": report.get("status", ""),
        "updated_at": report.get("ended_at", 0.0),
    }
