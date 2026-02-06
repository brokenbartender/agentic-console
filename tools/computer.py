from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from multimodal import capture_screenshot
from ui_automation import write_snapshot
try:
    import pyautogui
except Exception:
    pyautogui = None


@dataclass
class ComputerObservation:
    timestamp: float
    screenshot_path: str
    uia_path: Optional[str]
    active_window: str
    cursor: Dict[str, int]
    screenshot_size: int


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
        screenshot_size = 0
        try:
            screenshot_size = os.path.getsize(screenshot_path)
        except Exception:
            screenshot_size = 0
        cursor = {"x": 0, "y": 0}
        if pyautogui is not None:
            try:
                pos = pyautogui.position()
                cursor = {"x": int(pos.x), "y": int(pos.y)}
            except Exception:
                cursor = {"x": 0, "y": 0}
        return ComputerObservation(
            timestamp=time.time(),
            screenshot_path=screenshot_path,
            uia_path=uia_path,
            active_window="",
            cursor=cursor,
            screenshot_size=screenshot_size,
        )

    def _act_desktop(self, action: str, params: Dict[str, Any]) -> str:
        if pyautogui is None:
            raise RuntimeError("computer desktop backend requires pyautogui. Install with: pip install pyautogui")
        action = (action or "").strip().lower()
        if action == "click":
            x = params.get("x")
            y = params.get("y")
            if x is None or y is None:
                raise RuntimeError("computer.click desktop requires x,y")
            pyautogui.click(x, y)
            return f"clicked at {x},{y}"
        if action == "double_click":
            x = params.get("x")
            y = params.get("y")
            if x is None or y is None:
                raise RuntimeError("computer.double_click desktop requires x,y")
            pyautogui.doubleClick(x, y)
            return f"double clicked at {x},{y}"
        if action == "right_click":
            x = params.get("x")
            y = params.get("y")
            if x is None or y is None:
                raise RuntimeError("computer.right_click desktop requires x,y")
            pyautogui.rightClick(x, y)
            return f"right clicked at {x},{y}"
        if action == "move":
            x = params.get("x")
            y = params.get("y")
            if x is None or y is None:
                raise RuntimeError("computer.move desktop requires x,y")
            pyautogui.moveTo(x, y)
            return f"moved to {x},{y}"
        if action == "scroll":
            amount = int(params.get("amount") or 0)
            pyautogui.scroll(amount)
            return f"scrolled {amount}"
        if action == "type":
            text = params.get("text") or ""
            pyautogui.typewrite(str(text))
            return "typed text"
        if action == "press":
            key = params.get("key") or ""
            if not key:
                raise RuntimeError("computer.press desktop requires key")
            pyautogui.press(str(key))
            return f"pressed {key}"
        raise RuntimeError(f"computer.act unsupported desktop action: {action}")

    def _act_browser(self, action: str, params: Dict[str, Any]) -> str:
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
        raise RuntimeError(f"computer.act unsupported browser action: {action}")

    def act(self, action: str, params: Dict[str, Any]) -> str:
        backend = (params.get("backend") or "browser").strip().lower()
        if backend == "desktop":
            return self._act_desktop(action, params)
        return self._act_browser(action, params)

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
                "screenshot_size": obs.screenshot_size,
            }
        if mode == "act":
            action = payload.get("action") or ""
            params = payload.get("params") or {}
            if "backend" not in params and payload.get("backend"):
                params["backend"] = payload.get("backend")
            result = self.act(action, params)
            return {"result": result}
        raise RuntimeError("computer requires mode observe|act")
