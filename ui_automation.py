from __future__ import annotations

import json
import os
from typing import Any, Dict, List

try:
    from pywinauto import Desktop
except Exception:
    Desktop = None


def snapshot_uia(limit: int = 200) -> List[Dict[str, Any]]:
    if Desktop is None:
        raise RuntimeError("pywinauto not installed")
    nodes: List[Dict[str, Any]] = []
    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
        for w in windows:
            try:
                rect = w.rectangle()
                nodes.append(
                    {
                        "type": "window",
                        "title": w.window_text(),
                        "x": rect.left,
                        "y": rect.top,
                        "w": rect.width(),
                        "h": rect.height(),
                    }
                )
                if len(nodes) >= limit:
                    break
            except Exception:
                continue
    except Exception:
        return []
    return nodes


def write_snapshot(path: str, limit: int = 200) -> str:
    data = snapshot_uia(limit=limit)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    return path
