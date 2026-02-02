import os
import shlex
import shutil
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import contextlib
import urllib.request
import urllib.error
import logging

from config import get_settings
from memory import MemoryStore
from logger import setup_logging

# Lazy imports for optional dependencies
try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None

try:
    import pyautogui  # noqa: F401
except Exception:
    pyautogui = None

try:
    from interpreter import interpreter as oi_interpreter
except Exception:
    oi_interpreter = None


def _configure_agent():
    if oi_interpreter is None:
        raise RuntimeError(
            "open-interpreter not installed. Run: python -m pip install open-interpreter"
        )
    # Patch missing display helper in some open-interpreter versions.
    try:
        import builtins
        if not hasattr(builtins, "display_markdown_message"):
            builtins.display_markdown_message = lambda *args, **kwargs: None
        try:
            import interpreter.core.respond as respond_mod
            if not hasattr(respond_mod, "display_markdown_message"):
                respond_mod.display_markdown_message = lambda *args, **kwargs: None
        except Exception:
            pass
    except Exception:
        pass
    # OpenAI if key exists; otherwise fallback to local Ollama if configured.
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        oi_interpreter.offline = False
        model = os.getenv("OPENAI_MODEL")
        if model:
            oi_interpreter.llm.model = model
        return

    # Local fallback (optional)
    ollama_model = os.getenv("OLLAMA_MODEL")
    ollama_base = os.getenv("OLLAMA_BASE", "http://127.0.0.1:11434")
    if ollama_model:
        oi_interpreter.offline = True
        oi_interpreter.llm.model = ollama_model
        oi_interpreter.llm.api_base = ollama_base
        return

    raise RuntimeError(
        "No OpenAI key found and no local fallback configured. "
        "Set OPENAI_API_KEY or set OLLAMA_MODEL (and optional OLLAMA_BASE)."
    )


class ToolRegistry:
    def __init__(self, app):
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

    def execute(self, name, raw_args, retries=2):
        if name not in self.tools:
            raise RuntimeError(f"Unknown tool: {name}")
        last_err = None
        for _ in range(retries + 1):
            try:
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

APP_TITLE = "Agentic Console"

