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
                url = cmd[7:].strip()
                if not url.startswith("http"):
                    url = "https://" + url
                self.ensure_browser()
                self.page.goto(url, wait_until="domcontentloaded")
                self.log_line(f"Opened {url}")
                return

            if cmd.lower().startswith("search "):
                q = cmd[7:].strip()
                self.ensure_browser()
                self.page.goto("https://www.google.com", wait_until="domcontentloaded")
                self.page.locator("input[name='q']").fill(q)
                self.page.keyboard.press("Enter")
                self.log_line(f"Searched: {q}")
                return

            if cmd.lower().startswith("click "):
                selector = cmd[6:].strip()
                self.ensure_browser()
                self.page.locator(selector).first.click()
                self.log_line(f"Clicked {selector}")
                return

            if cmd.lower().startswith("type "):
                parts = cmd[5:].split("|", 1)
                if len(parts) != 2:
                    raise RuntimeError("type requires: type <css selector> | <text>")
                selector = parts[0].strip()
                text = parts[1].strip()
                self.ensure_browser()
                self.page.locator(selector).fill(text)
                self.log_line(f"Typed into {selector}")
                return

            if cmd.lower().startswith("press "):
                key = cmd[6:].strip()
                self.ensure_browser()
                self.page.keyboard.press(key)
                self.log_line(f"Pressed {key}")
                return

            if cmd.lower().startswith("screenshot "):
                path = cmd[11:].strip()
                if not path:
                    raise RuntimeError("screenshot requires a path")
                self.ensure_browser()
                self.page.screenshot(path=path, full_page=True)
                self.log_line(f"Saved screenshot {path}")
                return

            if cmd.lower().startswith("open "):
                path = cmd[5:].strip()
                os.startfile(path)
                self.log_line(f"Opened {path}")
                return

            if cmd.lower().startswith("move "):
                parts = cmd[5:].split("|", 1)
                if len(parts) != 2:
                    raise RuntimeError("move requires: move <src> | <dst>")
                src = parts[0].strip()
                dst = parts[1].strip()
                shutil.move(src, dst)
                self.log_line(f"Moved {src} -> {dst}")
                return

            if cmd.lower().startswith("copy "):
                parts = cmd[5:].split("|", 1)
                if len(parts) != 2:
                    raise RuntimeError("copy requires: copy <src> | <dst>")
                src = parts[0].strip()
                dst = parts[1].strip()
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
                self.log_line(f"Copied {src} -> {dst}")
                return

            if cmd.lower().startswith("delete "):
                path = cmd[7:].strip()
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                self.log_line(f"Deleted {path}")
                return

            if cmd.lower().startswith("mkdir "):
                path = cmd[6:].strip()
                os.makedirs(path, exist_ok=True)
                self.log_line(f"Created {path}")
                return

            if cmd.lower().startswith("agent "):
                instruction = cmd[6:].strip()
                if not instruction:
                    raise RuntimeError("agent requires an instruction")
                output = self._agent_chat(instruction)
                if output:
                    self.log_line(output)
                else:
                    self.log_line("Agent task completed")
                return

            # Default: route all natural language to the agent.
            output = self._agent_chat(cmd)
            if output:
                self.log_line(output)
            else:
                self.log_line("Agent task completed")
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
