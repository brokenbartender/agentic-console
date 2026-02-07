from __future__ import annotations

import os
import json
from datetime import datetime
from dataclasses import dataclass
from privacy import (
    parse_allowed_domains,
    parse_allowed_paths,
    is_domain_allowed,
    is_path_allowed,
)
from executor import files as exec_files
import importlib.util


def _load_tool_module(module_name: str, rel_path: str):
    base = os.path.dirname(__file__)
    path = os.path.join(base, rel_path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load tool module: {rel_path}")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_computer_mod = _load_tool_module("tools_computer", os.path.join("tools", "computer.py"))
_vm_mod = _load_tool_module("tools_vm", os.path.join("tools", "vm.py"))
ComputerController = _computer_mod.ComputerController
VMController = _vm_mod.VMController


class ToolNeedsConfirmation(RuntimeError):
    pass


@dataclass
class ToolSpec:
    name: str
    risk: str
    confirm_required: bool = False
    arg_hint: str = ""
    min_parts: int = 0
    splitter: str = ""


@dataclass
class ToolContext:
    confirm: bool = False
    dry_run: bool = False
    via_executor: bool = False


class ToolRegistry:
    def __init__(self, app) -> None:
        self.app = app
        self.allowed_paths = parse_allowed_paths(app.settings.allowed_paths)
        self.allowed_domains = parse_allowed_domains(app.settings.allowed_domains)
        self.computer = ComputerController(app)
        self.vm = VMController(app)
        self.tools = {
            "computer": self._computer,
            "vm": self._vm,
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
            "computer": ToolSpec("computer", "caution", arg_hint="computer <json payload>", min_parts=1, splitter=" "),
            "vm": ToolSpec("vm", "caution", arg_hint="vm <json payload>", min_parts=1, splitter=" "),
            "browse": ToolSpec("browse", "safe", arg_hint="browse <url>", min_parts=1, splitter=" "),
            "search": ToolSpec("search", "safe", arg_hint="search <query>", min_parts=1, splitter=" "),
            "click": ToolSpec("click", "safe", arg_hint="click <selector>", min_parts=1, splitter=" "),
            "type": ToolSpec("type", "safe", arg_hint="type <selector> | <text>", min_parts=2, splitter="|"),
            "press": ToolSpec("press", "safe", arg_hint="press <key>", min_parts=1, splitter=" "),
            "screenshot": ToolSpec("screenshot", "safe", arg_hint="screenshot <path>", min_parts=1, splitter=" "),
            "open": ToolSpec("open", "caution", arg_hint="open <path>", min_parts=1, splitter=" "),
            "move": ToolSpec("move", "caution", arg_hint="move <src> | <dst>", min_parts=2, splitter="|"),
            "copy": ToolSpec("copy", "caution", arg_hint="copy <src> | <dst>", min_parts=2, splitter="|"),
            "delete": ToolSpec("delete", "destructive", confirm_required=True, arg_hint="delete <path>", min_parts=1, splitter=" "),
            "mkdir": ToolSpec("mkdir", "safe", arg_hint="mkdir <path>", min_parts=1, splitter=" "),
            "undo": ToolSpec("undo", "caution"),
        }

    def execute(self, name: str, raw_args: str, ctx: ToolContext | None = None, retries: int = 2):
        if name not in self.tools:
            raise RuntimeError(f"Unknown tool: {name}")
        ctx = ctx or ToolContext()
        if not ctx.via_executor:
            raise RuntimeError("Tool execution must go through executor.execute")
        spec = self.specs.get(name)
        if getattr(self.app, "demo_mode", False) and name in ("delete", "move"):
            raise RuntimeError("Blocked in DEMO MODE. Enable Advanced Mode to proceed.")
        if spec:
            self._validate_args(spec, raw_args)
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

    def call(self, name: str, args: dict | str, ctx: ToolContext | None = None):
        if isinstance(args, dict):
            raw = args.get("raw") or ""
            if not raw:
                raw = json.dumps(args)
            return self.execute(name, raw, ctx=ctx)
        return self.execute(name, str(args), ctx=ctx)

    def _validate_args(self, spec: ToolSpec, raw_args: str) -> None:
        if spec.min_parts <= 0:
            return
        raw = raw_args.strip()
        if not raw:
            raise RuntimeError(f"{spec.name} requires args. Expected: {spec.arg_hint}")
        if spec.splitter:
            parts = [p.strip() for p in raw.split(spec.splitter)]
            if len(parts) < spec.min_parts or any(not p for p in parts[: spec.min_parts]):
                raise RuntimeError(f"{spec.name} requires: {spec.arg_hint}")
        else:
            parts = raw.split()
            if len(parts) < spec.min_parts:
                raise RuntimeError(f"{spec.name} requires: {spec.arg_hint}")

    def _browse(self, raw):
        url = raw.strip()
        if not url:
            raise RuntimeError("browse requires a url")
        if not url.startswith("http"):
            url = "https://" + url
        if not is_domain_allowed(url, self.allowed_domains):
            raise RuntimeError("browse blocked by AGENTIC_ALLOWED_DOMAINS")
        self.app.ensure_browser()
        self.app.page.goto(url, wait_until="domcontentloaded")
        return f"Opened {url}"

    def _computer(self, raw: str):
        payload = raw.strip()
        if not payload:
            raise RuntimeError("computer requires a payload")
        try:
            data = json.loads(payload)
        except Exception:
            raise RuntimeError("computer expects json payload")
        return self.computer.run(data)

    def _vm(self, raw: str):
        payload = raw.strip()
        if not payload:
            raise RuntimeError("vm requires a payload")
        return self.vm.call(payload)

    def _search(self, raw):
        q = raw.strip()
        if not q:
            raise RuntimeError("search requires a query")
        if not is_domain_allowed("https://www.google.com", self.allowed_domains):
            raise RuntimeError("search blocked by AGENTIC_ALLOWED_DOMAINS")
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
        if not is_path_allowed(path, self.allowed_paths):
            raise RuntimeError("screenshot blocked by AGENTIC_ALLOWED_PATHS")
        self.app.ensure_browser()
        self.app.page.screenshot(path=path, full_page=True)
        return f"Saved screenshot {path}"

    def _open(self, raw):
        path = raw.strip()
        if not path:
            raise RuntimeError("open requires a path")
        if not is_path_allowed(path, self.allowed_paths):
            raise RuntimeError("open blocked by AGENTIC_ALLOWED_PATHS")
        exec_files.open_path(path)
        return f"Opened {path}"

    def _move(self, raw):
        parts = raw.split("|", 1)
        if len(parts) != 2:
            raise RuntimeError("move requires: move <src> | <dst>")
        src = parts[0].strip()
        dst = parts[1].strip()
        if not is_path_allowed(src, self.allowed_paths) or not is_path_allowed(dst, self.allowed_paths):
            raise RuntimeError("move blocked by AGENTIC_ALLOWED_PATHS")
        exec_files.move_path(src, dst)
        return f"Moved {src} -> {dst}"

    def _copy(self, raw):
        parts = raw.split("|", 1)
        if len(parts) != 2:
            raise RuntimeError("copy requires: copy <src> | <dst>")
        src = parts[0].strip()
        dst = parts[1].strip()
        if not is_path_allowed(src, self.allowed_paths) or not is_path_allowed(dst, self.allowed_paths):
            raise RuntimeError("copy blocked by AGENTIC_ALLOWED_PATHS")
        exec_files.copy_path(src, dst)
        return f"Copied {src} -> {dst}"

    def _delete(self, raw):
        path = raw.strip()
        if not path:
            raise RuntimeError("delete requires a path")
        if not is_path_allowed(path, self.allowed_paths):
            raise RuntimeError("delete blocked by AGENTIC_ALLOWED_PATHS")
        trash_dir = os.path.join(self.app.settings.data_dir, "trash")
        src, target = exec_files.delete_to_trash(path, trash_dir)
        self.app.memory.set("last_trash", json.dumps({"from": src, "to": target}))
        return f"Moved to trash: {path}"

    def _mkdir(self, raw):
        path = raw.strip()
        if not path:
            raise RuntimeError("mkdir requires a path")
        if not is_path_allowed(path, self.allowed_paths):
            raise RuntimeError("mkdir blocked by AGENTIC_ALLOWED_PATHS")
        exec_files.mkdir_path(path)
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
                if not is_path_allowed(dst, self.allowed_paths):
                    return "Undo blocked by AGENTIC_ALLOWED_PATHS."
                exec_files.restore_path(src, dst)
                self.app.memory.set("last_trash", "")
                return f"Restored {dst}"
        except Exception:
            return "Undo failed."
        return "Nothing to undo."