class AgentApp:
    def __init__(self, root, settings, memory):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("900x600")

        self.settings = settings
        self.memory = memory

        self.playwright = None
        self.browser = None
        self.page = None
        self.log_buffer = []
        self.chat_history = []
        self.tools = ToolRegistry(self)

        self._build_ui()
        self._load_memory()

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.BOTH, expand=True)

        self.input_var = tk.StringVar()
        input_row = ttk.Frame(top)
        input_row.pack(fill=tk.X)

        ttk.Label(input_row, text="Task/Command:").pack(side=tk.LEFT)
        entry = ttk.Entry(input_row, textvariable=self.input_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        entry.bind("<Return>", lambda _e: self.run_command())

        run_btn = ttk.Button(input_row, text="Run", command=self.run_command)
        run_btn.pack(side=tk.LEFT)

        self.log = tk.Text(top, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True, pady=8)
        self.log.insert(tk.END, "Ready. Type a command and press Enter.\n")
        self.log.configure(state=tk.DISABLED)

        help_text = "Just type what you want. No special commands required."
        ttk.Label(top, text=help_text, foreground="#555").pack(fill=tk.X)

    def log_line(self, message):
        self.log.configure(state=tk.NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.insert(tk.END, f"[{ts}] {message}\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)
        self.log_buffer.append(f"[{ts}] {message}")
        if len(self.log_buffer) > 500:
            self.log_buffer = self.log_buffer[-500:]

    def get_recent_logs(self, count=20):
        return "\n".join(self.log_buffer[-count:])

    def _add_message(self, role, text):
        self.chat_history.append({"role": role, "content": text})
        max_turns = int(os.getenv("CHAT_HISTORY_TURNS", "20"))
        if len(self.chat_history) > max_turns * 2:
            self.chat_history = self.chat_history[-max_turns * 2:]
        self._save_memory()

    def _load_memory(self):
        try:
            raw = self.memory.get("chat_history")
            if raw:
                self.chat_history = json.loads(raw)
        except Exception:
            self.chat_history = []

    def _save_memory(self):
        try:
            self.memory.set("chat_history", json.dumps(self.chat_history))
        except Exception:
            pass

    def _agent_chat(self, instruction):
        _configure_agent()
        oi_interpreter.auto_run = True
        oi_interpreter.system_message = (
            "You are ChatGPT with full access to the user's computer and browser. "
            "When the user asks for actions, perform them directly. "
            "When the user asks for information or conversation, respond normally."
        )
        self.memory.log_event("instruction", instruction)
        logging.info("instruction: %s", instruction)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            result = oi_interpreter.chat(instruction)
        output = (buf.getvalue() or "").strip()
        if result and isinstance(result, str):
            output = (output + "\n" + result).strip() if output else result.strip()
        if output:
            self.memory.log_event("response", output)
            logging.info("response: %s", output[:500])
        return output

    def _needs_confirmation(self, instruction):
        danger = [" delete ", " remove ", " rm ", " rmdir ", " del ", " erase "]
        lowered = f" {instruction.lower()} "
        return any(d in lowered for d in danger)

    def _planner(self, instruction):
        # Lightweight planner: simple heuristic routing to tool actions vs. agent chat.
        lowered = instruction.strip().lower()
        tool_prefixes = (
            "browse ", "search ", "click ", "type ", "press ",
            "screenshot ", "open ", "move ", "copy ", "delete ", "mkdir ", "undo ", "agent "
        )
        if lowered.startswith(tool_prefixes):
            return [instruction]
        return []

    def _executor(self, plan_steps):
        for step in plan_steps:
            self._execute(step)

    def _verifier(self, plan_steps):
        # Minimal verifier: log completion of each step.
        if plan_steps:
            self.memory.log_event("verify", json.dumps({"steps": plan_steps}))

    def _orchestrate(self, instruction):
        # Guardrail for destructive actions.
        if self._needs_confirmation(instruction):
            pending = self.memory.get("pending_confirm")
            if pending != instruction:
                self.memory.set("pending_confirm", instruction)
                return "This action may be destructive. Type 'confirm' to proceed."
        if instruction.strip().lower() == "confirm":
            pending = self.memory.get("pending_confirm")
            if not pending:
                return "No pending action to confirm."
            self.memory.set("pending_confirm", "")
            instruction = pending

        plan = self._planner(instruction)
        if plan:
            self.memory.log_event("plan", json.dumps({"steps": plan}))
            self._executor(plan)
            self._verifier(plan)
            return "Done."

        # Default: use agent for freeform tasks.
        return self._agent_chat(instruction) or "Agent task completed"

    def ensure_browser(self):
        if self.page is not None:
            return
        if sync_playwright is None:
            raise RuntimeError("playwright not installed. Run: python -m pip install playwright")
        self.playwright = sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.launch(channel="chrome", headless=False)
        except Exception:
            # Fallback to bundled Chromium if Chrome channel isn't available
            self.browser = self.playwright.chromium.launch(headless=False)
        self.page = self.browser.new_page()

    def cleanup(self):
        try:
            if self.page:
                self.page.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass

    def run_command(self):
        cmd = self.input_var.get().strip()
        if not cmd:
            return
        self.input_var.set("")
        self.log_line(f"> {cmd}")
        t = threading.Thread(target=self._execute, args=(cmd,), daemon=True)
        t.start()

    def _execute(self, cmd):
        try:
            if cmd.lower().startswith("browse "):
                out = self.tools.execute("browse", cmd[7:].strip())
                self.log_line(out)
                return

            if cmd.lower().startswith("search "):
                out = self.tools.execute("search", cmd[7:].strip())
                self.log_line(out)
                return

            if cmd.lower().startswith("click "):
                out = self.tools.execute("click", cmd[6:].strip())
                self.log_line(out)
                return

            if cmd.lower().startswith("type "):
                out = self.tools.execute("type", cmd[5:].strip())
                self.log_line(out)
                return

            if cmd.lower().startswith("press "):
                out = self.tools.execute("press", cmd[6:].strip())
                self.log_line(out)
                return

            if cmd.lower().startswith("screenshot "):
                out = self.tools.execute("screenshot", cmd[11:].strip())
                self.log_line(out)
                return

            if cmd.lower().startswith("open "):
                out = self.tools.execute("open", cmd[5:].strip())
                self.log_line(out)
                return

            if cmd.lower().startswith("move "):
                out = self.tools.execute("move", cmd[5:].strip())
                self.log_line(out)
                return

            if cmd.lower().startswith("copy "):
                out = self.tools.execute("copy", cmd[5:].strip())
                self.log_line(out)
                return

            if cmd.lower().startswith("delete "):
                out = self.tools.execute("delete", cmd[7:].strip())
                self.log_line(out)
                return

            if cmd.lower().startswith("mkdir "):
                out = self.tools.execute("mkdir", cmd[6:].strip())
                self.log_line(out)
                return

            if cmd.lower().startswith("undo"):
                out = self.tools.execute("undo", "")
                self.log_line(out)
                return

            if cmd.lower().startswith("agent "):
                instruction = cmd[6:].strip()
                if not instruction:
                    raise RuntimeError("agent requires an instruction")
                output = self._orchestrate(instruction)
                self.log_line(output)
                return

            output = self._orchestrate(cmd)
            self.log_line(output)
        except Exception as e:
            self.log_line(f"Error: {e}")


def _make_web_handler(app):
    class WebHandler(BaseHTTPRequestHandler):
        def _send(self, status, body, content_type="text/html"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/favicon.ico":
                self._send(HTTPStatus.NO_CONTENT, b"", "image/x-icon")
                return
            if self.path == "/health":
                self._send(HTTPStatus.OK, b"ok", "text/plain")
                return
            if self.path != "/":
                self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")
                return
            html = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Agentic Console</title>
    <style>
      body { font-family: Segoe UI, Arial, sans-serif; margin: 20px; }
      textarea { width: 100%; height: 90px; }
      button { padding: 8px 14px; }
      pre { background: #f5f5f5; padding: 12px; white-space: pre-wrap; }
      .hint { color: #666; font-size: 12px; }
    </style>
  </head>
  <body>
    <h2>Agentic Console</h2>
    <div class="hint">Type naturally, like: open chrome and go to gmail.com</div>
    <textarea id="cmd"></textarea><br/>
    <button onclick="sendCmd()">Run</button>
    <pre id="out"></pre>
    <script>
      async function sendCmd() {
        const cmd = document.getElementById('cmd').value;
        const res = await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: cmd })
        });
        const data = await res.json();
        document.getElementById('out').textContent = data.output || '';
      }
    </script>
  </body>
</html>
"""
            self._send(HTTPStatus.OK, html.encode("utf-8"), "text/html")

        def do_POST(self):
            if self.path != "/api/command":
                self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8", errors="ignore")
                payload = json.loads(raw) if raw else {}
                command = (payload.get("command") or "").strip()
                if not command:
                    self._send(HTTPStatus.BAD_REQUEST, b"missing command", "text/plain")
                    return
                app._execute(command)
                out = app.get_recent_logs(40)
                body = json.dumps({"output": out}).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
            except Exception as exc:
                body = json.dumps({"error": str(exc)}).encode("utf-8")
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR, body, "application/json")

        def log_message(self, format, *args):
            return

    return WebHandler


def _start_web_server(app):
    host = app.settings.server_host
    port = app.settings.server_port
    handler = _make_web_handler(app)
    server = ThreadingHTTPServer((host, port), handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    app.log_line(f"Web UI: http://{host}:{port}")
    return server


def main():
    settings = get_settings()
    setup_logging(settings.log_file)
    root = tk.Tk()
    memory = MemoryStore(settings.memory_db)
    app = AgentApp(root, settings, memory)
    _start_web_server(app)
    app.log_line("OpenAI key loaded: " + ("yes" if os.getenv("OPENAI_API_KEY") else "no"))

    def on_close():
        app.cleanup()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
