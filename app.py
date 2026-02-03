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

from multimodal import ocr_pdf, capture_screenshot
from audio_io import record_and_transcribe, speak_text
from cognitive import slow_mode, dot_ensemble
from graph_rag import GraphStore
from workflows import run_workflow
from perception import collect_observation

from router import choose_model

from policy import requires_confirmation
from job_store import JobStore
from team import TeamOrchestrator, AgentRole
from a2a import A2ABus
from mcp_adapter import MCPAdapter
from privacy import redact_text
from cost import estimate_tokens, estimate_cost
from data_quality import profile_tabular
from playbook_tools import (
    interface_checklist,
    personalization_checklist,
    ai_marketing_checklist,
    strategic_planning_checklist,
    default_personas,
    synthetic_test_prompt,
)
from micro_saas_tools import (
    parse_assumption,
    format_assumptions,
    roadmap_12_weeks,
    pricing_simulator,
    gtm_channel_plan,
    data_moat_prompt,
    aha_validator,
    compliance_checklist,
    load_assumptions,
    dump_assumptions,
)
from research_store import ResearchStore
from automotive_agents import (
    ownership_companion_prompt,
    dealer_assist_prompt,
    mobile_work_prompt,
    audio_ai_checklist,
)
from agent_profiles import (
    agent_types_summary,
    default_persona_templates,
    misalignment_checklist,
    readiness_framework,
)
from coding_trends import (
    sdlc_shift_summary,
    oversight_scaling_checklist,
    security_first_checklist,
    agent_surfaces_summary,
)
from bdi_tools import agentic_pillars_summary, vertical_agent_templates
from r2e_tools import write_r2e_index


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





