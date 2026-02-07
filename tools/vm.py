from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import pyautogui
except Exception:
    pyautogui = None

try:
    import pygetwindow as gw
except Exception:
    gw = None

try:
    import win32con
    import win32gui
    import win32ui
except Exception:
    win32con = None
    win32gui = None
    win32ui = None


@dataclass
class VMWindow:
    title: str
    left: int
    top: int
    width: int
    height: int
    hwnd: Optional[int] = None


class VMController:
    def __init__(self, app) -> None:
        self.app = app

    def _require_deps(self) -> None:
        if pyautogui is None:
            raise RuntimeError("vm control requires pyautogui. Install with: pip install pyautogui")
        if gw is None:
            raise RuntimeError("vm control requires pygetwindow. Install with: pip install pygetwindow")

    def _find_window(self, vm_name: str) -> VMWindow:
        self._require_deps()
        name = (vm_name or "").strip().lower()
        if not name:
            raise RuntimeError("vm_name is required")
        matches = []
        for w in gw.getAllWindows():
            title = w.title or ""
            if name in title.lower():
                matches.append(w)
        if not matches:
            raise RuntimeError(f"No VM window found matching '{vm_name}'. Ensure VMConnect is open.")
        w = matches[0]
        hwnd = getattr(w, "_hWnd", None)
        return VMWindow(title=w.title or "", left=w.left, top=w.top, width=w.width, height=w.height, hwnd=hwnd)

    def observe(self, vm_name: str, out_path: Optional[str] = None) -> Dict[str, Any]:
        win = self._find_window(vm_name)
        if out_path:
            self._capture_window(win, out_path)
        return {
            "title": win.title,
            "left": win.left,
            "top": win.top,
            "width": win.width,
            "height": win.height,
            "screenshot": out_path or "",
        }

    def _capture_window(self, win: VMWindow, out_path: str) -> None:
        if win32gui and win32ui and win32con and win.hwnd:
            try:
                left, top, right, bottom = win32gui.GetWindowRect(win.hwnd)
                width = right - left
                height = bottom - top
                hwnd_dc = win32gui.GetWindowDC(win.hwnd)
                mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
                save_dc = mfc_dc.CreateCompatibleDC()
                save_bit_map = win32ui.CreateBitmap()
                save_bit_map.CreateCompatibleBitmap(mfc_dc, width, height)
                save_dc.SelectObject(save_bit_map)
                result = win32gui.PrintWindow(win.hwnd, save_dc.GetSafeHdc(), 1)
                if result == 1:
                    save_bit_map.SaveBitmapFile(save_dc, out_path)
                    win32gui.DeleteObject(save_bit_map.GetHandle())
                    save_dc.DeleteDC()
                    mfc_dc.DeleteDC()
                    win32gui.ReleaseDC(win.hwnd, hwnd_dc)
                    return
            except Exception:
                pass
        if pyautogui is None:
            raise RuntimeError("pyautogui not available")
        image = pyautogui.screenshot(region=(win.left, win.top, win.width, win.height))
        image.save(out_path)

    def focus(self, vm_name: str) -> str:
        self._require_deps()
        win = self._find_window(vm_name)
        for w in gw.getAllWindows():
            if (w.title or "") == win.title:
                try:
                    w.activate()
                except Exception:
                    pass
                break
        pyautogui.click(win.left + (win.width // 2), win.top + (win.height // 2))
        return f"focused {win.title}"

    def click(self, vm_name: str, x: int, y: int, button: str = "left", clicks: int = 1) -> str:
        self._require_deps()
        win = self._find_window(vm_name)
        tx = win.left + int(x)
        ty = win.top + int(y)
        pyautogui.click(tx, ty, clicks=clicks, button=button)
        return f"clicked {tx},{ty}"

    def type_text(self, text: str) -> str:
        self._require_deps()
        pyautogui.typewrite(str(text))
        return "typed text"

    def press(self, key: str) -> str:
        self._require_deps()
        if not key:
            raise RuntimeError("key is required")
        pyautogui.press(str(key))
        return f"pressed {key}"

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = (payload.get("action") or "").strip().lower()
        vm_name = payload.get("vm_name") or payload.get("name") or ""
        if action == "observe":
            path = payload.get("path") or ""
            return self.observe(vm_name, out_path=path)
        if action == "focus":
            return {"result": self.focus(vm_name)}
        if action in ("click", "double_click", "right_click"):
            x = payload.get("x")
            y = payload.get("y")
            if x is None or y is None:
                raise RuntimeError("click requires x,y")
            button = "left"
            clicks = 1
            if action == "double_click":
                clicks = 2
            if action == "right_click":
                button = "right"
            return {"result": self.click(vm_name, int(x), int(y), button=button, clicks=clicks)}
        if action == "type":
            return {"result": self.type_text(payload.get("text") or "")}
        if action == "press":
            return {"result": self.press(payload.get("key") or "")}
        raise RuntimeError(f"vm action unsupported: {action}")

    def call(self, raw: str) -> Dict[str, Any]:
        if not raw:
            raise RuntimeError("vm requires a json payload")
        try:
            payload = json.loads(raw)
        except Exception:
            raise RuntimeError("vm expects json payload")
        return self.run(payload)
