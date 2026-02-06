from __future__ import annotations

import os
import requests
from nicegui import ui

API = os.getenv("AGENTIC_WEB_HOST", "127.0.0.1")
PORT = int(os.getenv("AGENTIC_WEB_PORT", "8333"))
BASE = f"http://{API}:{PORT}"


def send_command(cmd: str) -> str:
    try:
        resp = requests.post(f"{BASE}/api/command", json={"command": cmd}, timeout=5)
        if resp.status_code != 200:
            return f"Error: {resp.status_code} {resp.text}"
        return resp.text
    except Exception as exc:
        return f"Error: {exc}"


ui.label("Agentic Control Plane")
status = ui.label("idle").classes("text-sm text-gray-500")
cmd = ui.input(placeholder="Enter command (e.g. agent do X)").classes("w-full")
out = ui.textarea().classes("w-full").props("readonly")


def run_cmd() -> None:
    text = cmd.value or ""
    status.text = "running..."
    out.value = send_command(text)
    status.text = "idle"


ui.button("Run", on_click=run_cmd)
ui.run(title="Agentic Control Plane", native=True, reload=False, dark=False, window_size=(520, 420), window_always_on_top=True)
