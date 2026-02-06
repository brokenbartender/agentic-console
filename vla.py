from __future__ import annotations

import base64
import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    import pyautogui
except Exception:
    pyautogui = None

try:
    from PIL import Image
except Exception:
    Image = None

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
    last_dom: list = field(default_factory=list)
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
            "last_dom_elements": len(self.state.last_dom),
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
        mode = os.getenv("AGENTIC_VLA_MODE", "auto").strip().lower()
        actions_env = os.getenv("AGENTIC_VLA_ACTIONS", "").strip()
        allowed_actions = [a.strip().lower() for a in actions_env.split(",") if a.strip()] or [
            "click",
            "scroll",
            "wait",
            "stop",
        ]
        read_only = _parse_bool(os.getenv("AGENTIC_VLA_READONLY", "true"), True)
        stitch_desktop = _parse_bool(os.getenv("AGENTIC_VLA_STITCH", "false"), False)
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
            web_mode = False
            if mode in ("auto", "browser", "web"):
                if getattr(self.app, "page", None) is not None:
                    try:
                        dom = self._capture_web_state(image_path)
                        web_mode = True
                    except Exception as exc:
                        self.app.log_line(f"VLA web capture failed: {exc}")
                        dom = []
                else:
                    dom = []
            else:
                dom = []

            if not web_mode:
                try:
                    if stitch_desktop:
                        image_path = self._capture_desktop_stitch(image_path, grid_size=grid_size)
                    else:
                        capture_screenshot_with_grid(image_path, grid_size=grid_size)
                except Exception as exc:
                    self.app.log_line(f"VLA capture failed: {exc}")
                    time.sleep(interval)
                    continue

            self.state.last_image = image_path
            self.state.last_dom = dom or []

            prompt = self._build_prompt(grid_size, dom, web_mode)
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
                self._execute_action(action, grid_size, web_mode)
            except Exception as exc:
                self.app.log_line(f"VLA action failed: {exc}")
            time.sleep(interval)

        self.state.running = False
        self.app.log_line("VLA loop exited.")

    def _capture_web_state(self, image_path: str) -> list:
        page = getattr(self.app, "page", None)
        if page is None:
            raise RuntimeError("No Playwright page available")
        try:
            page.screenshot(path=image_path, full_page=True)
        except Exception:
            page.screenshot(path=image_path)
        dom = self._snapshot_dom(page)
        return dom

    def _snapshot_dom(self, page) -> list:
        script = """
(() => {
  const nodes = [];
  const selectors = [
    'a','button','input','select','textarea',
    '[role=button]','[role=link]','[onclick]'
  ];
  const elements = Array.from(document.querySelectorAll(selectors.join(',')));
  let id = 1;
  for (const el of elements) {
    const rect = el.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) continue;
    const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
    const item = {
      element_id: id++,
      tag: el.tagName.toLowerCase(),
      text: text.slice(0, 120),
      aria: (el.getAttribute('aria-label') || '').slice(0, 120),
      href: (el.getAttribute('href') || '').slice(0, 200),
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      w: Math.round(rect.width),
      h: Math.round(rect.height),
    };
    nodes.push(item);
    if (nodes.length >= 200) break;
  }
  return nodes;
})();
"""
        try:
            return page.evaluate(script)
        except Exception:
            return []

    def _click_dom_element(self, element_id: int) -> None:
        page = getattr(self.app, "page", None)
        if page is None:
            raise RuntimeError("No Playwright page available")
        try:
            idx = int(element_id)
        except Exception:
            return
        script = """
(elementId) => {
  const selectors = [
    'a','button','input','select','textarea',
    '[role=button]','[role=link]','[onclick]'
  ];
  const elements = Array.from(document.querySelectorAll(selectors.join(',')));
  let id = 1;
  for (const el of elements) {
    const rect = el.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) continue;
    if (id === elementId) {
      try { el.scrollIntoView({block:'center'}); } catch (e) {}
      el.click();
      return true;
    }
    id++;
  }
  return false;
}
"""
        page.evaluate(script, idx)

    def _capture_desktop_stitch(self, base_path: str, grid_size: int = 6) -> str:
        if pyautogui is None or Image is None:
            capture_screenshot_with_grid(base_path, grid_size=grid_size)
            return base_path
        stitch_dir = os.path.join(self.data_dir, "vla")
        os.makedirs(stitch_dir, exist_ok=True)
        frames = []
        for i in range(3):
            path = base_path.replace(".png", f"-part{i}.png")
            capture_screenshot_with_grid(path, grid_size=grid_size)
            frames.append(path)
            try:
                pyautogui.scroll(-800)
            except Exception:
                pass
            time.sleep(0.4)
        try:
            images = [Image.open(p) for p in frames]
            widths, heights = zip(*(im.size for im in images))
            total_height = sum(heights)
            max_width = max(widths)
            stitched = Image.new("RGB", (max_width, total_height))
            y = 0
            for im in images:
                stitched.paste(im, (0, y))
                y += im.size[1]
            stitched.save(base_path)
        except Exception:
            capture_screenshot_with_grid(base_path, grid_size=grid_size)
        return base_path
    def _build_prompt(self, grid_size: int, dom: list, web_mode: bool) -> str:
        goal = self.state.goal or "Observe the screen and take the next helpful action."
        dom_text = ""
        if dom:
            try:
                dom_text = json.dumps(dom[:200])
            except Exception:
                dom_text = ""
        dom_hint = ""
        if dom_text:
            dom_hint = (
                "\nDOM_HINT: You also have a simplified DOM list with bounding boxes. "
                "Prefer using element_id from DOM_HINT when clicking."
                f"\nDOM_HINT={dom_text}"
            )
        return (
            "You are a visual control agent. Use the screenshot to choose the next action. "
            "The screen is overlaid with a numbered grid of size {grid}x{grid} (desktop mode). "
            "Cells are numbered left-to-right, top-to-bottom starting at 1. "
            "Return ONLY valid JSON. Allowed actions: click, scroll, wait, stop, type, key, hotkey. "
            "Prefer using `element_id` (web) or `cell` (desktop). If precise pixel coordinates are required, use x and y. "
            "JSON schema: {\"action\":\"click|scroll|wait|stop|type|key|hotkey\",\"cell\":int,"
            "\"x\":int,\"y\":int,\"scroll\":int,\"text\":string,\"key\":string,\"hotkey\":[string],"
            "\"element_id\":int,\"reason\":string}.\n"
            f"Goal: {goal}"
        ).format(grid=grid_size)
        + dom_hint

    def _execute_action(self, action: Dict[str, Any], grid_size: int, web_mode: bool) -> None:
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

        if act == "click":
            element_id = action.get("element_id")
            if web_mode and element_id is not None:
                self._click_dom_element(element_id)
                return
            if x is not None and y is not None:
                if web_mode and getattr(self.app, "page", None) is not None:
                    try:
                        self.app.page.mouse.click(int(x), int(y))
                        return
                    except Exception:
                        pass
                pyautogui.click(int(x), int(y))
                return
        if act == "scroll":
            amount = int(_safe_float(action.get("scroll")) or 0)
            if amount == 0:
                amount = -300
            if web_mode and getattr(self.app, "page", None) is not None:
                try:
                    self.app.page.mouse.wheel(0, amount)
                    return
                except Exception:
                    pass
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
