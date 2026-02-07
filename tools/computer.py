from __future__ import annotations

import json
import os
import time
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional

from multimodal import capture_screenshot, ocr_find_text_boxes
from ui_automation import write_snapshot, find_uia_first
try:
    import pyautogui
except Exception:
    pyautogui = None

try:
    import pygetwindow as gw
except Exception:
    gw = None


@dataclass
class ComputerObservation:
    timestamp: float
    screenshot_path: str
    uia_path: Optional[str]
    active_window: str
    cursor: Dict[str, int]
    screenshot_size: int
    screenshot_hash: str = ""


class ComputerController:
    def __init__(self, app) -> None:
        self.app = app
        self.last_observation: Optional[ComputerObservation] = None
        self.selector_cache_path = os.path.join(self.app.settings.data_dir, "selector_cache.json")
        self.selector_cache: Dict[str, Any] = {}
        self._load_selector_cache()

    def _load_selector_cache(self) -> None:
        try:
            if os.path.exists(self.selector_cache_path):
                with open(self.selector_cache_path, "r", encoding="utf-8") as handle:
                    self.selector_cache = json.load(handle) or {}
        except Exception:
            self.selector_cache = {}

    def _save_selector_cache(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.selector_cache_path), exist_ok=True)
            with open(self.selector_cache_path, "w", encoding="utf-8") as handle:
                json.dump(self.selector_cache, handle, indent=2)
        except Exception:
            return

    def _active_window_title(self) -> str:
        if gw is None:
            return ""
        try:
            win = gw.getActiveWindow()
            return win.title if win else ""
        except Exception:
            return ""

    def _cache_key(self, backend: str, app_title: str, query: Dict[str, Any]) -> str:
        payload = {"backend": backend, "app_title": app_title, "query": query}
        return json.dumps(payload, sort_keys=True)

    def _resolve_desktop_target(self, params: Dict[str, Any]) -> Dict[str, Any]:
        x = params.get("x")
        y = params.get("y")
        if x is not None and y is not None:
            return {"x": x, "y": y, "source": "coords"}

        app_title = (self.last_observation.active_window if self.last_observation else "") or self._active_window_title()

        uia_query = params.get("uia_query")
        if isinstance(uia_query, dict):
            key = self._cache_key("desktop", app_title, uia_query)
            cached = self.selector_cache.get(key)
            if isinstance(cached, dict) and "x" in cached and "y" in cached:
                return {"x": cached["x"], "y": cached["y"], "source": "uia_cache"}
            rect = find_uia_first(uia_query)
            if rect:
                cx = int(rect["x"] + rect["w"] / 2)
                cy = int(rect["y"] + rect["h"] / 2)
                self.selector_cache[key] = {"x": cx, "y": cy, "rect": rect, "ts": time.time()}
                self._save_selector_cache()
                return {"x": cx, "y": cy, "source": "uia_query"}

        ocr_text = params.get("ocr_text")
        if ocr_text:
            obs = self.last_observation
            if obs is None or not obs.screenshot_path or not os.path.exists(obs.screenshot_path):
                obs = self.observe(os.path.join(self.app.settings.data_dir, "runs", "latest"))
            try:
                boxes = ocr_find_text_boxes(obs.screenshot_path, str(ocr_text))
            except Exception:
                boxes = []
            if boxes:
                box = boxes[0]
                cx = int(box["x"] + box["w"] / 2)
                cy = int(box["y"] + box["h"] / 2)
                return {"x": cx, "y": cy, "source": "ocr_text"}

        bbox = params.get("bbox")
        if isinstance(bbox, dict):
            try:
                cx = int(bbox["x"] + bbox["w"] / 2)
                cy = int(bbox["y"] + bbox["h"] / 2)
                return {"x": cx, "y": cy, "source": "bbox"}
            except Exception:
                pass

        raise RuntimeError("desktop action requires x,y or uia_query/ocr_text/bbox")

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
        screenshot_hash = ""
        try:
            screenshot_size = os.path.getsize(screenshot_path)
        except Exception:
            screenshot_size = 0
        try:
            with open(screenshot_path, "rb") as handle:
                screenshot_hash = hashlib.sha1(handle.read()).hexdigest()
        except Exception:
            screenshot_hash = ""
        cursor = {"x": 0, "y": 0}
        if pyautogui is not None:
            try:
                pos = pyautogui.position()
                cursor = {"x": int(pos.x), "y": int(pos.y)}
            except Exception:
                cursor = {"x": 0, "y": 0}
        obs = ComputerObservation(
            timestamp=time.time(),
            screenshot_path=screenshot_path,
            uia_path=uia_path,
            active_window=self._active_window_title(),
            cursor=cursor,
            screenshot_size=screenshot_size,
            screenshot_hash=screenshot_hash,
        )
        self.last_observation = obs
        return obs

    def _act_desktop(self, action: str, params: Dict[str, Any]) -> str:
        if pyautogui is None:
            raise RuntimeError("computer desktop backend requires pyautogui. Install with: pip install pyautogui")
        action = (action or "").strip().lower()
        if action == "click":
            target = self._resolve_desktop_target(params)
            x = target["x"]
            y = target["y"]
            pyautogui.click(x, y)
            return f"clicked at {x},{y} ({target.get('source')})"
        if action == "double_click":
            target = self._resolve_desktop_target(params)
            x = target["x"]
            y = target["y"]
            pyautogui.doubleClick(x, y)
            return f"double clicked at {x},{y} ({target.get('source')})"
        if action == "right_click":
            target = self._resolve_desktop_target(params)
            x = target["x"]
            y = target["y"]
            pyautogui.rightClick(x, y)
            return f"right clicked at {x},{y} ({target.get('source')})"
        if action == "move":
            target = self._resolve_desktop_target(params)
            x = target["x"]
            y = target["y"]
            pyautogui.moveTo(x, y)
            return f"moved to {x},{y} ({target.get('source')})"
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
                "screenshot_hash": obs.screenshot_hash,
            }
        if mode == "act":
            action = payload.get("action") or ""
            params = payload.get("params") or {}
            if "backend" not in params and payload.get("backend"):
                params["backend"] = payload.get("backend")
            result = self.act(action, params)
            return {"result": result}
        raise RuntimeError("computer requires mode observe|act")
