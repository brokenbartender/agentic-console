import os

import threading

import tkinter as tk

from tkinter import ttk

from datetime import datetime

import json

import time

from http import HTTPStatus

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import io

import contextlib

import logging



from config import get_settings

from memory import MemoryStore

from logger import setup_logging

from metrics import Metrics

from task_queue import TaskQueue

from tools import ToolRegistry, ToolContext, ToolNeedsConfirmation

from agents import PlannerAgent, RetrieverAgent, ExecutorAgent, VerifierAgent

from rag import RagStore

from calibration import confidence_from_evidence

from deep_research import DeepResearch

from multimodal import ocr_pdf

from router import choose_model

from policy import requires_confirmation
from job_store import JobStore
from team import TeamOrchestrator, AgentRole
from a2a import A2ABus
from mcp_adapter import MCPAdapter
from privacy import redact_text


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





def _configure_agent(settings, instruction: str = ""):
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

        mode = choose_model(instruction)

        if mode == "coding":
            model = settings.openai_coding_model
        elif mode == "reasoning":
            model = settings.openai_reasoning_model
        else:
            model = settings.openai_model
        oi_interpreter.llm.model = model
        return model


    # Local fallback (optional)

    mode = choose_model(instruction)

    if mode == "coding":
        ollama_model = os.getenv("OLLAMA_CODING_MODEL") or settings.ollama_coding_model
    elif mode == "reasoning":
        ollama_model = os.getenv("OLLAMA_REASONING_MODEL") or settings.ollama_reasoning_model
    else:
        ollama_model = os.getenv("OLLAMA_MODEL") or settings.ollama_model
    ollama_base = os.getenv("OLLAMA_BASE", settings.ollama_base)

    if ollama_model:
        oi_interpreter.offline = True
        oi_interpreter.llm.model = ollama_model
        oi_interpreter.llm.api_base = ollama_base
        return ollama_model


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

        self.metrics = Metrics()

        self.task_queue = TaskQueue(settings.task_queue_size)



        self.playwright = None

        self.browser = None

        self.page = None

        self.log_buffer = []

        self.chat_history = []

        self.tools = ToolRegistry(self)

        self.rag = RagStore(self.memory)
        self.jobs = JobStore(self.memory._conn)
        self.a2a = A2ABus(self.memory)
        self.mcp = MCPAdapter()


        tool_prefixes = list(self.tools.tools.keys())

        tool_prefixes.append("index")
        tool_prefixes.append("rag")
        tool_prefixes.append("deep_research")
        tool_prefixes.append("ocr")
        tool_prefixes.append("a2a")
        tool_prefixes.append("mcp")
        tool_prefixes.append("agent")
        self.planner = PlannerAgent([f"{p} " for p in tool_prefixes])

        self.retriever = RetrieverAgent(self.memory)

        self.executor = ExecutorAgent(self._execute_step)

        self.verifier = VerifierAgent()

        self.deep_research = DeepResearch(self._agent_chat, self._rag_search)

        self.autonomy_level = self.memory.get("autonomy_level") or settings.autonomy_level

        self.purpose = self.memory.get("purpose") or settings.purpose
        self.redact_logs = settings.redact_logs.lower() == "true"
        self.memory.purge_events(settings.event_retention_seconds)

        self.team = TeamOrchestrator(self._agent_chat)



        self._build_ui()

        self._load_memory()



    def _build_ui(self):

        top = ttk.Frame(self.root, padding=8)

        top.pack(fill=tk.BOTH, expand=True)



        self.input_var = tk.StringVar()

        input_row = ttk.Frame(top)

        input_row.pack(fill=tk.X)



        ttk.Label(input_row, text="Task:").pack(side=tk.LEFT)

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



    def _maybe_redact(self, text: str) -> str:
        if getattr(self, "redact_logs", False):
            return redact_text(text)
        return text

    def _log_event(self, event_type: str, payload, extra: dict | None = None) -> None:
        safe_payload = payload
        if not isinstance(safe_payload, str):
            try:
                safe_payload = json.dumps(safe_payload)
            except Exception:
                safe_payload = str(safe_payload)
        safe_payload = self._maybe_redact(safe_payload)
        data = {
            "payload": safe_payload,
            "purpose": getattr(self, "purpose", "") or "",
            "autonomy": getattr(self, "autonomy_level", ""),
        }
        if extra:
            data.update(extra)
        self.memory.log_event(event_type, json.dumps(data))

    def log_line(self, message):
        self.log.configure(state=tk.NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        safe = self._maybe_redact(message)
        self.log.insert(tk.END, f"[{ts}] {safe}\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)
        self.log_buffer.append(f"[{ts}] {safe}")
        if len(self.log_buffer) > 500:
            self.log_buffer = self.log_buffer[-500:]

    def get_recent_logs(self, count=20):

        return "\n".join(self.log_buffer[-count:])



    def _add_message(self, role, text):

        self.chat_history.append({"role": role, "content": text})

        max_turns = self.settings.max_chat_turns

        if len(self.chat_history) > max_turns * 2:

            self._summarize_history()

        self._save_memory()



    def _summarize_history(self):

        if not self.chat_history:

            return

        summary = " ".join(m["content"] for m in self.chat_history[-10:])

        summary = summary[:800]

        self.memory.set("chat_summary", summary)

        if self.settings.auto_summarize.lower() == "true":

            self.memory.add_memory("summary", summary, ttl_seconds=self.settings.long_memory_ttl)

        self.chat_history = self.chat_history[-10:]



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

        model_name = _configure_agent(self.settings, instruction)

        oi_interpreter.auto_run = True

        oi_interpreter.system_message = (

            "You are ChatGPT with full access to the user's computer and browser. "

            "When the user asks for actions, perform them directly. "

            "When the user asks for information or conversation, respond normally. "

            "Always be concise and confirm destructive actions."

        )

        purpose = getattr(self, "purpose", "")
        if purpose:
            oi_interpreter.system_message += f" Current purpose: {purpose}."

        context = self.retriever.retrieve(instruction)

        if context:

            instruction = f"Context:\n{context}\n\nUser: {instruction}"

        self._add_message("user", instruction)

        self.memory.add_memory("short", f"USER: {instruction}", ttl_seconds=self.settings.short_memory_ttl)

        extra = {"model": model_name or ""}
        self._log_event("instruction", instruction, extra)

        logging.info("instruction: %s", self._maybe_redact(instruction))

        buf = io.StringIO()

        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):

            try:

                result = oi_interpreter.chat(instruction)

            except Exception as exc:

                msg = str(exc).lower()

                if "insufficient_quota" in msg or "quota" in msg:

                    oi_interpreter.offline = True

                    oi_interpreter.llm.model = self.settings.ollama_model

                    oi_interpreter.llm.api_base = self.settings.ollama_base
                    model_name = self.settings.ollama_model

                    result = oi_interpreter.chat(instruction)

                else:

                    raise

        output = (buf.getvalue() or "").strip()

        if result and isinstance(result, str):

            output = (output + "\n" + result).strip() if output else result.strip()

        if output:

            self._log_event("response", output, extra)

            logging.info("response: %s", self._maybe_redact(output)[:500])

            self._add_message("assistant", output)

            self.memory.add_memory("short", f"ASSISTANT: {output}", ttl_seconds=self.settings.short_memory_ttl)

        return output



    def _execute_tool(self, name: str, args: str, confirm: bool = False, dry_run: bool = False):

        ctx = ToolContext(confirm=confirm, dry_run=dry_run)

        self.metrics.add_tool_call(name)

        self._log_event("tool", json.dumps({"name": name, "args": args}))

        return self.tools.execute(name, args, ctx)



    def _rag_search(self, query: str, limit: int = 5):

        return self.rag.search(query, limit=limit)



    def _execute_step(self, step: str):

        lowered = step.strip().lower()

        if lowered.startswith("index "):

            path = step[6:].strip()

            if os.path.isdir(path):

                count = 0

                for root, _dirs, files in os.walk(path):

                    for name in files:

                        full = os.path.join(root, name)

                        try:

                            self.rag.index_file(full)

                            count += 1

                        except Exception:

                            continue

                self.log_line(f"Indexed {count} files")

                return

            self.rag.index_file(path)

            self.log_line(f"Indexed {path}")

            return



        if lowered.startswith("rag "):

            query = step[4:].strip()

            evidence = self._rag_search(query, limit=5)

            conf = confidence_from_evidence(evidence)

            if not evidence:

                self.log_line("No evidence found.")

                return

            ev_text = "\n".join(f"- {e['source']}: {e['text'][:200]}" for e in evidence)

            answer = self._agent_chat(f"Use evidence to answer: {query}\nEvidence:\n{ev_text}")

            self.log_line(f"Confidence: {conf:.2f}")

            self.log_line(answer or "Agent task completed")

            return



        if lowered.startswith("deep_research "):

            question = step[len("deep_research "):].strip()

            output = self.deep_research.run(question)

            self.log_line(output)

            return



        if lowered.startswith("team "):
            task = step[len("team "):].strip()
            roles = [

                AgentRole("Planner", "Create a brief plan."),

                AgentRole("Builder", "Execute the plan or draft the solution."),

                AgentRole("Reviewer", "Review for issues and improvements."),

            ]

            output = self.team.run(roles, task)

            self.log_line(output)
            return

        if lowered.startswith("a2a "):
            # format: a2a sender -> receiver | message
            raw = step[len("a2a "):].strip()
            if "->" not in raw or "|" not in raw:
                self.log_line("a2a requires: a2a sender -> receiver | message")
                return
            left, msg = raw.split("|", 1)
            sender, receiver = [s.strip() for s in left.split("->", 1)]
            self.a2a.send(sender, receiver, msg.strip())
            self.log_line("A2A message sent.")
            return

        if lowered.startswith("mcp "):
            # format: mcp provider | json
            raw = step[len("mcp "):].strip()
            if "|" not in raw:
                self.log_line("mcp requires: mcp provider | {json}")
                return
            provider, payload = [s.strip() for s in raw.split("|", 1)]
            try:
                data = json.loads(payload)
                result = self.mcp.call(provider, data)
                self.log_line(json.dumps(result))
            except Exception as exc:
                self.log_line(f"mcp error: {exc}")
            return


        if lowered.startswith("ocr "):

            path = step[len("ocr "):].strip()

            text = ocr_pdf(path, pages=2)

            self.log_line(text[:2000] if text else "No OCR text.")

            return



        for name in self.tools.tools.keys():

            prefix = f"{name} "

            if lowered.startswith(prefix):

                args = step[len(prefix):].strip()

                out = self._execute_tool(name, args)

                self.log_line(out)

                return

        # If not a tool, route to agent.

        out = self._agent_chat(step) or "Agent task completed"

        self.log_line(out)



    def _orchestrate(self, instruction):

        if instruction.strip().lower() == "confirm":

            pending = self.memory.get("pending_action")

            if not pending:

                return "No pending action to confirm."

            payload = json.loads(pending)

            self.memory.set("pending_action", "")

            if payload.get("type") == "tool":

                name = payload.get("name")

                args = payload.get("args")

                out = self._execute_tool(name, args, confirm=True)

                return out

            return "Nothing to confirm."



        plan = self.planner.plan(instruction)

        if plan:

            self._log_event("plan", json.dumps({"steps": plan}))

            self.executor.run(plan)

            verify_msg = self.verifier.verify(plan)

            if verify_msg:

                self._log_event("verify", verify_msg)

            return "Done."



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

        self.task_queue.enqueue(lambda: self._execute(cmd))



    def _execute(self, cmd: str):

        try:

            self.metrics.inc("tasks_total")

            start = time.time()

            lowered = cmd.lower().strip()

            if not hasattr(self, "purpose"):
                self.purpose = ""
            if not hasattr(self, "redact_logs"):
                self.redact_logs = False

            if "remember" in lowered or "note this" in lowered:

                self.memory.add_memory("long", cmd, ttl_seconds=self.settings.long_memory_ttl)



            if lowered.startswith("agent "):

                instruction = cmd[6:].strip()

                if not instruction:

                    raise RuntimeError("agent requires an instruction")

                output = self._orchestrate(instruction)

                self.log_line(output)

                return



            if lowered.startswith("autonomy "):

                level = lowered.split(" ", 1)[1].strip()

                if level not in ("supervised", "semi", "autonomous"):

                    self.log_line("Autonomy must be one of: supervised, semi, autonomous")

                    return

                self.autonomy_level = level

                self.memory.set("autonomy_level", level)

                self.log_line(f"Autonomy set to {level}")

                return



            if lowered.startswith("purpose"):
                value = cmd.split(" ", 1)[1].strip() if " " in cmd else ""
                if value.lower() in ("", "clear", "none"):
                    self.purpose = ""
                    self.memory.set("purpose", "")
                    self.log_line("Purpose cleared.")
                else:
                    self.purpose = value
                    self.memory.set("purpose", value)
                    self.log_line("Purpose set.")
                return

            if lowered == "jobs":
                rows = self.jobs.list(10)
                out = "\n".join(f"{r['id']} {r['status']} {r['command']}" for r in rows) or "No jobs."
                self.log_line(out)
                return


            level = getattr(self, "autonomy_level", None) or getattr(self.settings, "autonomy_level", "semi")

            if level == "autonomous" and not self.purpose and lowered not in ("confirm",):
                self.log_line("Set a purpose first: purpose <text>")
                return

            for name in self.tools.tools.keys():

                prefix = f"{name} "

                if lowered.startswith(prefix):

                    args = cmd[len(prefix):].strip()

                    tool_risk = self.tools.specs.get(name).risk if name in self.tools.specs else "safe"

                    if requires_confirmation(tool_risk, level) and not lowered.startswith("confirm"):

                        payload = json.dumps({"type": "tool", "name": name, "args": args})

                        self.memory.set("pending_action", payload)

                        out = "This action requires confirmation. Type 'confirm' to proceed."

                        self.log_line(out)

                        return

                    try:

                        out = self._execute_tool(name, args)

                    except ToolNeedsConfirmation:

                        payload = json.dumps({"type": "tool", "name": name, "args": args})

                        self.memory.set("pending_action", payload)

                        out = "This action may be destructive. Type 'confirm' to proceed."

                    self.log_line(out)

                    return



            if lowered.startswith("index ") or lowered.startswith("rag ") or lowered.startswith("deep_research ") or lowered.startswith("ocr "):

                self._execute_step(cmd)

                return



            job_id = self.jobs.create(cmd)

            output = self._orchestrate(cmd)

            self.jobs.update(job_id, "done", output or "")

            self.log_line(output)

        except Exception as e:

            self.metrics.inc("tasks_failed")

            self.log_line(f"Error: {e}")

        finally:

            self.metrics.set_timer("last_task_seconds", time.time() - start)

            self.metrics.inc("tasks_completed")





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

            if self.path == "/api/metrics":
                body = json.dumps(app.metrics.snapshot()).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if self.path == "/api/trace":
                body = json.dumps(app.memory.recent_events(50)).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if self.path == "/api/jobs":
                body = json.dumps(app.jobs.list(20)).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if self.path == "/api/a2a":
                body = json.dumps(app.a2a.recent(20)).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
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

    <pre id="metrics"></pre>

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

        await refreshMetrics();

      }

      async function refreshMetrics() {

        const res = await fetch('/api/metrics');

        const data = await res.json();

        document.getElementById('metrics').textContent = JSON.stringify(data, null, 2);

      }

      refreshMetrics();

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

                app.task_queue.enqueue_and_wait(lambda: app._execute(command))

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

    memory = MemoryStore(settings.memory_db, settings.embedding_dim)

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