def _configure_agent(settings, instruction: str = "", prefer_offline: bool = False):
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

    if openai_key and not prefer_offline:
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
        self.graph = GraphStore(self.memory._conn)
        self.research = ResearchStore(self.memory._conn)
        self.jobs = JobStore(self.memory._conn)
        self.a2a = A2ABus(self.memory)
        self.mcp = MCPAdapter()
        self.slow_mode = False
        self.dot_mode = False


        tool_prefixes = list(self.tools.tools.keys())

        tool_prefixes.append("index")
        tool_prefixes.append("rag")
        tool_prefixes.append("deep_research")
        tool_prefixes.append("ocr")
        tool_prefixes.append("screenshot")
        tool_prefixes.append("listen")
        tool_prefixes.append("speak")
        tool_prefixes.append("a2a")
        tool_prefixes.append("mcp")
        tool_prefixes.append("data_profile")
        tool_prefixes.append("ai_interface")
        tool_prefixes.append("rag_sources")
        tool_prefixes.append("rag_rank")
        tool_prefixes.append("simulate")
        tool_prefixes.append("explain")
        tool_prefixes.append("telemetry")
        tool_prefixes.append("personalization")
        tool_prefixes.append("ai_marketing")
        tool_prefixes.append("strategy")
        tool_prefixes.append("assumption_add")
        tool_prefixes.append("assumption_list")
        tool_prefixes.append("roadmap12")
        tool_prefixes.append("pricing_sim")
        tool_prefixes.append("gtm_plan")
        tool_prefixes.append("data_moat")
        tool_prefixes.append("aha_validate")
        tool_prefixes.append("compliance")
        tool_prefixes.append("synthetic_test")
        tool_prefixes.append("lit_review")
        tool_prefixes.append("analysis_plan")
        tool_prefixes.append("hypothesis")
        tool_prefixes.append("experiment")
        tool_prefixes.append("experiment_update")
        tool_prefixes.append("incident")
        tool_prefixes.append("incidents")
        tool_prefixes.append("eval_run")
        tool_prefixes.append("evals")
        tool_prefixes.append("deployment_gate")
        tool_prefixes.append("red_team")
        tool_prefixes.append("ownership_companion")
        tool_prefixes.append("dealer_assist")
        tool_prefixes.append("mobile_work")
        tool_prefixes.append("audio_ai")
        tool_prefixes.append("edge_mode")
        tool_prefixes.append("profile")
        tool_prefixes.append("persona_add")
        tool_prefixes.append("personas")
        tool_prefixes.append("persona_templates")
        tool_prefixes.append("agent_types")
        tool_prefixes.append("misalignment_check")
        tool_prefixes.append("readiness_framework")
        tool_prefixes.append("long_run")
        tool_prefixes.append("long_run_update")
        tool_prefixes.append("long_runs")
        tool_prefixes.append("oversight_rule")
        tool_prefixes.append("oversight_rules")
        tool_prefixes.append("agent_team")
        tool_prefixes.append("sdlc_shift")
        tool_prefixes.append("oversight_scaling")
        tool_prefixes.append("security_first")
        tool_prefixes.append("agent_surfaces")
        tool_prefixes.append("pillars")
        tool_prefixes.append("vertical_agents")
        tool_prefixes.append("workflow")
        tool_prefixes.append("slow_mode")
        tool_prefixes.append("dot_mode")
        tool_prefixes.append("graph_query")
        tool_prefixes.append("perception")
        tool_prefixes.append("belief")
        tool_prefixes.append("beliefs")
        tool_prefixes.append("desire")
        tool_prefixes.append("desires")
        tool_prefixes.append("intention")
        tool_prefixes.append("intentions")
        tool_prefixes.append("action_space_add")
        tool_prefixes.append("action_space_list")
        tool_prefixes.append("action_space_remove")
        tool_prefixes.append("checkpoint")
        tool_prefixes.append("checkpoints")
        tool_prefixes.append("rollback_note")
        tool_prefixes.append("reflect")
        tool_prefixes.append("r2e_index")
        tool_prefixes.append("lab_note")
        tool_prefixes.append("readiness")
        tool_prefixes.append("governance")
        tool_prefixes.append("agent")
        self.planner = PlannerAgent([f"{p} " for p in tool_prefixes])

        self.retriever = RetrieverAgent(self.memory)

        self.executor = ExecutorAgent(self._execute_step)

        self.verifier = VerifierAgent()

        self.deep_research = DeepResearch(self._agent_chat, self._rag_search)

        self.autonomy_level = self.memory.get("autonomy_level") or settings.autonomy_level

        self.purpose = self.memory.get("purpose") or settings.purpose
        self.analysis_mode = self.memory.get("analysis_mode") or "fast"
        self.redact_logs = settings.redact_logs.lower() == "true"
        self.memory.purge_events(settings.event_retention_seconds)

        self.team = TeamOrchestrator(self._agent_chat)
        self.edge_mode = self.memory.get("edge_mode") or "auto"
        self.agent_profile = self.memory.get("agent_profile") or ""



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


    def _readiness_report(self) -> str:
        stats = self.rag.stats()
        purpose = getattr(self, "purpose", "")
        governance = []
        if not purpose:
            governance.append("Set a purpose (purpose <text>)")
        if self.settings.allowed_paths:
            governance.append("Path allowlist set")
        else:
            governance.append("Set AGENTIC_ALLOWED_PATHS")
        if self.settings.allowed_domains:
            governance.append("Domain allowlist set")
        else:
            governance.append("Set AGENTIC_ALLOWED_DOMAINS")
        governance.append(f"Redaction: {self.settings.redact_logs}")
        data_lines = [f"RAG chunks: {stats['chunks']}", f"RAG sources: {stats['sources']}"]
        if stats['chunks'] == 0:
            data_lines.append("Index documents with: index <path>")
        data_lines.append("List RAG sources with: rag_sources")
        data_lines.append("Rank RAG source with: rag_rank <source> <rank>")
        tech = []
        has_openai = bool(os.getenv("OPENAI_API_KEY"))
        has_ollama = bool(os.getenv("OLLAMA_MODEL") or self.settings.ollama_model)
        tech.append(f"OpenAI key: {'yes' if has_openai else 'no'}")
        tech.append(f"Ollama model: {'yes' if has_ollama else 'no'}")
        tech.append(f"Edge mode: {getattr(self, 'edge_mode', 'auto')}")
        tech.append(f"Web UI: http://{self.settings.server_host}:{self.settings.server_port}")
        tech.append("Explain routing with: explain <query>")
        tech.append("Telemetry snapshot: telemetry")
        culture = ["Use team <task> for cross-role review", "Adopt change-management playbooks"]
        lines = ["AI Readiness Snapshot", "", "Strategy & Governance:"]
        lines.extend([f"- {g}" for g in governance])
        lines.append("")
        lines.append("Data Foundations:")
        lines.extend([f"- {d}" for d in data_lines])
        lines.append("")
        lines.append("Technology & Tools:")
        lines.extend([f"- {t}" for t in tech])
        lines.append("")
        lines.append("Talent & Culture:")
        lines.extend([f"- {c}" for c in culture])
        return "\n".join(lines)

    def _deployment_gate(self) -> str:
        checks = []
        ok = True
        purpose = getattr(self, "purpose", "")
        if purpose:
            checks.append("Purpose set: ok")
        else:
            checks.append("Purpose set: missing")
            ok = False
        if self.settings.allowed_paths:
            checks.append("Path allowlist: ok")
        else:
            checks.append("Path allowlist: missing")
            ok = False
        if self.settings.allowed_domains:
            checks.append("Domain allowlist: ok")
        else:
            checks.append("Domain allowlist: missing")
            ok = False
        evals = self.memory.list_evaluations(5)
        recent_eval = evals[0] if evals else None
        if recent_eval:
            checks.append("Recent eval: ok")
        else:
            checks.append("Recent eval: missing")
            ok = False
        incidents = self.memory.list_incidents(20)
        critical = any(i["severity"].lower() in ("critical", "high") for i in incidents)
        if critical:
            checks.append("Critical incidents: present")
            ok = False
        else:
            checks.append("Critical incidents: none")
        status = "PASS" if ok else "FAIL"
        return "Deployment Gate: " + status + "\n" + "\n".join(f"- {c}" for c in checks)

    def _governance_checklist(self) -> str:
        items = [
            "Define AI purpose and success criteria",
            "Treat AI like a new employee: onboarding, supervision, monitoring",
            "Validate data quality and document known limitations",
            "Complete legal/compliance approval gates before production",
            "Establish human review for high-impact decisions",
            "Monitor drift, errors, and user feedback",
        ]
        red_flags = [
            "No documented purpose or owner",
            "No approval/validation workflow",
            "Unknown data lineage or quality",
            "Unbounded tool access",
        ]
        lines = ["Governance Checklist", ""]
        lines.extend([f"- {i}" for i in items])
        lines.append("")
        lines.append("Red Flags")
        lines.extend([f"- {r}" for r in red_flags])
        return "\n".join(lines)

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
        if getattr(self, "dot_mode", False):
            return dot_ensemble(self._agent_chat_base, instruction)
        if getattr(self, "slow_mode", False):
            return slow_mode(self._agent_chat_base, instruction)
        return self._agent_chat_base(instruction)

    def _agent_chat_base(self, instruction):

        prefer_offline = getattr(self, "edge_mode", "auto") == "offline"
        model_name = _configure_agent(self.settings, instruction, prefer_offline=prefer_offline)

        oi_interpreter.auto_run = True

        oi_interpreter.system_message = (

            "You are ChatGPT with full access to the user's computer and browser. "

            "When the user asks for actions, perform them directly. "

            "When the user asks for information or conversation, respond normally. "

            "Always be concise and confirm destructive actions."

        )

        purpose = getattr(self, "purpose", "")
        mode = getattr(self, "analysis_mode", "fast")
        if mode == "rigorous":
            oi_interpreter.system_message += (
                " Use checkable steps, verify calculations, and cite sources where possible."
            )
        if purpose:
            oi_interpreter.system_message += f" Current purpose: {purpose}."
        profile = getattr(self, "agent_profile", "")
        if profile:
            oi_interpreter.system_message += f" Current profile: {profile}."

        context = self.retriever.retrieve(instruction)

        if context:

            instruction = f"Context:\n{context}\n\nUser: {instruction}"

        self._add_message("user", instruction)

        self.memory.add_memory("short", f"USER: {instruction}", ttl_seconds=self.settings.short_memory_ttl)

        extra = {"model": model_name or ""}
        self._log_event("instruction", instruction, extra)

        logging.info("instruction: %s", self._maybe_redact(instruction))

        buf = io.StringIO()
        start = time.time()

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

        latency = time.time() - start
        tokens_in = estimate_tokens(instruction)
        tokens_out = estimate_tokens(output)
        is_openai = bool(os.getenv("OPENAI_API_KEY")) and not oi_interpreter.offline
        if is_openai:
            cost = estimate_cost(
                tokens_in,
                tokens_out,
                self.settings.openai_cost_input_per_million,
                self.settings.openai_cost_output_per_million,
            )
        else:
            cost = estimate_cost(
                tokens_in,
                tokens_out,
                self.settings.ollama_cost_input_per_million,
                self.settings.ollama_cost_output_per_million,
            )
        self.memory.log_model_run(model_name or "", tokens_in, tokens_out, cost, latency)

        return output



    def _execute_tool(self, name: str, args: str, confirm: bool = False, dry_run: bool = False):

        ctx = ToolContext(confirm=confirm, dry_run=dry_run)

        if not hasattr(self, "_tool_calls_this_task"):
            self._tool_calls_this_task = 0
        max_calls = getattr(self.settings, "max_tool_calls_per_task", 0)
        if max_calls and self._tool_calls_this_task >= max_calls:
            self.metrics.inc("tool_budget_exceeded")
            raise RuntimeError("Tool call budget exceeded for this task")
        self._tool_calls_this_task += 1
        self.metrics.add_tool_call(name)

        self._log_event("tool", json.dumps({"name": name, "args": args}))

        return self.tools.execute(name, args, ctx)



    def _rag_search(self, query: str, limit: int = 5):

        return self.rag.search(query, limit=limit)

    def _explain_query(self, query: str) -> str:
        route = choose_model(query)
        memory_hits = self.retriever.retrieve(query)
        evidence = self._rag_search(query, limit=5)
        tool_hint = None
        lowered = query.lower().strip()
        for name in self.tools.tools.keys():
            if lowered.startswith(f"{name} "):
                tool_hint = name
                break
        lines = [f"Model route: {route}"]
        if tool_hint:
            lines.append(f"Tool hint: {tool_hint}")
        if memory_hits:
            lines.append("Memory hits:")
            lines.append(memory_hits)
        if evidence:
            lines.append("Top evidence:")
            for item in evidence:
                score = item.get("score", 0.0)
                rank = item.get("source_rank", 0.0)
                chunk = item.get("chunk_index")
                lines.append(f"- {item.get('source')}#chunk{chunk} score={score:.3f} rank={rank:.2f}")
        if not memory_hits and not evidence:
            lines.append("No memory or evidence hits found.")
        return "\n".join(lines)



    def _execute_step(self, step: str):

        lowered = step.strip().lower()

        if lowered.startswith("simulate "):
            payload = step[len("simulate "):].strip()
            if not payload or " " not in payload:
                raise RuntimeError("simulate requires: simulate <tool> <args>")
            name, args = payload.split(" ", 1)
            out = self._execute_tool(name.strip(), args.strip(), dry_run=True)
            self.log_line(out)
            return

        if lowered == "rag_sources":
            sources = self.rag.list_sources()
            if not sources:
                self.log_line("No RAG sources indexed.")
                return
            for item in sources:
                source = item.get("source")
                chunks = item.get("chunks")
                avg_rank = item.get("avg_rank", 0.0)
                self.log_line(f"{source}: chunks={chunks} rank={avg_rank:.2f}")
            return

        if lowered.startswith("rag_rank "):
            parts = step.split(" ", 2)
            if len(parts) < 3:
                raise RuntimeError("rag_rank requires: rag_rank <source> <rank>")
            source = parts[1].strip()
            try:
                rank = float(parts[2].strip())
            except Exception:
                raise RuntimeError("rag_rank requires a numeric rank")
            updated = self.rag.set_source_rank(source, rank)
            self.log_line(f"Updated {updated} chunks for {source} (rank={rank:.2f})")
            return

        if lowered.startswith("assumption_add "):
            raw = step[len("assumption_add "):].strip()
            assumption = parse_assumption(raw)
            existing = load_assumptions(self.memory.get("market_assumptions") or "")
            existing.append(assumption)
            self.memory.set("market_assumptions", dump_assumptions(existing))
            self.log_line(f"Added assumption: {assumption.label}")
            return

        if lowered == "assumption_list":
            items = load_assumptions(self.memory.get("market_assumptions") or "")
            self.log_line(format_assumptions(items))
            return

        if lowered.startswith("roadmap12 "):
            niche = step[len("roadmap12 "):].strip()
            if not niche:
                raise RuntimeError("roadmap12 requires a niche")
            self.log_line(roadmap_12_weeks(niche))
            return

        if lowered.startswith("pricing_sim "):
            parts = step.split()
            if len(parts) < 3:
                raise RuntimeError("pricing_sim requires: pricing_sim <price> <target_mrr>")
            price = float(parts[1])
            target = float(parts[2])
            self.log_line(pricing_simulator(price, target))
            return

        if lowered.startswith("gtm_plan "):
            niche = step[len("gtm_plan "):].strip()
            if not niche:
                raise RuntimeError("gtm_plan requires a niche")
            self.log_line(gtm_channel_plan(niche))
            return

        if lowered.startswith("data_moat "):
            niche = step[len("data_moat "):].strip()
            if not niche:
                raise RuntimeError("data_moat requires a niche")
            self.log_line(data_moat_prompt(niche))
            return

        if lowered.startswith("aha_validate "):
            niche = step[len("aha_validate "):].strip()
            if not niche:
                raise RuntimeError("aha_validate requires a niche")
            self.log_line(aha_validator(niche))
            return

        if lowered == "compliance":
            self.log_line(compliance_checklist())
            return

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



        if lowered.startswith("data_profile "):
            path = step[len("data_profile "):].strip()
            report = profile_tabular(path)
            self.log_line(report)
            return

        if lowered.startswith("ai_interface"):
            self.log_line(interface_checklist())
            return

        if lowered.startswith("personalization"):
            self.log_line(personalization_checklist())
            return

        if lowered.startswith("ai_marketing"):
            self.log_line(ai_marketing_checklist())
            return

        if lowered.startswith("strategy"):
            self.log_line(strategic_planning_checklist())
            return

        if lowered.startswith("synthetic_test "):
            scenario = step[len("synthetic_test "):].strip()
            personas = default_personas()
            prompt = synthetic_test_prompt(scenario, personas)
            output = self._agent_chat(prompt)
            self.log_line(output or "Agent task completed")
            return

        if lowered.startswith("lit_review "):
            query = step[len("lit_review "):].strip()
            evidence = self._rag_search(query, limit=7)
            if not evidence:
                self.log_line("No evidence found. Index documents first.")
                return
            ev_text = "\n".join(f"- {e['source']}: {e['text'][:200]}" for e in evidence)
            prompt = ("Summarize the literature from the evidence below. "
                      "Include key claims, limitations, and open questions. "
                      "Cite sources by name.\n\nEvidence:\n" + ev_text)
            answer = self._agent_chat(prompt)
            self.log_line(answer or "Agent task completed")
            return

        if lowered.startswith("analysis_plan "):
            question = step[len("analysis_plan "):].strip()
            prompt = ("Create a rigorous analysis plan with steps, data needed, "
                      "verification checks, and expected outputs for: " + question)
            answer = self._agent_chat(prompt)
            self.log_line(answer or "Agent task completed")
            return

        if lowered.startswith("ownership_companion "):
            task = step[len("ownership_companion "):].strip()
            output = self._agent_chat(ownership_companion_prompt(task))
            self.log_line(output or "Agent task completed")
            return

        if lowered.startswith("dealer_assist "):
            task = step[len("dealer_assist "):].strip()
            output = self._agent_chat(dealer_assist_prompt(task))
            self.log_line(output or "Agent task completed")
            return

        if lowered.startswith("mobile_work "):
            task = step[len("mobile_work "):].strip()
            output = self._agent_chat(mobile_work_prompt(task))
            self.log_line(output or "Agent task completed")
            return

        if lowered == "audio_ai":
            self.log_line(audio_ai_checklist())
            return

        if lowered == "persona_templates":
            self.log_line(default_persona_templates())
            return

        if lowered == "agent_types":
            self.log_line(agent_types_summary())
            return

        if lowered == "misalignment_check":
            self.log_line(misalignment_checklist())
            return

        if lowered == "readiness_framework":
            self.log_line(readiness_framework())
            return

        if lowered == "sdlc_shift":
            self.log_line(sdlc_shift_summary())
            return

        if lowered == "oversight_scaling":
            self.log_line(oversight_scaling_checklist())
            return

        if lowered == "security_first":
            self.log_line(security_first_checklist())
            return

        if lowered == "agent_surfaces":
            self.log_line(agent_surfaces_summary())
            return

        if lowered == "pillars":
            self.log_line(agentic_pillars_summary())
            return

        if lowered == "vertical_agents":
            self.log_line(vertical_agent_templates())
            return

        if lowered.startswith("reflect "):
            question = step[len("reflect "):].strip()
            draft = self._agent_chat(f"Draft a concise answer: {question}")
            critique = self._agent_chat(f"Critique this answer for gaps and errors:\n{draft}")
            final = self._agent_chat(
                f"Revise the answer using the critique.\nAnswer:\n{draft}\n\nCritique:\n{critique}"
            )
            self.log_line(final or "Agent task completed")
            return

        if lowered.startswith("lab_note "):
            note = step[len("lab_note "):].strip()
            self.memory.add_memory("lab_note", note, ttl_seconds=self.settings.long_memory_ttl)
            self.log_line("Lab note saved.")
            return

        if lowered.startswith("red_team "):
            scenario = step[len("red_team "):].strip()
            prompt = ("You are a red-team evaluator. Identify misuse risks, "
                      "security weaknesses, and mitigations for: " + scenario)
            output = self._agent_chat(prompt)
            self.log_line(output or "Agent task completed")
            return

        if lowered == "deployment_gate":
            self.log_line(self._deployment_gate())
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

        if lowered.startswith("screenshot "):
            path = step[len("screenshot "):].strip()
            try:
                saved = capture_screenshot(path)
                self.log_line(f"Screenshot saved: {saved}")
            except Exception as exc:
                self.log_line(f"Screenshot failed: {exc}")
            return

        if lowered.startswith("listen"):
            parts = step.split(" ", 1)
            seconds = 5
            if len(parts) > 1 and parts[1].strip():
                try:
                    seconds = int(parts[1].strip())
                except Exception:
                    seconds = 5
            try:
                text = record_and_transcribe(seconds=seconds)
                self.log_line(text or "No speech detected.")
            except Exception as exc:
                self.log_line(f"Listen failed: {exc}")
            return

        if lowered.startswith("speak "):
            text = step[len("speak "):].strip()
            if not text:
                self.log_line("speak requires text")
                return
            try:
                speak_text(text)
                self.log_line("Spoken.")
            except Exception as exc:
                self.log_line(f"Speak failed: {exc}")
            return

        if lowered.startswith("workflow "):
            raw = step[len("workflow "):].strip()
            if "|" not in raw:
                self.log_line("workflow requires: workflow name | payload")
                return
            name, payload = [s.strip() for s in raw.split("|", 1)]
            try:
                output = run_workflow(name, payload)
                self.log_line(output)
            except Exception as exc:
                self.log_line(f"workflow error: {exc}")
            return

        if lowered.startswith("slow_mode"):
            parts = step.split(" ", 1)
            value = parts[1].strip().lower() if len(parts) > 1 else ""
            if value in ("on", "true", "1"):
                self.slow_mode = True
            elif value in ("off", "false", "0"):
                self.slow_mode = False
            else:
                self.log_line("slow_mode requires: slow_mode on|off")
                return
            self.log_line(f"Slow mode {'enabled' if self.slow_mode else 'disabled'}.")
            return

        if lowered.startswith("dot_mode"):
            parts = step.split(" ", 1)
            value = parts[1].strip().lower() if len(parts) > 1 else ""
            if value in ("on", "true", "1"):
                self.dot_mode = True
            elif value in ("off", "false", "0"):
                self.dot_mode = False
            else:
                self.log_line("dot_mode requires: dot_mode on|off")
                return
            self.log_line(f"DoT mode {'enabled' if self.dot_mode else 'disabled'}.")
            return

        if lowered.startswith("graph_query "):
            entity = step[len("graph_query "):].strip()
            results = self.graph.neighbors(entity)
            if not results:
                self.log_line("No graph neighbors found.")
                return
            self.log_line(json.dumps(results))
            return

        if lowered.startswith("perception"):
            parts = step.split(" ", 1)
            path = parts[1].strip() if len(parts) > 1 else ""
            try:
                observation = collect_observation(path if path else None)
                self.log_line(json.dumps(observation))
            except Exception as exc:
                self.log_line(f"perception error: {exc}")
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
            max_steps = getattr(self.settings, "max_plan_steps", 0)
            if max_steps and len(plan) > max_steps:
                self._log_event(
                    "plan_guard",
                    json.dumps({
                        "limit": max_steps,
                        "original_steps": len(plan),
                    }),
                )
                plan = plan[:max_steps]
                self.log_line(f"Plan truncated to {max_steps} steps due to budget.")

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

            self._tool_calls_this_task = 0

            if not hasattr(self, "purpose"):
                self.purpose = ""
            if not hasattr(self, "redact_logs"):
                self.redact_logs = False

            if "remember" in lowered or "note this" in lowered:

                self.memory.add_memory("long", cmd, ttl_seconds=self.settings.long_memory_ttl)

            if lowered == "telemetry":
                snapshot = self.metrics.snapshot()
                self.log_line(json.dumps(snapshot, indent=2))
                return

            if lowered.startswith("explain "):
                query = cmd[len("explain "):].strip()
                if not query:
                    raise RuntimeError("explain requires a query")
                self.log_line(self._explain_query(query))
                return

            if lowered.startswith("assumption_add "):
                raw = cmd[len("assumption_add "):].strip()
                assumption = parse_assumption(raw)
                existing = load_assumptions(self.memory.get("market_assumptions") or "")
                existing.append(assumption)
                self.memory.set("market_assumptions", dump_assumptions(existing))
                self.log_line(f"Added assumption: {assumption.label}")
                return

            if lowered == "assumption_list":
                items = load_assumptions(self.memory.get("market_assumptions") or "")
                self.log_line(format_assumptions(items))
                return

            if lowered.startswith("roadmap12 "):
                niche = cmd[len("roadmap12 "):].strip()
                if not niche:
                    raise RuntimeError("roadmap12 requires a niche")
                self.log_line(roadmap_12_weeks(niche))
                return

            if lowered.startswith("pricing_sim "):
                parts = cmd.split()
                if len(parts) < 3:
                    raise RuntimeError("pricing_sim requires: pricing_sim <price> <target_mrr>")
                price = float(parts[1])
                target = float(parts[2])
                self.log_line(pricing_simulator(price, target))
                return

            if lowered.startswith("gtm_plan "):
                niche = cmd[len("gtm_plan "):].strip()
                if not niche:
                    raise RuntimeError("gtm_plan requires a niche")
                self.log_line(gtm_channel_plan(niche))
                return

            if lowered.startswith("data_moat "):
                niche = cmd[len("data_moat "):].strip()
                if not niche:
                    raise RuntimeError("data_moat requires a niche")
                self.log_line(data_moat_prompt(niche))
                return

            if lowered.startswith("aha_validate "):
                niche = cmd[len("aha_validate "):].strip()
                if not niche:
                    raise RuntimeError("aha_validate requires a niche")
                self.log_line(aha_validator(niche))
                return

            if lowered == "compliance":
                self.log_line(compliance_checklist())
                return



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



            if lowered.startswith("mode "):
                value = lowered.split(" ", 1)[1].strip()
                if value not in ("fast", "rigorous"):
                    self.log_line("Mode must be fast or rigorous")
                    return
                self.analysis_mode = value
                self.memory.set("analysis_mode", value)
                self.log_line(f"Mode set to {value}")
                return

            if lowered.startswith("edge_mode "):
                value = lowered.split(" ", 1)[1].strip()
                if value not in ("offline", "online", "auto"):
                    self.log_line("edge_mode must be offline, online, or auto")
                    return
                self.edge_mode = value
                self.memory.set("edge_mode", value)
                self.log_line(f"Edge mode set to {value}")
                return

            if lowered.startswith("profile "):
                value = cmd.split(" ", 1)[1].strip() if " " in cmd else ""
                if value.lower() in ("", "clear", "none"):
                    self.agent_profile = ""
                    self.memory.set("agent_profile", "")
                    self.log_line("Profile cleared.")
                else:
                    self.agent_profile = value
                    self.memory.set("agent_profile", value)
                    self.log_line("Profile set.")
                return

            if lowered == "profile":
                current = getattr(self, "agent_profile", "")
                self.log_line(current or "No profile set.")
                return

            if lowered.startswith("persona_add "):
                raw = cmd.split(" ", 1)[1] if " " in cmd else ""
                parts = [s.strip() for s in raw.split("|", 2)]
                if len(parts) < 2:
                    self.log_line("persona_add requires: persona_add <name> | <role> | <constraints>")
                    return
                name = parts[0]
                role = parts[1]
                constraints = parts[2] if len(parts) > 2 else ""
                pid = self.memory.add_persona(name, role, constraints, owner=self.purpose or "")
                self.log_line(f"Persona saved: {pid}")
                return

            if lowered == "personas":
                rows = self.memory.list_personas(10)
                out = "\n".join(
                    f"{r['id']} {r['name']} {r['role']}"
                    for r in rows
                ) or "No personas."
                self.log_line(out)
                return

            if lowered.startswith("belief "):
                text = cmd.split(" ", 1)[1].strip()
                bid = self.memory.add_bdi("belief", text, owner=self.purpose or "")
                self.log_line(f"Belief saved: {bid}")
                return

            if lowered == "beliefs":
                rows = self.memory.list_bdi("belief", 10)
                out = "\n".join(f"{r['id']} {r['text']}" for r in rows) or "No beliefs."
                self.log_line(out)
                return

            if lowered.startswith("desire "):
                text = cmd.split(" ", 1)[1].strip()
                did = self.memory.add_bdi("desire", text, owner=self.purpose or "")
                self.log_line(f"Desire saved: {did}")
                return

            if lowered == "desires":
                rows = self.memory.list_bdi("desire", 10)
                out = "\n".join(f"{r['id']} {r['text']}" for r in rows) or "No desires."
                self.log_line(out)
                return

            if lowered.startswith("intention "):
                text = cmd.split(" ", 1)[1].strip()
                iid = self.memory.add_bdi("intention", text, owner=self.purpose or "")
                self.log_line(f"Intention saved: {iid}")
                return

            if lowered == "intentions":
                rows = self.memory.list_bdi("intention", 10)
                out = "\n".join(f"{r['id']} {r['text']}" for r in rows) or "No intentions."
                self.log_line(out)
                return

            if lowered.startswith("action_space_add "):
                raw = cmd.split(" ", 1)[1] if " " in cmd else ""
                if "|" not in raw:
                    self.log_line("action_space_add requires: action_space_add <name> | <description>")
                    return
                name, desc = [s.strip() for s in raw.split("|", 1)]
                aid = self.memory.add_action_space(name, desc)
                self.log_line(f"Action space saved: {aid}")
                return

            if lowered == "action_space_list":
                rows = self.memory.list_action_space(50)
                out = "\n".join(f"{r['name']}: {r['description']}" for r in rows) or "No action space."
                self.log_line(out)
                return

            if lowered.startswith("action_space_remove "):
                name = cmd.split(" ", 1)[1].strip()
                self.memory.remove_action_space(name)
                self.log_line("Action space removed.")
                return

            if lowered.startswith("checkpoint "):
                label = cmd.split(" ", 1)[1].strip()
                cid = self.memory.add_checkpoint(label)
                self.log_line(f"Checkpoint saved: {cid}")
                return

            if lowered == "checkpoints":
                rows = self.memory.list_checkpoints(10)
                out = "\n".join(f"{r['id']} {r['label']}" for r in rows) or "No checkpoints."
                self.log_line(out)
                return

            if lowered.startswith("rollback_note "):
                raw = cmd.split(" ", 1)[1] if " " in cmd else ""
                parts = [s.strip() for s in raw.split("|", 1)]
                if len(parts) < 2:
                    self.log_line("rollback_note requires: rollback_note <checkpoint_id> | <notes>")
                    return
                try:
                    cid = int(parts[0])
                except Exception:
                    self.log_line("rollback_note requires numeric id")
                    return
                self.memory.update_checkpoint(cid, parts[1])
                self.log_line("Rollback note saved.")
                return

            if lowered.startswith("r2e_index "):
                repo_path = cmd.split(" ", 1)[1].strip()
                out_path = write_r2e_index(repo_path, "evals/r2e_index.tsv")
                self.log_line(f"R2E index written: {out_path}")
                return

            if lowered.startswith("long_run "):
                raw = cmd.split(" ", 1)[1] if " " in cmd else ""
                if "|" not in raw:
                    self.log_line("long_run requires: long_run <title> | <milestones>")
                    return
                title, milestones = [s.strip() for s in raw.split("|", 1)]
                rid = self.memory.add_long_run(title, milestones)
                self.log_line(f"Long run saved: {rid}")
                return

            if lowered.startswith("long_run_update "):
                raw = cmd.split(" ", 1)[1] if " " in cmd else ""
                parts = [s.strip() for s in raw.split("|", 2)]
                if len(parts) < 2:
                    self.log_line("long_run_update requires: long_run_update <id> | <status> | <note>")
                    return
                try:
                    run_id = int(parts[0])
                except Exception:
                    self.log_line("long_run_update requires numeric id")
                    return
                status = parts[1]
                note = parts[2] if len(parts) > 2 else ""
                self.memory.update_long_run(run_id, status, note)
                self.log_line("Long run updated.")
                return

            if lowered == "long_runs":
                rows = self.memory.list_long_runs(10)
                out = "\n".join(
                    f"{r['id']} {r['status']} {r['title']}"
                    for r in rows
                ) or "No long runs."
                self.log_line(out)
                return

            if lowered.startswith("oversight_rule "):
                raw = cmd.split(" ", 1)[1] if " " in cmd else ""
                if "|" not in raw:
                    self.log_line("oversight_rule requires: oversight_rule <rule> | <severity>")
                    return
                rule, severity = [s.strip() for s in raw.split("|", 1)]
                oid = self.memory.add_oversight_rule(rule, severity)
                self.log_line(f"Oversight rule saved: {oid}")
                return

            if lowered == "oversight_rules":
                rows = self.memory.list_oversight_rules(10)
                out = "\n".join(
                    f"{r['id']} {r['severity']} {r['rule']}"
                    for r in rows
                ) or "No oversight rules."
                self.log_line(out)
                return

            if lowered.startswith("agent_team "):
                task = cmd.split(" ", 1)[1].strip()
                roles = [
                    AgentRole("Planner", "Create a brief plan."),
                    AgentRole("Builder", "Execute the plan or draft the solution."),
                    AgentRole("Reviewer", "Review for issues and improvements."),
                    AgentRole("Security", "Check for security risks or dual-use concerns."),
                    AgentRole("QA", "Validate correctness and edge cases."),
                ]
                output = self.team.run(roles, task)
                self.log_line(output)
                return

            if lowered.startswith("hypothesis "):
                text = cmd.split(" ", 1)[1].strip() if " " in cmd else ""
                if not text:
                    self.log_line("hypothesis requires text")
                    return
                if hasattr(self, "research"):
                    hid = self.research.add_hypothesis(text)
                    self.log_line(f"Hypothesis saved: {hid}")
                else:
                    self.log_line("Research store unavailable")
                return

            if lowered == "hypotheses":
                if hasattr(self, "research"):
                    rows = self.research.list_hypotheses(10)
                    out = "\n".join(f"{r['id']} {r['status']} {r['text']}" for r in rows) or "No hypotheses."
                    self.log_line(out)
                else:
                    self.log_line("Research store unavailable")
                return

            if lowered.startswith("experiment "):
                raw = cmd.split(" ", 1)[1] if " " in cmd else ""
                if "|" not in raw:
                    self.log_line("experiment requires: experiment <title> | <plan>")
                    return
                title, plan = [s.strip() for s in raw.split("|", 1)]
                if hasattr(self, "research"):
                    eid = self.research.add_experiment(title, plan)
                    self.log_line(f"Experiment saved: {eid}")
                else:
                    self.log_line("Research store unavailable")
                return

            if lowered == "experiments":
                if hasattr(self, "research"):
                    rows = self.research.list_experiments(10)
                    out = "\n".join(f"{r['id']} {r['status']} {r['title']}" for r in rows) or "No experiments."
                    self.log_line(out)
                else:
                    self.log_line("Research store unavailable")
                return

            if lowered.startswith("experiment_update "):
                raw = cmd.split(" ", 1)[1] if " " in cmd else ""
                parts = [s.strip() for s in raw.split("|", 2)]
                if len(parts) < 2:
                    self.log_line("experiment_update requires: experiment_update <id> | <status> | <notes>")
                    return
                try:
                    exp_id = int(parts[0])
                except Exception:
                    self.log_line("experiment_update requires numeric id")
                    return
                status = parts[1]
                notes = parts[2] if len(parts) > 2 else ""
                if hasattr(self, "research"):
                    self.research.update_experiment(exp_id, status, notes)
                    self.log_line("Experiment updated.")
                else:
                    self.log_line("Research store unavailable")
                return

            if lowered.startswith("incident "):
                raw = cmd.split(" ", 1)[1] if " " in cmd else ""
                if "|" not in raw:
                    self.log_line("incident requires: incident <severity> | <summary>")
                    return
                severity, summary = [s.strip() for s in raw.split("|", 1)]
                iid = self.memory.add_incident(severity, summary)
                self.log_line(f"Incident logged: {iid}")
                return

            if lowered == "incidents":
                rows = self.memory.list_incidents(10)
                out = "\n".join(
                    f"{r['id']} {r['severity']} {r['summary']}" for r in rows
                ) or "No incidents."
                self.log_line(out)
                return

            if lowered.startswith("eval_run "):
                raw = cmd.split(" ", 1)[1] if " " in cmd else ""
                if "|" not in raw:
                    self.log_line("eval_run requires: eval_run <name> | <notes>")
                    return
                name, notes = [s.strip() for s in raw.split("|", 1)]
                eid = self.memory.add_evaluation(name, notes)
                self.log_line(f"Eval logged: {eid}")
                return

            if lowered == "evals":
                rows = self.memory.list_evaluations(10)
                out = "\n".join(f"{r['id']} {r['name']}" for r in rows) or "No evals."
                self.log_line(out)
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

            if lowered.startswith("feedback"):
                raw = cmd.split(" ", 1)[1].strip() if " " in cmd else ""
                rating = 0
                notes = ""
                if "|" in raw:
                    left, notes = raw.split("|", 1)
                    raw = left.strip()
                    notes = notes.strip()
                try:
                    rating = int(raw) if raw else 0
                except Exception:
                    rating = 0
                self.memory.add_feedback(rating, notes)
                self.log_line("Feedback recorded.")
                return

            if lowered == "governance":
                self.log_line(self._governance_checklist())
                return

            if lowered == "readiness":
                self.log_line(self._readiness_report())
                return

            if lowered == "models":
                rows = self.memory.model_summary(10)
                if not rows:
                    self.log_line("No model runs yet.")
                    return
                lines = []
                for row in rows:
                    lines.append(
                        f"{row['model']} runs={row['runs']} avg_latency={row['avg_latency']:.2f}s "
                        f"tokens_in={row['tokens_in']} tokens_out={row['tokens_out']} cost=${row['cost']:.6f}"
                    )
                self.log_line("\n".join(lines))
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
            if self.path == "/api/models":
                body = json.dumps(app.memory.model_summary(20)).encode("utf-8")
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

