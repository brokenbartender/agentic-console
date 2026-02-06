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
    from PIL import ImageDraw
except Exception:
    ImageDraw = None

try:
    import keyboard
except Exception:
    keyboard = None

try:
    import requests
except Exception:
    requests = None

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
    last_som: list = field(default_factory=list)
    last_frames: list = field(default_factory=list)
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

    def decide(self, prompt: str, image_path: str, extra_images: Optional[list] = None) -> str:
        data_url = encode_image_data_url(image_path)
        content = [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": data_url},
        ]
        if extra_images:
            for path in extra_images[:5]:
                try:
                    content.append({"type": "input_image", "image_url": encode_image_data_url(path)})
                except Exception:
                    continue
        resp = self._client.responses.create(
            model=self._model,
            input=[{"role": "user", "content": content}],
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
            "last_som_elements": len(self.state.last_som),
            "last_frames": len(self.state.last_frames),
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
        som_endpoint = os.getenv("AGENTIC_SOM_ENDPOINT", "").strip()
        som_overlay = _parse_bool(os.getenv("AGENTIC_SOM_OVERLAY", "false"), False)
        frames = max(1, int(os.getenv("AGENTIC_VLA_FRAMES", "1")))
        tiles = max(1, int(os.getenv("AGENTIC_VLA_TILES", "1")))
        explore = _parse_bool(os.getenv("AGENTIC_VLA_EXPLORE", "false"), False)
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
            self.state.last_frames = []

            extra_images = self._capture_temporal_frames(image_path, frames, web_mode)
            if extra_images:
                self.state.last_frames = list(extra_images)

            if tiles > 1:
                extra_images.extend(self._tile_image(image_path, tiles))

            som = []
            if som_endpoint:
                som = self._som_detect(som_endpoint, image_path)
            self.state.last_som = som or []
            if som_overlay and som:
                try:
                    self._draw_som_overlay(image_path, som)
                except Exception:
                    pass

            prompt = self._build_prompt(grid_size, dom, som, web_mode)
            reply = ""
            try:
                reply = self._model.decide(prompt, image_path, extra_images=extra_images)
            except Exception as exc:
                self.app.log_line(f"VLA model error: {exc}")
                time.sleep(interval)
                continue

            action = _extract_json(reply)
            if not action:
                if explore:
                    self._execute_action({"action": "scroll", "scroll": -400}, grid_size, web_mode)
                else:
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

    def _capture_temporal_frames(self, base_path: str, frames: int, web_mode: bool) -> list:
        if frames <= 1:
            return []
        extra = []
        for i in range(frames - 1):
            path = base_path.replace(".png", f"-t{i}.png")
            try:
                if web_mode and getattr(self.app, "page", None) is not None:
                    try:
                        self.app.page.screenshot(path=path, full_page=True)
                    except Exception:
                        self.app.page.screenshot(path=path)
                else:
                    capture_screenshot_with_grid(path)
                extra.append(path)
            except Exception:
                continue
            time.sleep(0.25)
        return extra

    def _tile_image(self, path: str, tiles: int) -> list:
        if Image is None or tiles <= 1:
            return []
        try:
            img = Image.open(path)
        except Exception:
            return []
        w, h = img.size
        cols = tiles
        rows = tiles
        tw = w // cols
        th = h // rows
        out = []
        idx = 0
        for r in range(rows):
            for c in range(cols):
                left = c * tw
                top = r * th
                right = w if c == cols - 1 else (c + 1) * tw
                bottom = h if r == rows - 1 else (r + 1) * th
                crop = img.crop((left, top, right, bottom))
                tile_path = path.replace(".png", f"-tile{idx}.png")
                crop.save(tile_path)
                out.append(tile_path)
                idx += 1
        return out

    def _som_detect(self, endpoint: str, image_path: str) -> list:
        if requests is None:
            return []
        try:
            with open(image_path, "rb") as handle:
                files = {"file": handle}
                resp = requests.post(endpoint, files=files, timeout=10)
            if resp.status_code != 200:
                return []
            data = resp.json()
            if isinstance(data, dict):
                return data.get("boxes") or data.get("elements") or []
            if isinstance(data, list):
                return data
        except Exception:
            return []
        return []

    def _snapshot_dom(self, page) -> list:
        script = """
(() => {
  const nodes = [];
  const selectors = [
    'a','button','input','select','textarea',
    '[role=button]','[role=link]','[onclick]'
  ];
  let id = 1;

  function collect(root) {
    if (!root) return;
    const elements = Array.from(root.querySelectorAll(selectors.join(',')));
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
      if (nodes.length >= 200) return;
    }
    const all = root.querySelectorAll('*');
    for (const el of all) {
      if (nodes.length >= 200) return;
      if (el.shadowRoot) collect(el.shadowRoot);
      if (el.tagName === 'IFRAME') {
        try {
          const doc = el.contentDocument;
          if (doc) collect(doc);
        } catch (e) {}
      }
    }
  }

  collect(document);
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
        if self._is_blocked_element(idx):
            self.app.log_line(f"VLA: blocked click on element {idx} (blacklist).")
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

    def _click_dom_at_point(self, x: int, y: int) -> bool:
        page = getattr(self.app, "page", None)
        if page is None:
            return False
        script = """
(x, y) => {
  const el = document.elementFromPoint(x, y);
  if (!el) return null;
  const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().toLowerCase();
  return { tag: el.tagName ? el.tagName.toLowerCase() : '', text };
}
"""
        try:
            info = page.evaluate(script, x, y)
            if not isinstance(info, dict):
                return False
            if self._is_blocked_text(info.get("text", "")):
                self.app.log_line("VLA: blocked click at point (blacklist).")
                return True
            page.mouse.click(int(x), int(y))
            return True
        except Exception:
            return False

    def _is_blocked_text(self, text: str) -> bool:
        blocklist = os.getenv(
            "AGENTIC_DOM_BLOCKLIST",
            "delete,remove,close,sign out,logout,log out,unsubscribe,drop,format,wipe",
        )
        lowered = (text or "").lower()
        for term in [t.strip().lower() for t in blocklist.split(",") if t.strip()]:
            if term and term in lowered:
                return True
        return False

    def _is_blocked_element(self, element_id: int) -> bool:
        for item in self.state.last_dom:
            if not isinstance(item, dict):
                continue
            if int(item.get("element_id", -1)) != int(element_id):
                continue
            text = " ".join(
                [
                    str(item.get("text", "")),
                    str(item.get("aria", "")),
                    str(item.get("href", "")),
                ]
            )
            return self._is_blocked_text(text)
        return False

    def _draw_som_overlay(self, image_path: str, som: list) -> None:
        if Image is None or ImageDraw is None:
            return
        try:
            img = Image.open(image_path)
            draw = ImageDraw.Draw(img)
            for item in som:
                if not isinstance(item, dict):
                    continue
                box = item.get("box") if isinstance(item.get("box"), dict) else {}
                bx = item.get("x", box.get("x"))
                by = item.get("y", box.get("y"))
                bw = item.get("w", box.get("w"))
                bh = item.get("h", box.get("h"))
                label = item.get("label_id") or item.get("id") or item.get("index")
                if bx is None or by is None or bw is None or bh is None:
                    continue
                x1, y1 = float(bx), float(by)
                x2, y2 = x1 + float(bw), y1 + float(bh)
                draw.rectangle([x1, y1, x2, y2], outline=(0, 255, 0), width=2)
                if label is not None:
                    draw.text((x1 + 2, y1 + 2), str(label), fill=(0, 255, 0))
            img.save(image_path)
        except Exception:
            return

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
    def _build_prompt(self, grid_size: int, dom: list, som: list, web_mode: bool) -> str:
        goal = self.state.goal or "Observe the screen and take the next helpful action."
        dom_text = ""
        if dom:
            try:
                dom_text = json.dumps(dom[:200])
            except Exception:
                dom_text = ""
        som_text = ""
        if som:
            try:
                som_text = json.dumps(som[:200])
            except Exception:
                som_text = ""
        dom_hint = ""
        if dom_text:
            dom_hint = (
                "\nDOM_HINT: You also have a simplified DOM list with bounding boxes. "
                "Prefer using element_id from DOM_HINT when clicking."
                f"\nDOM_HINT={dom_text}"
            )
        som_hint = ""
        if som_text:
            som_hint = (
                "\nSOM_HINT: You also have visual element boxes with labels. "
                "Prefer using label_id from SOM_HINT when clicking."
                f"\nSOM_HINT={som_text}"
            )
        prompt = (
            "You are a visual control agent. Use the screenshot to choose the next action. "
            "The screen is overlaid with a numbered grid of size {grid}x{grid} (desktop mode). "
            "Cells are numbered left-to-right, top-to-bottom starting at 1. "
            "Return ONLY valid JSON. Allowed actions: click, scroll, wait, stop, type, key, hotkey. "
            "Prefer using `element_id` (web) or `cell` (desktop). If precise pixel coordinates are required, use x and y. "
            "JSON schema: {\"action\":\"click|scroll|wait|stop|type|key|hotkey\",\"cell\":int,"
            "\"x\":int,\"y\":int,\"scroll\":int,\"text\":string,\"key\":string,\"hotkey\":[string],"
            "\"element_id\":int,\"label_id\":int,\"reason\":string}.\n"
            f"Goal: {goal}"
        ).format(grid=grid_size)
        return prompt + dom_hint + som_hint

    def _execute_action(self, action: Dict[str, Any], grid_size: int, web_mode: bool) -> None:
        act = str(action.get("action", "")).lower()
        if pyautogui is None:
            raise RuntimeError("pyautogui not installed")
        width, height = pyautogui.size()

        x = _safe_float(action.get("x"))
        y = _safe_float(action.get("y"))
        cell = action.get("cell")
        label_id = action.get("label_id")
        if (x is None or y is None) and label_id is not None and self.state.last_som:
            try:
                lid = int(label_id)
                for item in self.state.last_som:
                    if not isinstance(item, dict):
                        continue
                    item_id = item.get("label_id") or item.get("id") or item.get("index")
                    if item_id is None:
                        continue
                    if int(item_id) != lid:
                        continue
                    bx = item.get("x") or (item.get("box", {}) if isinstance(item.get("box"), dict) else {}).get("x")
                    by = item.get("y") or (item.get("box", {}) if isinstance(item.get("box"), dict) else {}).get("y")
                    bw = item.get("w") or (item.get("box", {}) if isinstance(item.get("box"), dict) else {}).get("w")
                    bh = item.get("h") or (item.get("box", {}) if isinstance(item.get("box"), dict) else {}).get("h")
                    if bx is not None and by is not None and bw is not None and bh is not None:
                        x = float(bx) + float(bw) / 2
                        y = float(by) + float(bh) / 2
                        break
            except Exception:
                pass
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
                        if _parse_bool(os.getenv("AGENTIC_DOM_PRIORITY", "true"), True):
                            if self._click_dom_at_point(int(x), int(y)):
                                return
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
