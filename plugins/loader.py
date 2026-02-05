from __future__ import annotations

import json
import os
from typing import Dict, Any


DENYLIST_PATH = os.path.join(os.path.dirname(__file__), "denylist.json")


def load_denylist() -> set[str]:
    if not os.path.exists(DENYLIST_PATH):
        return set()
    try:
        with open(DENYLIST_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return set(data.get("denied", []))
    except Exception:
        return set()


def validate_manifest(manifest: Dict[str, Any]) -> None:
    required = ["name", "version", "capabilities"]
    for key in required:
        if key not in manifest:
            raise RuntimeError(f"Plugin manifest missing: {key}")


def load_manifest(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    validate_manifest(manifest)
    return manifest
