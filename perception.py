from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, Any

try:
    import pyautogui
except Exception:
    pyautogui = None


def capture_screen(path: str) -> str:
    if pyautogui is None:
        raise RuntimeError("pyautogui not installed")
    image = pyautogui.screenshot()
    image.save(path)
    return path


def collect_observation(screenshot_path: str | None = None) -> Dict[str, Any]:
    observation: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "cwd": os.getcwd(),
    }
    if screenshot_path:
        saved = capture_screen(screenshot_path)
        observation["screenshot"] = saved
    return observation
