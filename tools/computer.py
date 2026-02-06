from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from multimodal import capture_screenshot
from ui_automation import write_snapshot


@dataclass
class ComputerObservation:
    timestamp: float
    screenshot_path: str
    uia_path: Optional[str]
    active_window: str
    cursor: Dict[str, int]


class ComputerController:
    def __init__(self, app) -> None:
        self.app = app

    def observe(self, out_dir: str) -> ComputerObservation:
        os.makedirs(out_dir, exist_ok=True)
        stamp = time.strftime("%H%M%S")
        screenshot_path = os.path.join(out_dir, f"screen-{stamp}.png")
        capture_screenshot(screenshot_path)
        uia_path = None
        try:
            uia_path = os.path.join(out_dir, f"uia-{stamp}.json")
            write_snapshot(uia_path)
        except Exception:
            uia_path = None
        return ComputerObservation(
            timestamp=time.time(),
            screenshot_path=screenshot_path,
            uia_path=uia_path,
            active_window="",
            cursor={"x": 0, "y": 0},
        )

    def act(self, action: str, params: Dict[str, Any]) -> str:
        action = (action or "").strip().lower()
        if action == "click":
            selector = params.get("selector") or ""
            if not selector:
                raise RuntimeError("computer.click requires selector")
            self.app._execute_tool("click", selector)
            return f"clicked {selector}"
        if action == "type":
            selector = params.get("selector") or ""
            text = params.get("text") or ""
            self.app._execute_tool("type", f"{selector} | {text}")
            return f"typed into {selector}"
        if action == "press":
            key = params.get("key") or ""
            self.app._execute_tool("press", key)
            return f"pressed {key}"
        if action == "open":
            path = params.get("path") or ""
            self.app._execute_tool("open", path)
            return f"opened {path}"
        raise RuntimeError(f"computer.act unsupported action: {action}")

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mode = payload.get("mode") or "observe"
        out_dir = payload.get("out_dir") or os.path.join(self.app.settings.data_dir, "runs", "latest")
        if mode == "observe":
            obs = self.observe(out_dir)
            return {
                "timestamp": obs.timestamp,
                "screenshot": obs.screenshot_path,
                "uia": obs.uia_path,
                "active_window": obs.active_window,
                "cursor": obs.cursor,
            }
        if mode == "act":
            action = payload.get("action") or ""
            params = payload.get("params") or {}
            result = self.act(action, params)
            return {"result": result}
        raise RuntimeError("computer requires mode observe|act")
