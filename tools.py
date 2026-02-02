from __future__ import annotations

import os
import shutil
import json
from datetime import datetime
from dataclasses import dataclass


class ToolNeedsConfirmation(RuntimeError):
    pass


@dataclass
class ToolSpec:
    name: str
    risk: str
    confirm_required: bool = False


@dataclass
class ToolContext:
    confirm: bool = False
    dry_run: bool = False


class ToolRegistry:
    def __init__(self, app) -> None:
        self.app = app
        self.tools = {
            "browse": self._browse,
            "search": self._search,
            "click": self._click,
            "type": self._type,
            "press": self._press,
            "screenshot": self._screenshot,
            "open": self._open,
            "move": self._move,
            "copy": self._copy,
            "delete": self._delete,
            "mkdir": self._mkdir,
            "undo": self._undo,
        }
        self.specs = {
            "browse": ToolSpec("browse", "safe"),
            "search": ToolSpec("search", "safe"),
            "click": ToolSpec("click", "safe"),
            "type": ToolSpec("type", "safe"),
            "press": ToolSpec("press", "safe"),
            "screenshot": ToolSpec("screenshot", "safe"),
            "open": ToolSpec("open", "caution"),
            "move": ToolSpec("move", "caution"),
            "copy": ToolSpec("copy", "caution"),
            "delete": ToolSpec("delete", "destructive", confirm_required=True),
            "mkdir": ToolSpec("mkdir", "safe"),
            "undo": ToolSpec("undo", "caution"),
        }

    def execute(self, name: str, raw_args: str, ctx: ToolContext | None = None, retries: int = 2):
        if name not in self.tools:
            raise RuntimeError(f"Unknown tool: {name}")
        ctx = ctx or ToolContext()
        spec = self.specs.get(name)
        if spec and spec.confirm_required and not ctx.confirm:
            raise ToolNeedsConfirmation(f"Tool '{name}' requires confirmation.")
        last_err = None
        for _ in range(retries + 1):
            try:
                if ctx.dry_run:
                    return f"DRY RUN: {name} {raw_args}".strip()
                return self.tools[name](raw_args)
            except Exception as exc:
                last_err = exc
        raise last_err

    def _browse(self, raw):
        url = raw.strip()
        if not url:
            raise RuntimeError("browse requires a url")
        if not url.startswith("http"):
            url = "https://" + url
        self.app.ensure_browser()
        self.app.page.goto(url, wait_until="domcontentloaded")
        return f"Opened {url}"

    def _search(self, raw):
        q = raw.strip()
        if not q:
            raise RuntimeError("search requires a query")
        self.app.ensure_browser()
        self.app.page.goto("https://www.google.com", wait_until="domcontentloaded")
        self.app.page.locator("input[name='q']").fill(q)
        self.app.page.keyboard.press("Enter")
        return f"Searched: {q}"

    def _click(self, raw):
        selector = raw.strip()
        if not selector:
            raise RuntimeError("click requires a selector")
        self.app.ensure_browser()
        self.app.page.locator(selector).first.click()
        return f"Clicked {selector}"

    def _type(self, raw):
        parts = raw.split("|", 1)
        if len(parts) != 2:
            raise RuntimeError("type requires: type <css selector> | <text>")
        selector = parts[0].strip()
        text = parts[1].strip()
        self.app.ensure_browser()
        self.app.page.locator(selector).fill(text)
        return f"Typed into {selector}"

    def _press(self, raw):
        key = raw.strip()
        if not key:
            raise RuntimeError("press requires a key")
        self.app.ensure_browser()
        self.app.page.keyboard.press(key)
        return f"Pressed {key}"

    def _screenshot(self, raw):
        path = raw.strip()
        if not path:
            raise RuntimeError("screenshot requires a path")
        self.app.ensure_browser()
        self.app.page.screenshot(path=path, full_page=True)
        return f"Saved screenshot {path}"

    def _open(self, raw):
        path = raw.strip()
        if not path:
            raise RuntimeError("open requires a path")
        os.startfile(path)
        return f"Opened {path}"

    def _move(self, raw):
        parts = raw.split("|", 1)
        if len(parts) != 2:
            raise RuntimeError("move requires: move <src> | <dst>")
        src = parts[0].strip()
        dst = parts[1].strip()
        shutil.move(src, dst)
        if not os.path.exists(dst):
            raise RuntimeError("move verification failed")
        return f"Moved {src} -> {dst}"

    def _copy(self, raw):
        parts = raw.split("|", 1)
        if len(parts) != 2:
            raise RuntimeError("copy requires: copy <src> | <dst>")
        src = parts[0].strip()
        dst = parts[1].strip()
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        if not os.path.exists(dst):
            raise RuntimeError("copy verification failed")
        return f"Copied {src} -> {dst}"

    def _delete(self, raw):
        path = raw.strip()
        if not path:
            raise RuntimeError("delete requires a path")
        trash_dir = os.path.join(self.app.settings.data_dir, "trash")
        os.makedirs(trash_dir, exist_ok=True)
        base = os.path.basename(path.rstrip("\\/"))
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = os.path.join(trash_dir, f"{stamp}-{base}")
        shutil.move(path, target)
        self.app.memory.set("last_trash", json.dumps({"from": path, "to": target}))
        return f"Moved to trash: {path}"

    def _mkdir(self, raw):
        path = raw.strip()
        if not path:
            raise RuntimeError("mkdir requires a path")
        os.makedirs(path, exist_ok=True)
        return f"Created {path}"

    def _undo(self, raw):
        data = self.app.memory.get("last_trash")
        if not data:
            return "Nothing to undo."
        try:
            payload = json.loads(data)
            src = payload.get("to")
            dst = payload.get("from")
            if src and dst:
                shutil.move(src, dst)
                self.app.memory.set("last_trash", "")
                return f"Restored {dst}"
        except Exception:
            return "Undo failed."
        return "Nothing to undo."
