from __future__ import annotations

import json
from typing import Any, Dict, List

try:
    import requests
except Exception:
    requests = None


def detect(endpoint: str, image_path: str) -> List[Dict[str, Any]]:
    if requests is None:
        raise RuntimeError("requests not installed")
    with open(image_path, "rb") as handle:
        files = {"file": handle}
        resp = requests.post(endpoint, files=files, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"SOM endpoint returned {resp.status_code}")
    data = resp.json()
    if isinstance(data, dict):
        return data.get("boxes") or data.get("elements") or []
    if isinstance(data, list):
        return data
    return []


def save(endpoint: str, image_path: str, out_path: str) -> str:
    data = detect(endpoint, image_path)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    return out_path
