from __future__ import annotations

import base64
import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import pyautogui
except Exception:
    pyautogui = None

try:
    import keyboard
except Exception:
    keyboard = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from multimodal import capture_screenshot_with_grid, encode_image_data_url


@dataclass
class VLAState:
    goal: str = ""
    last_action: str = ""
    last_reason: str = ""
    last_image: str = ""
    running: bool = False
    paused: bool = False


def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    payload = text[start : end + 1]
    try:
        return json.loads(payload)
    except Exception:
        return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


class VisionModel:
    def __init__(self, model: str, api_key: Optional[str] = None, base_url: Optional[str] = None):
        if OpenAI is None:
            raise RuntimeError("openai package not installed")
        kwargs: Dict[str, Any] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self._model = model

    def decide(self, prompt: str, image_path: str) -> str:
        data_url = encode_image_data_url(image_path)
        resp = self._client.responses.create(
            model=self._model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
        )
        text = getattr(resp, "output_text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
        try:
            output = resp.output  # type: ignore[attr-defined]
        except Exception:
            output = None
        if isinstance(output, list):
            parts = []
            for item in output:
                content = item.get("content") if isinstance(item, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "output_text":
                        parts.append(block.get("text", ""))
            if parts:
                return "\n".join(p for p in parts if p).strip()
        return ""


class LiveDriver:
    def __init__(self, app, data_dir: str):
        self.app = app
        self.data_dir = data_dir
        self.state = VLAState()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._model: Optional[VisionModel] = None
        self._load_model()

    def _load_model(self) -> None:
        model = os.getenv("AGENTIC_VLA_MODEL", "").strip()
        if not model:
            return
        try:
            self._model = VisionModel(
                model=model,
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL"),
            )
        except Exception as exc:
            self.app.log_line(f"VLA: vision model unavailable: {exc}")
            self._model = None

    def set_goal(self, goal: str) -> None:
        self.state.goal = goal.strip()
        self.app.log_line(f"VLA goal set: {self.state.goal}")

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            self.app.log_line("VLA already running.")
            return
        self._stop.clear()
        self.state.running = True
        self.state.paused = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.app.log_line("VLA live loop started.")

    def stop(self) -> None:
        self._stop.set()
        self.state.running = False
        self.app.log_line("VLA live loop stopped.")

    def pause(self) -> None:
        self.state.paused = True
        self.app.log_line("VLA paused.")

    def resume(self) -> None:
        self.state.paused = False
        self.app.log_line("VLA resumed.")

    def status(self) -> Dict[str, Any]:
        return {
            "running": self.state.running,
            "paused": self.state.paused,
            "goal": self.state.goal,
            "last_action": self.state.last_action,
            "last_reason": self.state.last_reason,
            "last_image": self.state.last_image,
        }

    def _loop(self) -> None:
        if pyautogui is None:
            self.app.log_line("VLA requires pyautogui; install it to enable live control.")
            self.state.running = False
            return
        if not self._model:
            self.app.log_line("VLA requires AGENTIC_VLA_MODEL and OpenAI SDK to run.")
            self.state.running = False
            return

        interval = float(os.getenv("AGENTIC_VLA_INTERVAL", "1.0"))
        grid_size = int(os.getenv("AGENTIC_VLA_GRID", "6"))
        actions_env = os.getenv("AGENTIC_VLA_ACTIONS", "").strip()
        allowed_actions = [a.strip().lower() for a in actions_env.split(",") if a.strip()] or [
            "click",
            "scroll",
            "wait",
            "stop",
        ]
        read_only = _parse_bool(os.getenv("AGENTIC_VLA_READONLY", "true"), True)
        pause_key = os.getenv("AGENTIC_VLA_PAUSE_KEY", "f9").strip().lower()
        pause_file = os.path.join(self.data_dir, "vla.pause")
        stop_file = os.path.join(self.data_dir, "vla.stop")
        os.makedirs(os.path.join(self.data_dir, "vla"), exist_ok=True)

        while not self._stop.is_set():
            if self.state.paused or self.app.pause_event.is_set():
                time.sleep(0.5)
                continue
            if keyboard and pause_key:
                try:
                    if keyboard.is_pressed(pause_key):
                        self.app.log_line(f"VLA paused via hotkey {pause_key}.")
                        self.state.paused = True
                        time.sleep(0.5)
                        continue
                except Exception:
                    pass
            if os.path.exists(stop_file):
                try:
                    os.remove(stop_file)
                except Exception:
                    pass
                break
            if os.path.exists(pause_file):
                time.sleep(0.5)
                continue

            stamp = str(int(time.time()))
            image_path = os.path.join(self.data_dir, "vla", f"screen-{stamp}.png")
            try:
                capture_screenshot_with_grid(image_path, grid_size=grid_size)
            except Exception as exc:
                self.app.log_line(f"VLA capture failed: {exc}")
                time.sleep(interval)
                continue
            self.state.last_image = image_path

            prompt = self._build_prompt(grid_size)
            reply = ""
            try:
                reply = self._model.decide(prompt, image_path)
            except Exception as exc:
                self.app.log_line(f"VLA model error: {exc}")
                time.sleep(interval)
                continue

            action = _extract_json(reply)
            if not action:
                self.app.log_line("VLA: no action parsed.")
                time.sleep(interval)
                continue

            act = str(action.get("action", "")).lower()
            reason = str(action.get("reason", "")).strip()
            if act not in allowed_actions:
                self.app.log_line(f"VLA: action '{act}' not allowed.")
                time.sleep(interval)
                continue

            if read_only and act in ("type", "key", "hotkey"):
                self.app.log_line("VLA: read-only mode blocked keyboard action.")
                time.sleep(interval)
                continue

            self.state.last_action = act
            self.state.last_reason = reason

            if act == "stop":
                self.app.log_line("VLA: stop requested by model.")
                break

            try:
                self._execute_action(action, grid_size)
            except Exception as exc:
                self.app.log_line(f"VLA action failed: {exc}")
            time.sleep(interval)

        self.state.running = False
        self.app.log_line("VLA loop exited.")

    def _build_prompt(self, grid_size: int) -> str:
        goal = self.state.goal or "Observe the screen and take the next helpful action."
        return (
            "You are a visual control agent. Use the screenshot to choose the next action. "
            "The screen is overlaid with a numbered grid of size {grid}x{grid}. "
            "Cells are numbered left-to-right, top-to-bottom starting at 1. "
            "Return ONLY valid JSON. Allowed actions: click, scroll, wait, stop, type, key, hotkey. "
            "Prefer using `cell` (grid cell number). If precise pixel coordinates are required, use x and y. "
            "JSON schema: {\"action\":\"click|scroll|wait|stop|type|key|hotkey\",\"cell\":int,"
            "\"x\":int,\"y\":int,\"scroll\":int,\"text\":string,\"key\":string,\"hotkey\":[string],\"reason\":string}.\n"
            f"Goal: {goal}"
        ).format(grid=grid_size)

    def _execute_action(self, action: Dict[str, Any], grid_size: int) -> None:
        act = str(action.get("action", "")).lower()
        if pyautogui is None:
            raise RuntimeError("pyautogui not installed")
        width, height = pyautogui.size()

        x = _safe_float(action.get("x"))
        y = _safe_float(action.get("y"))
        cell = action.get("cell")
        if (x is None or y is None) and cell is not None:
            try:
                cell_idx = int(cell)
                if cell_idx > 0:
                    idx = cell_idx - 1
                    row = idx // grid_size
                    col = idx % grid_size
                    cell_w = width / grid_size
                    cell_h = height / grid_size
                    x = int((col + 0.5) * cell_w)
                    y = int((row + 0.5) * cell_h)
            except Exception:
                pass

        if act == "click" and x is not None and y is not None:
            pyautogui.click(int(x), int(y))
            return
        if act == "scroll":
            amount = int(_safe_float(action.get("scroll")) or 0)
            if amount == 0:
                amount = -300
            pyautogui.scroll(amount)
            return
        if act == "wait":
            time.sleep(0.5)
            return
        if act == "type":
            text = str(action.get("text", ""))
            if text:
                pyautogui.typewrite(text)
            return
        if act == "key":
            key = str(action.get("key", ""))
            if key:
                pyautogui.press(key)
            return
        if act == "hotkey":
            keys = action.get("hotkey")
            if isinstance(keys, list) and keys:
                pyautogui.hotkey(*[str(k) for k in keys])
            return
