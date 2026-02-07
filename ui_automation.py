from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

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


def _element_rect(element) -> Optional[Dict[str, int]]:
    try:
        rect = element.rectangle()
        return {"x": rect.left, "y": rect.top, "w": rect.width(), "h": rect.height()}
    except Exception:
        return None


def _match_element(element, query: Dict[str, Any]) -> bool:
    info = getattr(element, "element_info", None)
    name = ""
    control_type = ""
    automation_id = ""
    class_name = ""
    try:
        name = info.name or ""
        control_type = info.control_type or ""
        automation_id = info.automation_id or ""
        class_name = info.class_name or ""
    except Exception:
        pass
    q_name = (query.get("name") or "").strip().lower()
    q_role = (query.get("role") or query.get("control_type") or "").strip().lower()
    q_auto = (query.get("automation_id") or "").strip().lower()
    q_class = (query.get("class_name") or "").strip().lower()
    if q_name and q_name not in name.lower():
        return False
    if q_role and q_role not in control_type.lower():
        return False
    if q_auto and q_auto not in automation_id.lower():
        return False
    if q_class and q_class not in class_name.lower():
        return False
    return True


def find_uia(query: Dict[str, Any], limit: int = 50, depth: int = 3) -> List[Dict[str, Any]]:
    if Desktop is None:
        raise RuntimeError("pywinauto not installed")
    matches: List[Dict[str, Any]] = []
    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
        title_filter = (query.get("window_title") or "").strip().lower()
        for w in windows:
            try:
                if title_filter and title_filter not in (w.window_text() or "").lower():
                    continue
                if _match_element(w, query):
                    rect = _element_rect(w)
                    if rect:
                        matches.append(rect)
                for el in w.descendants(depth=depth):
                    if _match_element(el, query):
                        rect = _element_rect(el)
                        if rect:
                            matches.append(rect)
                            if len(matches) >= limit:
                                return matches
            except Exception:
                continue
    except Exception:
        return []
    return matches


def find_uia_first(query: Dict[str, Any]) -> Optional[Dict[str, int]]:
    results = find_uia(query, limit=1)
    return results[0] if results else None


def write_snapshot(path: str, limit: int = 200) -> str:
    data = snapshot_uia(limit=limit)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    return path
