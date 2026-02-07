import os
import re
 

import threading

import tkinter as tk

from tkinter import ttk

from datetime import datetime
import socket

import json
import shutil

import time

from http import HTTPStatus

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import io
import base64
import queue
import uuid
import subprocess

import contextlib

import logging
import hashlib
import platform
import sys
import asyncio
from urllib.parse import urlparse, parse_qs
import shlex
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any



from config import get_settings

from engine import AgentEngine

from logger import setup_logging

from metrics import Metrics
from telemetry_langfuse import LangfuseClient
from telemetry_agentops import AgentOpsClient
from telemetry_otel import OTelTracer

from task_queue import TaskQueue

from tools import ToolRegistry, ToolContext, ToolNeedsConfirmation
try:
    from tools.registry import UnifiedToolRegistry
except Exception:
    import importlib.util as _importlib_util
    import sys as _sys
    _tools_registry_path = os.path.join(os.path.dirname(__file__), "tools", "registry.py")
    _spec = _importlib_util.spec_from_file_location("tools_registry", _tools_registry_path)
    if _spec and _spec.loader:
        _mod = _importlib_util.module_from_spec(_spec)
        _sys.modules["tools_registry"] = _mod
        _spec.loader.exec_module(_mod)
        UnifiedToolRegistry = _mod.UnifiedToolRegistry
    else:
        raise
from executor import files as exec_files
from executor.execute import execute_tool

from agents import PlannerAgent, RetrieverAgent, ExecutorAgent, VerifierAgent


from calibration import confidence_from_evidence

from deep_research import DeepResearch

from multimodal import ocr_pdf, capture_screenshot
from vla import LiveDriver
from ui_automation import snapshot_uia, write_snapshot, find_uia_first
from som_client import save as som_save
from browser_use_adapter import BrowserUseAdapter, WorkflowUseAdapter
from workflow_recorder import WorkflowRecorder
from audio_io import record_and_transcribe, speak_text
from cost import estimate_tokens
from cognitive import slow_mode, dot_ensemble
from workflows import run_workflow
from perception import collect_observation

from router import choose_model

from policy import requires_confirmation
from team import TeamOrchestrator, AgentRole, ManagerWorkerOrchestrator
from mcp_adapter import MCPAdapter
from lsp_tools import find_symbol_def, find_inherits
from privacy import redact_text
from core.logging_api import log_audit
from core.schemas import ToolCall, TaskEvent, RunHeartbeat
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
from safety import screen_text
from sandbox import run_python
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
from orchestrator.state import OrchestratorState, validate_transition
from core.schemas import (
    PlanSchema,
    PlanStepSchema,
    VerifySchema,
    ExecutionReport,
    StepReport,
    ToolResult,
    Budget,
)
from core.run_state import list_run_dirs, summarize_run


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


@dataclass
class PlanStep:
    step: int
    action: str
    target: str
    value: str = ""
    reason: str = ""
    command: str = ""


@dataclass
class TaskRun:
    run_id: str
    intent: Dict[str, str]
    plan_steps: List[PlanStep]
    plan_schema: object | None = None
    report: object | None = None
    approved: bool = False
    mode: str = "demo"
    status: str = "planned"
    created_at: str = ""
    command: str = ""
    run_dir: str = ""
    actions_path: str = ""
    events_path: str = ""
    screenshots_dir: str = ""
    extracted_path: str = ""
    trace_id: str = ""




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

    def __init__(self, root, settings, engine: AgentEngine):

        self.root = root

        self.root.title(APP_TITLE)

        self.root.geometry("900x600")



        self.settings = settings
        self.engine = engine
        self.memory = engine.memory
        self._apply_policy_pack()
        self.node_name = self.settings.node_name
        self.a2a_pause_path = os.path.join(self.settings.data_dir, "a2a_bridge_pause.json")

        self.metrics = engine.metrics
        self.langfuse = LangfuseClient()
        self.agentops = AgentOpsClient()
        self.otel = OTelTracer()
        self.task_queue = engine.task_queue



        self.playwright = None

        self.browser = None

        self.page = None

        self.log_buffer = []

        self.chat_history = []

        self.tools = ToolRegistry(self)
        self.ui_blocks: list = []

        self.rag = engine.rag
        self.graph = engine.graph
        self.research = engine.research
        self.jobs = engine.jobs
        self.a2a = engine.a2a
        self.a2a_net = engine.a2a_net
        self.a2a_net.on_message = self._on_a2a_message
        self.engine.start_a2a()
        self.mcp = MCPAdapter()
        self.slow_mode = False
        self.dot_mode = False
        self._memory_prune_stop = threading.Event()
        self._start_memory_prune_loop()
        self._a2a_async_enabled = os.getenv("AGENTIC_A2A_ASYNC", "false").lower() in ("1", "true", "yes", "on")
        if self._a2a_async_enabled:
            self._start_a2a_async_loop()
        self._dreaming_enabled = os.getenv("AGENTIC_DREAMING", "false").lower() in ("1", "true", "yes", "on")
        self._world_loop_enabled = os.getenv("AGENTIC_WORLD_LOOP", "false").lower() in ("1", "true", "yes", "on")
        self._cfo_enabled = os.getenv("AGENTIC_CFO", "false").lower() in ("1", "true", "yes", "on")
        self._vision_enabled = os.getenv("AGENTIC_VISION_LOOP", "false").lower() in ("1", "true", "yes", "on")
        self._vla_enabled = os.getenv("AGENTIC_VLA_ENABLED", "false").lower() in ("1", "true", "yes", "on")
        self._jarvis_enabled = os.getenv("AGENTIC_JARVIS", "false").lower() in ("1", "true", "yes", "on")
        self._schedule_enabled = bool(os.getenv("AGENTIC_SCHEDULE_JSON", ""))
        self._schedule_stop = threading.Event()
        if self._dreaming_enabled:
            self._start_dreaming_loop()
        if self._world_loop_enabled:
            self._start_world_loop()
        if self._cfo_enabled:
            self._start_cfo_loop()
        if self._vision_enabled:
            self._start_vision_loop()
        if self._jarvis_enabled:
            self._start_jarvis_loop()
        if self._schedule_enabled:
            self._start_schedule_loop()
        self._start_watchers()


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
        tool_prefixes.append("mcp_resources")
        tool_prefixes.append("mcp_prompts")
        tool_prefixes.append("mcp_tools")
        tool_prefixes.append("mcp_providers")
        tool_prefixes.append("lsp_find")
        tool_prefixes.append("lsp_inherits")
        tool_prefixes.append("vla")

        # Capabilities handshake (dynamic discovery)
        if os.getenv("AGENTIC_A2A_HANDSHAKE", "false").lower() in ("1", "true", "yes", "on"):
            try:
                self._send_capabilities()
            except Exception:
                pass
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
        tool_prefixes.append("workflow_record")
        tool_prefixes.append("workflow_run")
        tool_prefixes.append("browser_use")
        tool_prefixes.append("workflow_use")
        tool_prefixes.append("slow_mode")
        tool_prefixes.append("dot_mode")
        tool_prefixes.append("graph_query")
        tool_prefixes.append("perception")
        tool_prefixes.append("hybrid_rag")
        tool_prefixes.append("graph_add")
        tool_prefixes.append("graph_edge")
        tool_prefixes.append("sandbox_run")
        tool_prefixes.append("uia_snapshot")
        tool_prefixes.append("som_detect")
        tool_prefixes.append("fishbowl")
        tool_prefixes.append("step_approval")
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
        self.memory.purge_audit_logs(settings.audit_retention_seconds)
        self.memory.purge_debug_logs(settings.debug_retention_seconds)

        self.team = TeamOrchestrator(self._agent_chat)
        self.edge_mode = self.memory.get("edge_mode") or "auto"
        self.agent_profile = self.memory.get("agent_profile") or ""
        self.demo_mode = settings.demo_mode.lower() == "true"
        self.replay_mode = str(getattr(settings, "replay_mode", "false")).lower() == "true"
        self.advanced_mode = False
        self.step_approval_enabled = False
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.step_approval_event = threading.Event()
        self.waiting_for_step = False
        self.current_run = None
        self.pending_runs = {}

        self.workflow = WorkflowRecorder(self.settings.data_dir)
        self.browser_use = BrowserUseAdapter()
        self.workflow_use = WorkflowUseAdapter()

        self.vla_driver = LiveDriver(self, self.settings.data_dir)
        if self._vla_enabled:
            self.vla_driver.start()

        self._build_ui()
        self._load_last_run()

        self._load_memory()



    def _build_ui(self):

        top = ttk.Frame(self.root, padding=8)

        top.pack(fill=tk.BOTH, expand=True)

        self.mode_banner = ttk.Label(
            top,
            text=self._mode_banner_text(),
            foreground="#fff",
            background="#b04c2f" if self.demo_mode else "#2a6f3b",
            padding=6,
        )
        self.mode_banner.pack(fill=tk.X)

        self.input_var = tk.StringVar()
        input_row = ttk.Frame(top)
        input_row.pack(fill=tk.X, pady=6)

        ttk.Label(input_row, text="Task:").pack(side=tk.LEFT)
        entry = ttk.Entry(input_row, textvariable=self.input_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        entry.bind("<Return>", lambda _e: self.run_command())

        run_btn = ttk.Button(input_row, text="Plan", command=self.run_command)
        run_btn.pack(side=tk.LEFT, padx=2)

        self.approve_btn = ttk.Button(input_row, text="Approve & Run", command=self.approve_run, state=tk.DISABLED)
        self.approve_btn.pack(side=tk.LEFT, padx=2)

        edit_btn = ttk.Button(input_row, text="Edit Plan", command=self.edit_plan)
        edit_btn.pack(side=tk.LEFT, padx=2)

        cancel_btn = ttk.Button(input_row, text="Cancel", command=self.cancel_plan)
        cancel_btn.pack(side=tk.LEFT, padx=2)

        self.pause_btn = ttk.Button(input_row, text="Pause", command=self.toggle_pause)
        self.pause_btn.pack(side=tk.LEFT, padx=2)

        step_btn = ttk.Button(input_row, text="Approve Step", command=self.approve_step)
        step_btn.pack(side=tk.LEFT, padx=2)

        stop_btn = ttk.Button(input_row, text="Stop", command=self.stop_run)
        stop_btn.pack(side=tk.LEFT, padx=2)

        self.advanced_var = tk.BooleanVar(value=False)
        self.step_approval_var = tk.BooleanVar(value=False)
        adv_toggle = ttk.Checkbutton(
            input_row, text="Advanced Mode", variable=self.advanced_var, command=self.toggle_advanced_mode
        )
        adv_toggle.pack(side=tk.LEFT, padx=6)
        step_toggle = ttk.Checkbutton(
            input_row, text="Step Approval", variable=self.step_approval_var, command=self.toggle_step_approval
        )
        step_toggle.pack(side=tk.LEFT, padx=6)

        main_pane = ttk.PanedWindow(top, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, pady=6)

        left = ttk.Frame(main_pane)
        right = ttk.Frame(main_pane)
        main_pane.add(left, weight=3)
        main_pane.add(right, weight=2)

        self.left_notebook = ttk.Notebook(left)
        self.left_notebook.pack(fill=tk.BOTH, expand=True)

        console_tab = ttk.Frame(self.left_notebook)
        a2a_tab = ttk.Frame(self.left_notebook)
        terminal_tab = ttk.Frame(self.left_notebook)
        canvas_tab = ttk.Frame(self.left_notebook)
        ui_tab = ttk.Frame(self.left_notebook)
        self.left_notebook.add(console_tab, text="Console")
        self.left_notebook.add(a2a_tab, text="A2A Control")
        self.left_notebook.add(terminal_tab, text="Terminal")
        self.left_notebook.add(canvas_tab, text="Canvas")
        self.left_notebook.add(ui_tab, text="UI Blocks")

        self.log = tk.Text(console_tab, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True)
        self.log.insert(tk.END, "Ready. Type a command and press Enter.\n")
        self.log.configure(state=tk.DISABLED)

        self._build_a2a_tab(a2a_tab)
        self._build_terminal_tab(terminal_tab)
        self._build_canvas_tab(canvas_tab)
        self._build_ui_blocks_tab(ui_tab)

        ttk.Label(right, text="Plan (Intent → Plan → Proof)").pack(anchor="w")
        self.plan_text = tk.Text(right, height=10, wrap=tk.WORD)
        self.plan_text.pack(fill=tk.BOTH, expand=False, pady=4)
        self.plan_text.configure(state=tk.DISABLED)

        ttk.Label(right, text="Action Cards").pack(anchor="w", pady=(6, 0))
        cols = ("step", "action", "target", "risk", "reason", "status", "timestamp")
        self.action_tree = ttk.Treeview(right, columns=cols, show="headings", height=10)
        for col in cols:
            self.action_tree.heading(col, text=col)
            self.action_tree.column(col, width=120 if col != "reason" else 200, anchor="w")
        self.action_tree.pack(fill=tk.BOTH, expand=True)

        help_text = "Plan first, then approve to execute. Demo Mode blocks destructive actions."
        ttk.Label(top, text=help_text, foreground="#555").pack(fill=tk.X)

    def _build_a2a_tab(self, parent):
        status_row = ttk.Frame(parent)
        status_row.pack(fill=tk.X, pady=(4, 2))

        self.a2a_status_var = tk.StringVar(value="UNKNOWN")
        ttk.Label(status_row, text="Status:").pack(side=tk.LEFT)
        ttk.Label(status_row, textvariable=self.a2a_status_var).pack(side=tk.LEFT, padx=6)

        ttk.Label(status_row, text="Peer:").pack(side=tk.LEFT, padx=(12, 0))
        peers = list(self.a2a_net.peers.keys())
        if not peers:
            peers = ["desktop"]
        self.a2a_peer_var = tk.StringVar(value=peers[0])
        self.a2a_peer_combo = ttk.Combobox(status_row, textvariable=self.a2a_peer_var, values=peers, width=16)
        self.a2a_peer_combo.pack(side=tk.LEFT, padx=4)

        ttk.Label(status_row, text="Filter:").pack(side=tk.LEFT, padx=(12, 0))
        self.a2a_filter_var = tk.StringVar(value="all")
        self.a2a_filter_combo = ttk.Combobox(
            status_row,
            textvariable=self.a2a_filter_var,
            values=["all", "desktop", "laptop", "user"],
            width=10,
        )
        self.a2a_filter_combo.pack(side=tk.LEFT, padx=4)

        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=tk.X, pady=(2, 6))
        ttk.Button(btn_row, text="Start Conversation", command=self._a2a_start).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Stop Conversation", command=self._a2a_stop).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Pause", command=self._a2a_pause).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Resume AI↔AI", command=self._a2a_resume).pack(side=tk.LEFT, padx=2)

        self.a2a_text = tk.Text(parent, wrap=tk.WORD, height=20)
        self.a2a_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=4)
        self.a2a_text.configure(state=tk.DISABLED)

        input_row = ttk.Frame(parent)
        input_row.pack(fill=tk.X, pady=(4, 2))
        ttk.Label(input_row, text="Send:").pack(side=tk.LEFT)
        self.a2a_input_var = tk.StringVar()
        entry = ttk.Entry(input_row, textvariable=self.a2a_input_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        entry.bind("<Return>", lambda _e: self._a2a_send(join=False))
        ttk.Button(input_row, text="Send only", command=lambda: self._a2a_send(join=False)).pack(side=tk.LEFT, padx=2)
        ttk.Button(input_row, text="Send & Join", command=lambda: self._a2a_send(join=True)).pack(side=tk.LEFT, padx=2)

        self._update_a2a_status()
        self.root.after(1000, self._a2a_refresh)

    def _run_shell_async(self, cmd: str) -> None:
        if not self._shell_allowed(cmd):
            self.log_line("Shell command blocked by allowlist.")
            return
        def _worker():
            try:
                subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            except Exception:
                return

        threading.Thread(target=_worker, daemon=True).start()

    def _set_a2a_bridge_pause(self, paused: bool) -> None:
        os.makedirs(self.settings.data_dir, exist_ok=True)
        payload = {"paused": bool(paused), "updated": datetime.now().isoformat()}
        try:
            with open(self.a2a_pause_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
        except Exception:
            return
        self._update_a2a_status()

    def _is_a2a_paused(self) -> bool:
        try:
            with open(self.a2a_pause_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return bool(data.get("paused"))
        except Exception:
            return False

    def _update_a2a_status(self) -> None:
        self.a2a_status_var.set("PAUSED" if self._is_a2a_paused() else "LIVE")

    def _a2a_start(self) -> None:
        self._set_a2a_bridge_pause(False)
        self._run_shell_async('schtasks /Run /TN "AgenticA2ABridge"')
        self._run_shell_async('schtasks /Run /TN "AgenticA2ARelay"')

    def _a2a_stop(self) -> None:
        self._set_a2a_bridge_pause(True)
        self._run_shell_async('schtasks /End /TN "AgenticA2ABridge"')

    def _a2a_pause(self) -> None:
        self._set_a2a_bridge_pause(True)

    def _a2a_resume(self) -> None:
        self._set_a2a_bridge_pause(False)

    def _a2a_send(self, join: bool = False) -> None:
        message = (self.a2a_input_var.get() or "").strip()
        if not message:
            return
        peer = (self.a2a_peer_var.get() or "desktop").strip()
        sender = "user" if join else getattr(self, "node_name", "work")
        try:
            with self.otel.span("a2a_send", trace_id="", attributes={"peer": peer, "sender": sender}):
                self.a2a_net.send(peer, sender, "remote", message)
            self.log_line(f"A2A send to {peer}: {message}")
        except Exception as exc:
            self.log_line(f"A2A send failed: {exc}")
        if join:
            self._set_a2a_bridge_pause(True)
        self.a2a_input_var.set("")
        self._a2a_refresh()

    def _a2a_refresh(self) -> None:
        try:
            msgs = self.a2a.recent(200)
        except Exception:
            self.root.after(2000, self._a2a_refresh)
            return
        msgs = list(reversed(msgs))
        filt = (self.a2a_filter_var.get() or "all").strip()
        lines = []
        for m in msgs:
            sender = m.get("sender")
            if filt != "all" and sender != filt:
                continue
            ts = datetime.fromtimestamp(m.get("timestamp", time.time())).isoformat(timespec="seconds")
            lines.append(f"[{ts}] {sender} -> {m.get('receiver')}: {m.get('message')}")
        self.a2a_text.configure(state=tk.NORMAL)
        self.a2a_text.delete("1.0", tk.END)
        self.a2a_text.insert(tk.END, "\n".join(lines) + ("\n" if lines else ""))
        self.a2a_text.configure(state=tk.DISABLED)
        self._update_a2a_status()
        self.root.after(2000, self._a2a_refresh)

    def _build_terminal_tab(self, parent) -> None:
        self._terminal_process = None
        self._terminal_queue = queue.Queue()
        self._terminal_autorun_done = False

        status_row = ttk.Frame(parent)
        status_row.pack(fill=tk.X, pady=4)
        self.term_status_var = tk.StringVar(value="idle")
        ttk.Label(status_row, text="Status:").pack(side=tk.LEFT, padx=2)
        ttk.Label(status_row, textvariable=self.term_status_var).pack(side=tk.LEFT, padx=4)

        self.term_text = tk.Text(parent, wrap=tk.WORD, height=18)
        self.term_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=4)
        self.term_text.configure(state=tk.DISABLED)

        input_row = ttk.Frame(parent)
        input_row.pack(fill=tk.X, pady=4)
        self.term_input_var = tk.StringVar()
        entry = ttk.Entry(input_row, textvariable=self.term_input_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        entry.bind("<Return>", lambda _e: self._terminal_run())
        ttk.Button(input_row, text="Run", command=self._terminal_run).pack(side=tk.LEFT, padx=2)
        ttk.Button(input_row, text="Kill", command=self._terminal_kill).pack(side=tk.LEFT, padx=2)
        ttk.Button(input_row, text="Clear", command=self._terminal_clear).pack(side=tk.LEFT, padx=2)

        hint = ttk.Label(parent, text="Example: codex danger-full-access", foreground="#666")
        hint.pack(anchor=tk.W, padx=4, pady=2)

        self.root.after(200, self._terminal_pump)

    def _build_canvas_tab(self, parent) -> None:
        self.canvas_text = tk.Text(parent, wrap=tk.WORD, height=18)
        self.canvas_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=4)
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=tk.X, pady=4)
        ttk.Button(btn_row, text="Load", command=self._canvas_load).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Save", command=self._canvas_save).pack(side=tk.LEFT, padx=4)

    def _canvas_path(self) -> str:
        run_id = self.current_run.run_id if getattr(self, "current_run", None) else "default"
        base = os.path.join(self.settings.data_dir, "runs", run_id)
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "canvas.md")

    def _canvas_load(self) -> None:
        path = self._canvas_path()
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except Exception:
            text = ""
        self.canvas_text.delete("1.0", tk.END)
        self.canvas_text.insert(tk.END, text)

    def _canvas_save(self) -> None:
        path = self._canvas_path()
        text = self.canvas_text.get("1.0", tk.END)
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            self.log_line(f"Canvas saved: {path}")
        except Exception as exc:
            self.log_line(f"Canvas save failed: {exc}")

    def _build_ui_blocks_tab(self, parent) -> None:
        self.ui_list = tk.Listbox(parent)
        self.ui_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.ui_detail = ttk.Frame(parent)
        self.ui_detail.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.ui_list.bind("<<ListboxSelect>>", lambda _e: self._render_ui_block_detail())

    def _render_ui_blocks_tab(self) -> None:
        if not hasattr(self, "ui_list"):
            return
        self.ui_list.delete(0, tk.END)
        for idx, block in enumerate(self.ui_blocks):
            label = block.get("type", "ui")
            self.ui_list.insert(tk.END, f"{idx}: {label}")

    def _render_ui_block_detail(self) -> None:
        for widget in self.ui_detail.winfo_children():
            widget.destroy()
        sel = self.ui_list.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self.ui_blocks):
            return
        block = self.ui_blocks[idx]
        ttk.Label(self.ui_detail, text=f"Type: {block.get('type')}").pack(anchor="w")
        if block.get("type") == "form":
            fields = block.get("fields") or []
            entries = {}
            for f in fields:
                key = f.get("key") or f.get("name") or ""
                if not key:
                    continue
                ttk.Label(self.ui_detail, text=key).pack(anchor="w")
                var = tk.StringVar()
                entry = ttk.Entry(self.ui_detail, textvariable=var)
                entry.pack(fill=tk.X, padx=2, pady=2)
                entries[key] = var
            def _submit():
                data = {k: v.get() for k, v in entries.items()}
                self._orchestrate("submit_form " + json.dumps(data))
            ttk.Button(self.ui_detail, text="Submit", command=_submit).pack(pady=4)
        if block.get("type") == "approval":
            ttk.Button(self.ui_detail, text="Approve Once", command=lambda: self._orchestrate("approve_once")).pack(pady=2)
            ttk.Button(self.ui_detail, text="Always Allow", command=lambda: self._orchestrate("approve_always")).pack(pady=2)
            ttk.Button(self.ui_detail, text="Never Allow", command=lambda: self._orchestrate("approve_never")).pack(pady=2)
        self._terminal_maybe_autorun()

    def _terminal_clear(self) -> None:
        self.term_text.configure(state=tk.NORMAL)
        self.term_text.delete("1.0", tk.END)
        self.term_text.configure(state=tk.DISABLED)

    def _terminal_kill(self) -> None:
        proc = getattr(self, "_terminal_process", None)
        if proc:
            try:
                proc.terminate()
            except Exception:
                pass
        self._terminal_process = None
        self.term_status_var.set("idle")

    def _terminal_run(self) -> None:
        cmd = (self.term_input_var.get() or "").strip()
        if not cmd:
            return
        if not self._shell_allowed(cmd):
            self._terminal_queue.put("[terminal] blocked by allowlist.\n")
            return
        self.term_input_var.set("")
        if getattr(self, "_terminal_process", None):
            self._terminal_queue.put("\n[terminal] process already running. Kill it first.\n")
            return
        self.term_status_var.set("running")

        def _worker():
            try:
                proc = subprocess.Popen(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                self._terminal_process = proc
                if proc.stdout:
                    for line in proc.stdout:
                        self._terminal_queue.put(line)
                proc.wait()
            except Exception as exc:
                self._terminal_queue.put(f"[terminal error] {exc}\n")
            finally:
                self._terminal_process = None
                self.term_status_var.set("idle")

        threading.Thread(target=_worker, daemon=True).start()

    def _shell_allowed(self, cmd: str) -> bool:
        allow = os.getenv("AGENTIC_ALLOWED_SHELL", "")
        if not allow:
            return True
        allowed = [a.strip().lower() for a in allow.split(",") if a.strip()]
        lowered = (cmd or "").strip().lower()
        return any(lowered.startswith(a) for a in allowed)

    def _terminal_pump(self) -> None:
        try:
            while True:
                line = self._terminal_queue.get_nowait()
                self.term_text.configure(state=tk.NORMAL)
                self.term_text.insert(tk.END, line)
                self.term_text.see(tk.END)
                self.term_text.configure(state=tk.DISABLED)
        except Exception:
            pass
        self.root.after(200, self._terminal_pump)

    def _terminal_maybe_autorun(self) -> None:
        if self._terminal_autorun_done:
            return
        if os.getenv("AGENTIC_TERMINAL_AUTORUN", "false").lower() not in ("1", "true", "yes", "on"):
            return
        cmd = os.getenv("AGENTIC_TERMINAL_AUTORUN_CMD", "codex danger-full-access")
        if not cmd:
            return
        self._terminal_autorun_done = True
        self.term_input_var.set(cmd)
        self._terminal_run()

    def _debate_step(self, step: str) -> bool:
        try:
            pro = self._agent_chat(f"Argue FOR executing this step safely: {step}")
            con = self._agent_chat(f"Argue AGAINST executing this step: {step}")
            verdict = self._agent_chat(
                f"Judge this action. If safe, respond with 'SAFE' and why. If unsafe, respond with 'UNSAFE' and why.\n"
                f"Step: {step}\nProponent: {pro}\nOpponent: {con}"
            )
            return "safe" in (verdict or "").lower()
        except Exception:
            return False

    def _send_capabilities(self) -> None:
        tools = sorted(list(self.tools.tools.keys()))
        payload = {
            "type": "capabilities",
            "tools": tools,
            "node": getattr(self, "node_name", "unknown"),
            "version": APP_VERSION,
        }
        for peer in self.a2a_net.peers:
            try:
                self.a2a_net.send(peer, getattr(self, "node_name", "work"), "remote", payload)
            except Exception:
                continue

    def _broadcast_memory_sync(self, item: dict) -> None:
        payload = {
            "type": "memory_sync",
            "item": item,
            "node": getattr(self, "node_name", "unknown"),
        }
        for peer in self.a2a_net.peers:
            try:
                self.a2a_net.send(peer, getattr(self, "node_name", "work"), "remote", payload)
            except Exception:
                continue



    def _maybe_redact(self, text: str) -> str:
        if getattr(self, "redact_logs", False):
            return redact_text(text)
        return text

    def _log_event(self, event_type: str, payload, extra: dict | None = None) -> None:
        data = {
            "payload": payload,
            "purpose": getattr(self, "purpose", "") or "",
            "autonomy": getattr(self, "autonomy_level", ""),
        }
        data["actor"] = f"agent:{getattr(self, 'node_name', 'agent')}"
        data["requester"] = f"user:{os.getenv('AGENTIC_USER_ID', 'default')}"
        if extra:
            data.update(extra)
        run_id = ""
        trace_id = ""
        if getattr(self, "current_run", None):
            run_id = self.current_run.run_id
            trace_id = getattr(self.current_run, "trace_id", "")
        event = TaskEvent(
            event_type=event_type,
            run_id=run_id,
            step_id=(extra or {}).get("step_id") if extra else None,
            payload=data,
            timestamp=time.time(),
            trace_id=(extra or {}).get("trace_id") or trace_id,
        )
        log_audit(self.memory, "task_event", event.__dict__, redact=getattr(self, "redact_logs", False))
        try:
            if getattr(self, "current_run", None) and getattr(self.current_run, "events_path", ""):
                with open(self.current_run.events_path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(event.__dict__) + "\n")
        except Exception:
            pass

    def emit_ui_block(self, block: dict) -> None:
        self._log_event("ui_block", {"ui": block})

    def emit_ui_patch(self, patch: dict) -> None:
        self._log_event("ui_patch", {"ui": patch})

    def emit_trace_update(self, message: str, level: str = "info") -> None:
        self._log_event("trace_update", {"message": message, "level": level})
        try:
            trace_id = (extra or {}).get("trace_id") or trace_id
            if trace_id:
                self.langfuse.log_event(trace_id, event_type, data)
                self.agentops.log_event(trace_id, event_type, data)
                self.otel.log_event(trace_id, event_type, data)
        except Exception:
            pass
        if event_type == "ui_block" and isinstance(payload, dict):
            try:
                block = payload.get("ui") or {}
                self.ui_blocks.append(block)
                self._render_ui_blocks_tab()
            except Exception:
                pass

    def log_line(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        safe = self._maybe_redact(message)
        line = f"[{ts}] {safe}"
        # Allow logging before UI widgets are initialized.
        if not hasattr(self, "log"):
            self.log_buffer.append(line)
            if len(self.log_buffer) > 500:
                self.log_buffer = self.log_buffer[-500:]
            return
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, f"{line}\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)
        self.log_buffer.append(line)
        if len(self.log_buffer) > 500:
            self.log_buffer = self.log_buffer[-500:]

    def _mode_banner_text(self) -> str:
        return "DEMO MODE (SAFE ACTIONS ONLY)" if self.demo_mode else "ADVANCED MODE"

    def _update_mode_banner(self) -> None:
        if not hasattr(self, "mode_banner"):
            return
        self.mode_banner.configure(
            text=self._mode_banner_text(),
            background="#b04c2f" if self.demo_mode else "#2a6f3b",
        )

    def toggle_advanced_mode(self) -> None:
        self.advanced_mode = bool(self.advanced_var.get())
        self.demo_mode = not self.advanced_mode
        self._update_mode_banner()
        self.log_line("Advanced mode enabled." if self.advanced_mode else "Demo mode enabled.")

    def toggle_step_approval(self) -> None:
        self.step_approval_enabled = bool(self.step_approval_var.get())
        msg = "Step approvals enabled." if self.step_approval_enabled else "Step approvals disabled."
        self.log_line(msg)

    def _start_a2a_async_loop(self) -> None:
        self._a2a_async_queue = asyncio.Queue()

        async def _worker():
            while True:
                sender, receiver, message = await self._a2a_async_queue.get()
                try:
                    await asyncio.to_thread(self._on_a2a_message_impl, sender, receiver, message)
                except Exception:
                    pass

        def _run():
            try:
                asyncio.run(_worker())
            except Exception:
                pass

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def _start_dreaming_loop(self) -> None:
        interval_hours = int(os.getenv("AGENTIC_DREAMING_HOURS", "24"))
        runs_dir = os.path.join(self.settings.data_dir, "runs")

        def _dream():
            try:
                wisdom_lines = []
                if os.path.isdir(runs_dir):
                    for name in sorted(os.listdir(runs_dir))[-20:]:
                        summary_path = os.path.join(runs_dir, name, "summary.md")
                        if not os.path.exists(summary_path):
                            continue
                        with open(summary_path, "r", encoding="utf-8") as handle:
                            text = handle.read().strip()
                        if text:
                            wisdom_lines.append(text.splitlines()[-1][:200])
                if wisdom_lines:
                    wisdom = " | ".join(wisdom_lines[-10:])
                    self.memory.add_memory(
                        kind="wisdom",
                        content=wisdom,
                        tags=["dreaming"],
                        ttl_seconds=30 * 24 * 3600,
                        scope="shared",
                    )
                # prune old run folders (keep last 50)
                if os.path.isdir(runs_dir):
                    runs = sorted(os.listdir(runs_dir))
                    for old in runs[:-50]:
                        try:
                            old_path = os.path.join(runs_dir, old)
                            if os.path.isdir(old_path):
                                for root, dirs, files in os.walk(old_path, topdown=False):
                                    for f in files:
                                        os.remove(os.path.join(root, f))
                                    for d in dirs:
                                        os.rmdir(os.path.join(root, d))
                                os.rmdir(old_path)
                        except Exception:
                            pass
            except Exception:
                pass

        def _loop():
            while True:
                _dream()
                time.sleep(max(1, interval_hours) * 3600)

        threading.Thread(target=_loop, daemon=True).start()

    def _start_world_loop(self) -> None:
        interval = int(os.getenv("AGENTIC_WORLD_LOOP_INTERVAL", "60"))

        def _loop():
            while True:
                try:
                    desires = self.memory.list_bdi("desire", limit=20)
                    beliefs = self.memory.list_bdi("belief", limit=20)
                    belief_text = " ".join([b.get("text", "") for b in beliefs])
                    for d in desires:
                        text = d.get("text", "")
                        lowered = text.lower()
                        if "clean" in lowered and ("temp" in belief_text or "tmp" in belief_text):
                            run = self._create_task_run("Clean temp files in workspace.")
                            self.log_line("World loop queued: Clean temp files.")
                            self.pending_runs[run.run_id] = run
                except Exception:
                    pass
                time.sleep(interval)

        threading.Thread(target=_loop, daemon=True).start()

    def _start_cfo_loop(self) -> None:
        max_calls = int(os.getenv("AGENTIC_CFO_MAX_TOOL_CALLS", "200"))
        max_tokens = int(os.getenv("AGENTIC_CFO_MAX_TOKENS", "200000"))

        def _loop():
            while True:
                try:
                    snap = self.metrics.snapshot()
                    counters = snap.get("counters", {})
                    calls = sum(v for k, v in counters.items() if k.startswith("tool.") and k.endswith(".calls"))
                    tokens_in = counters.get("tokens_in", 0)
                    tokens_out = counters.get("tokens_out", 0)
                    if calls > max_calls or (tokens_in + tokens_out) > max_tokens:
                        self.log_line("CFO: budget exceeded, pausing auto-reply and switching to offline.")
                        self._set_a2a_bridge_pause(True)
                        self.edge_mode = "offline"
                except Exception:
                    pass
                time.sleep(30)

        threading.Thread(target=_loop, daemon=True).start()

    def _start_vision_loop(self) -> None:
        interval = float(os.getenv("AGENTIC_VISION_FPS", "1.0"))

        def _loop():
            try:
                import pytesseract  # type: ignore
                import pyautogui  # type: ignore
            except Exception:
                return
            while True:
                try:
                    img = pyautogui.screenshot()
                    text = pytesseract.image_to_string(img)
                    lowered = (text or "").lower()
                    if "traceback" in lowered or "error" in lowered:
                        self.log_line("Vision: detected error on screen. Want me to help?")
                except Exception:
                    pass
                time.sleep(max(0.2, 1.0 / max(0.1, interval)))

        threading.Thread(target=_loop, daemon=True).start()

    def _start_jarvis_loop(self) -> None:
        interval = int(os.getenv("AGENTIC_JARVIS_INTERVAL", "10"))
        model = os.getenv("AGENTIC_JARVIS_MODEL", "base")

        def _loop():
            while True:
                try:
                    text = record_and_transcribe(seconds=5, model_name=model)
                    if text:
                        reply = self._agent_chat(text) or ""
                        if reply:
                            speak_text(reply)
                except Exception:
                    pass
                time.sleep(interval)

        threading.Thread(target=_loop, daemon=True).start()

    def _load_schedule_entries(self) -> List[Dict[str, Any]]:
        raw = os.getenv("AGENTIC_SCHEDULE_JSON", "").strip()
        if not raw:
            return []
        try:
            if os.path.exists(raw):
                with open(raw, "r", encoding="utf-8") as handle:
                    raw = handle.read()
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _start_schedule_loop(self) -> None:
        entries = self._load_schedule_entries()
        if not entries:
            return
        schedule = []
        now = time.time()
        for item in entries:
            try:
                command = (item.get("command") or "").strip()
                every = float(item.get("every_seconds") or 0)
                if not command or every <= 0:
                    continue
                schedule.append({"command": command, "every": every, "next": now + every})
            except Exception:
                continue
        if not schedule:
            return

        def _loop():
            while not self._schedule_stop.is_set():
                now_ts = time.time()
                for entry in schedule:
                    if now_ts >= entry["next"]:
                        try:
                            run = self._create_task_run(entry["command"])
                            run.approved = True
                            self.current_run = run
                            self.task_queue.enqueue(lambda r=run: self._run_task_run(r))
                            entry["next"] = now_ts + entry["every"]
                        except Exception:
                            entry["next"] = now_ts + entry["every"]
                time.sleep(1.0)

        threading.Thread(target=_loop, daemon=True).start()

    def stop_run(self) -> None:
        self.stop_event.set()
        self.pause_event.clear()
        self.step_approval_event.set()
        self._shutdown_browser()
        if self.current_run:
            try:
                self._set_run_status(self.current_run, OrchestratorState.STOPPED.value)
            except Exception:
                pass
        self.log_line("STOP requested. Halting after current step.")

    def toggle_pause(self) -> None:
        if self.pause_event.is_set():
            self.pause_event.clear()
            if hasattr(self, "pause_btn"):
                self.pause_btn.configure(text="Pause")
            if self.current_run and self.current_run.status == OrchestratorState.PAUSED.value:
                try:
                    self._set_run_status(self.current_run, OrchestratorState.RUNNING.value)
                except Exception:
                    pass
            self.log_line("Resumed.")
        else:
            self.pause_event.set()
            if hasattr(self, "pause_btn"):
                self.pause_btn.configure(text="Resume")
            if self.current_run and self.current_run.status == OrchestratorState.RUNNING.value:
                try:
                    self._set_run_status(self.current_run, OrchestratorState.PAUSED.value)
                except Exception:
                    pass
            self.log_line("Pause requested. Will pause after current step.")

    def approve_step(self) -> None:
        self.step_approval_event.set()
        self.waiting_for_step = False
        self.log_line("Step approved.")

    def _set_plan_text(self, text: str) -> None:
        if not hasattr(self, "plan_text"):
            return
        self.plan_text.configure(state=tk.NORMAL)
        self.plan_text.delete("1.0", tk.END)
        self.plan_text.insert(tk.END, text)
        self.plan_text.configure(state=tk.DISABLED)

    def _reset_action_cards(self, plan_steps: List[PlanStep]) -> None:
        if not hasattr(self, "action_tree"):
            return
        for item in self.action_tree.get_children():
            self.action_tree.delete(item)
        self._action_items = {}
        risk_map = {}
        if self.current_run and getattr(self.current_run, "plan_schema", None):
            try:
                for s in self.current_run.plan_schema.steps:
                    risk_map[int(s.step_id)] = s.risk
            except Exception:
                risk_map = {}
        for step in plan_steps:
            risk = risk_map.get(step.step, "safe")
            item_id = self.action_tree.insert(
                "",
                tk.END,
                values=(step.step, step.action, step.target, risk, step.reason, "pending", ""),
            )
            self._action_items[step.step] = item_id

    def _set_action_status(self, step_id: int, status: str, timestamp: str) -> None:
        item_id = getattr(self, "_action_items", {}).get(step_id)
        if not item_id:
            return
        values = list(self.action_tree.item(item_id, "values"))
        values[4] = status
        values[5] = timestamp
        self.action_tree.item(item_id, values=values)

    def _append_extracted(self, text: str) -> None:
        if not self.current_run or not self.current_run.extracted_path:
            return
        with open(self.current_run.extracted_path, "a", encoding="utf-8") as handle:
            handle.write(text.strip() + "\n\n")

    def _update_a2a_thread_summary(self, sender: str, receiver: str, message: str) -> None:
        path = os.path.join(self.settings.data_dir, "a2a_thread_summaries.json")
        key = f"{sender}->{receiver}"
        now = datetime.now().isoformat()
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            data = {}
        entry = data.get(key, {"summary": "", "messages": [], "count_since_memory": 0})
        entry["messages"].append({"ts": now, "sender": sender, "receiver": receiver, "message": message})
        if len(entry["messages"]) > 10:
            entry["messages"] = entry["messages"][-10:]
        snippet = f"{sender}: {message}".strip()
        summary = entry.get("summary", "")
        summary = f"{summary} | {snippet}" if summary else snippet
        if len(summary) > 1000:
            summary = "…" + summary[-1000:]
        entry["summary"] = summary
        entry["count_since_memory"] = int(entry.get("count_since_memory", 0)) + 1
        data[key] = entry
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
        except Exception:
            return
        if entry["count_since_memory"] >= 5:
            try:
                self.memory.add_memory(
                    kind="a2a_thread_summary",
                    content=f"{key}: {summary}",
                    tags=[sender, receiver, "a2a_summary"],
                    ttl_seconds=7 * 24 * 3600,
                    scope="shared",
                )
                try:
                    self._broadcast_memory_sync({"kind": "a2a_thread_summary", "content": f"{key}: {summary}"})
                except Exception:
                    pass
                entry["count_since_memory"] = 0
                data[key] = entry
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(data, handle)
            except Exception:
                return

    def _on_a2a_message(self, sender: str, receiver: str, message: str) -> None:
        if getattr(self, "_a2a_async_enabled", False):
            try:
                if not hasattr(self, "_a2a_async_queue"):
                    return
                self._a2a_async_queue.put_nowait((sender, receiver, message))
                return
            except Exception:
                pass
        self._on_a2a_message_impl(sender, receiver, message)

    def _on_a2a_message_impl(self, sender: str, receiver: str, message: str) -> None:
        trace_id = ""
        try:
            raw = (message or "").strip()
            if raw.startswith("{") and raw.endswith("}"):
                payload = json.loads(raw)
                trace_id = payload.get("trace_id") or ""
        except Exception:
            trace_id = ""
        try:
            self.otel.log_event(trace_id, "a2a_receive", {"sender": sender, "receiver": receiver})
        except Exception:
            pass
        # Ensure summary file exists for downstream tooling even if other hooks fail.
        try:
            path = os.path.join(self.settings.data_dir, "a2a_thread_summaries.json")
            if not os.path.exists(path):
                key = f"{sender}->{receiver}"
                data = {key: {"summary": f"{sender}: {message}", "messages": [], "count_since_memory": 0}}
                os.makedirs(self.settings.data_dir, exist_ok=True)
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(data, handle)
        except Exception:
            pass
        # Persist inbound A2A to memory for self-improvement and recall
        try:
            content = f"{sender} -> {receiver}: {message}"
            self.memory.add_memory(
                kind="a2a",
                content=content,
                tags=[sender, receiver, "a2a"],
                scope="shared",
            )
        except Exception:
            pass
        try:
            self._update_a2a_thread_summary(sender, receiver, message)
        except Exception:
            pass
        if sender == getattr(self, "node_name", "work"):
            return
        if self._is_a2a_paused():
            return
        if str(self.settings.a2a_auto_reply).lower() not in ("1", "true", "yes", "on"):
            return

        mode = (getattr(self.settings, "a2a_agent_mode", "plan") or "plan").lower()
        if mode in ("off", "disabled", "false"):
            return
        if sender not in self.a2a_net.peers:
            return

        def _worker():
            try:
                payload = None
                raw = (message or "").strip()
                if raw.startswith("{") and raw.endswith("}"):
                    try:
                        payload = json.loads(raw)
                    except Exception:
                        payload = None

                msg_type = None
                msg_text = raw
                trace_id = None
                thread_id = None
                message_id = None
                if payload:
                    msg_type = (payload.get("type") or payload.get("performative") or "").lower()
                    msg_text = payload.get("text") or payload.get("task") or payload.get("content") or payload.get("message") or raw
                    trace_id = payload.get("trace_id")
                    thread_id = payload.get("thread_id")
                    message_id = payload.get("message_id")
                    if msg_type == "memory_sync":
                        try:
                            item = payload.get("item") or {}
                            kind = item.get("kind") or "memory_sync"
                            content = item.get("content") or json.dumps(item)
                            self.memory.add_memory(
                                kind=kind,
                                content=content,
                                tags=["memory_sync", sender],
                                scope="shared",
                            )
                            self.log_line(f"Memory sync received from {sender}.")
                        except Exception:
                            pass
                        return
                    if msg_type == "capabilities":
                        try:
                            tools = payload.get("tools") or []
                            node = payload.get("node") or sender
                            content = f"{node} capabilities: {', '.join(tools)}"
                            self.memory.add_memory(
                                kind="capabilities",
                                content=content,
                                tags=[node, "capabilities"],
                                scope="shared",
                            )
                            self.log_line(f"A2A capabilities received from {node}.")
                        except Exception:
                            pass
                        return

                # Simple prefix overrides
                lowered = msg_text.lower().strip()
                if lowered.startswith("plan:") or lowered.startswith("task:"):
                    msg_type = "plan"
                    msg_text = msg_text.split(":", 1)[1].strip()
                if lowered.startswith("execute:"):
                    msg_type = "execute"
                    msg_text = msg_text.split(":", 1)[1].strip()

                reply = ""
                if msg_type in ("chat", "") and mode in ("chat", "auto"):
                    reply = self._agent_chat(msg_text) or ""
                elif msg_type in ("plan", "task") or mode in ("plan", "auto"):
                    run = self._create_task_run(msg_text)
                    reply = self._format_plan(run.intent, run.plan_steps)
                elif msg_type == "execute":
                    if str(getattr(self.settings, "a2a_execute_enabled", "false")).lower() in (
                        "1",
                        "true",
                        "yes",
                        "on",
                    ):
                        run = self._create_task_run(msg_text)
                        reply = self._format_plan(run.intent, run.plan_steps)
                        reply = "EXECUTION DISABLED BY DEFAULT. Plan prepared:\n" + reply
                    else:
                        reply = "Execution disabled. Send `plan:` or `task:` to get a plan."
                else:
                    # Default lightweight ping response
                    host = socket.gethostname()
                    now = datetime.now().isoformat()
                    reply = f"AUTO_REPLY: hostname={host} time={now}"

                if reply:
                    reply_payload = {
                        "type": "reply",
                        "text": reply,
                        "trace_id": trace_id,
                        "thread_id": thread_id or message_id,
                        "reply_to": message_id,
                    }
                    try:
                        self.otel.log_event(trace_id or "", "a2a_send", {"peer": sender, "sender": getattr(self, "node_name", "work")})
                    except Exception:
                        pass
                    self.a2a_net.send(sender, getattr(self, "node_name", "work"), "remote", reply_payload)
                    self.log_line(f"A2A auto-reply sent to {sender}.")
            except Exception as exc:
                self.log_line(f"A2A auto-reply failed: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def _record_action(self, step: PlanStep, status: str, error: str = "") -> None:
        if not self.current_run or not self.current_run.actions_path:
            return
        payload = {
            "step": step.step,
            "action": step.action,
            "target": step.target,
            "value": step.value,
            "reason": step.reason,
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error": error,
        }
        with open(self.current_run.actions_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

    def _shutdown_browser(self) -> None:
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass

    def _capture_step_screenshot(self, step: PlanStep) -> None:
        if not self.current_run or not self.current_run.screenshots_dir:
            return
        if not self.page:
            return
        safe_action = step.action.replace(" ", "_")
        stamp = datetime.utcnow().strftime("%H%M%S")
        target = os.path.join(self.current_run.screenshots_dir, f"step-{step.step}-{safe_action}-{stamp}.png")
        try:
            self.page.screenshot(path=target, full_page=True)
        except Exception:
            pass

    def _build_intent(self, cmd: str) -> Dict[str, str]:
        return {"goal": cmd, "source": "user"}

    def _normalize_step(self, idx: int, step: str) -> PlanStep:
        lowered = step.strip().lower()
        action = "agent"
        target = step.strip()
        value = ""
        reason = "Derived from user intent."
        command = step.strip()

        if lowered.startswith("browse "):
            action = "navigate"
            target = step[7:].strip()
            reason = "Open the target URL."
        elif lowered.startswith("search "):
            action = "search"
            target = step[7:].strip()
            reason = "Query the search engine."
        elif lowered.startswith("click "):
            action = "click"
            target = step[6:].strip()
            reason = "Activate the target UI element."
        elif lowered.startswith("type "):
            action = "type"
            parts = step[5:].split("|", 1)
            target = parts[0].strip()
            value = parts[1].strip() if len(parts) > 1 else ""
            reason = "Enter text into the target field."
        elif lowered.startswith("press "):
            action = "press"
            target = step[6:].strip()
            reason = "Send a key press."
        elif lowered.startswith("screenshot "):
            action = "screenshot"
            target = step[11:].strip()
            reason = "Capture a screenshot for proof."
        elif lowered.startswith("open "):
            action = "open"
            target = step[5:].strip()
            reason = "Open a local file."
        elif lowered.startswith(("move ", "copy ", "delete ", "mkdir ")):
            action = "file"
            target = step.split(" ", 1)[1].strip() if " " in step else ""
            reason = "Perform a file operation."
        elif lowered.startswith(("rag ", "hybrid_rag ", "ocr ", "deep_research ", "lit_review ")):
            action = "extract"
            target = step.split(" ", 1)[1].strip() if " " in step else ""
            reason = "Retrieve or extract information."
        elif lowered.startswith(("workflow ", "graph_add ", "graph_edge ", "graph_query ")):
            action = "graph"
            target = step.split(" ", 1)[1].strip() if " " in step else ""
            reason = "Update or query structured data."
        elif lowered.startswith("sandbox_run "):
            action = "sandbox"
            target = "python"
            value = step[len("sandbox_run "):].strip()
            reason = "Execute isolated code."

        return PlanStep(step=idx, action=action, target=target, value=value, reason=reason, command=command)

    def _build_plan(self, cmd: str) -> List[PlanStep]:
        # Prefer recipes if available
        try:
            hits = self.memory.search_memory(cmd, limit=1)
            if hits:
                top = hits[0]
                if top.get("kind") == "recipe":
                    payload = json.loads(top.get("content") or "{}")
                    steps_raw = payload.get("steps") or []
                    steps: List[PlanStep] = []
                    for idx, s in enumerate(steps_raw, 1):
                        steps.append(
                            PlanStep(
                                step=idx,
                                action=s.get("action", "agent"),
                                target=s.get("target", ""),
                                value=s.get("value", ""),
                                reason=s.get("reason", ""),
                                command=s.get("command", s.get("target", "")),
                            )
                        )
                    if steps:
                        return steps
        except Exception:
            pass
        plan = self.planner.plan(cmd)
        if not plan:
            plan = [cmd]
        steps: List[PlanStep] = []
        for idx, step in enumerate(plan, 1):
            steps.append(self._normalize_step(idx, step))
        return steps

    def _format_plan(self, intent: Dict[str, str], steps: List[PlanStep]) -> str:
        json_payload = {
            "intent": intent,
            "plan_steps": [
                {
                    "step": s.step,
                    "action": s.action,
                    "target": s.target,
                    "value": s.value,
                    "reason": s.reason,
                }
                for s in steps
            ],
        }
        bullets = "\n".join([f"{s.step}. {s.action} → {s.target} ({s.reason})" for s in steps])
        return "PLAN (JSON)\n" + json.dumps(json_payload, indent=2) + "\n\nPLAN (BULLETS)\n" + bullets

    def _detect_ambiguity(self, cmd: str) -> bool:
        text = (cmd or "").strip().lower()
        if len(text) < 6:
            return True
        vague = ("do it", "do that", "fix it", "handle it", "start", "go", "run", "update", "help")
        if any(text == v or text.endswith(f" {v}") for v in vague):
            return True
        pronouns = ("this", "that", "it", "those", "these")
        if any(p in text.split() for p in pronouns) and len(text.split()) < 4:
            return True
        return False

    def _create_task_run(self, cmd: str) -> TaskRun:
        run_id = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
        trace_id = str(uuid.uuid4())
        intent = self._build_intent(cmd)
        steps = self._build_plan(cmd)
        plan_schema = None
        needs_input = self._detect_ambiguity(cmd)
        try:
            if os.getenv("AGENTIC_LLM_PLANNER", "true").lower() in ("1", "true", "yes", "on"):
                plan_schema = self._plan_with_llm(cmd)
                if plan_schema:
                    steps = self._plan_schema_to_steps(plan_schema)
            if plan_schema is None:
                schema_steps = [self._step_to_schema(i + 1, s.command or f"{s.action} {s.target}".strip()) for i, s in enumerate(steps)]
                plan_schema = PlanSchema(
                    run_id=run_id,
                    trace_id=trace_id,
                    goal=cmd,
                    success_criteria=["No errors and user intent satisfied"],
                    steps=schema_steps,
                    constraints={"demo_mode": self.demo_mode},
                    budget=Budget(
                        max_steps=getattr(self.settings, "max_plan_steps", 20) or 20,
                        max_tool_calls=int(getattr(self.settings, "max_tool_calls_per_task", 50) or 50),
                        max_seconds=900,
                    ),
                    created_at=time.time(),
                    model=getattr(self.settings, "openai_model", ""),
                    needs_user_input=needs_input,
                    questions=(
                        [
                            {
                                "id": "clarify",
                                "question": "Your request is ambiguous. What exactly should I do?",
                                "placeholder": "Add concrete target or desired outcome",
                            }
                        ]
                        if needs_input
                        else []
                    ),
                )
            if plan_schema and needs_input:
                plan_schema.needs_user_input = True
                plan_schema.questions = [
                    {
                        "id": "clarify",
                        "question": "Your request is ambiguous. What exactly should I do?",
                        "placeholder": "Add concrete target or desired outcome",
                    }
                ]
        except Exception:
            plan_schema = None
        plan_json = json.dumps(
            [
                {
                    "step": s.step,
                    "action": s.action,
                    "target": s.target,
                    "value": s.value,
                    "reason": s.reason,
                    "command": s.command,
                }
                for s in steps
            ]
        )
        run = TaskRun(
            run_id=run_id,
            intent=intent,
            plan_steps=steps,
            plan_schema=plan_schema,
            approved=False,
            mode="advanced" if self.advanced_mode else "demo",
            status=OrchestratorState.PLANNED.value,
            created_at=datetime.utcnow().isoformat() + "Z",
            command=cmd,
            trace_id=trace_id,
        )
        if needs_input:
            self._log_event(
                "needs_input",
                {"run_id": run_id, "questions": plan_schema.questions if plan_schema else []},
            )
        self.pending_runs[run_id] = run
        self.memory.create_task_run(
            run_id=run.run_id,
            status=run.status,
            approved=run.approved,
            command=run.command,
            intent_json=json.dumps(run.intent),
            plan_json=plan_json,
        )
        return run

    def _hydrate_task_run(self, payload: Dict) -> TaskRun:
        intent = json.loads(payload.get("intent_json") or "{}")
        plan_raw = json.loads(payload.get("plan_json") or "[]")
        steps = []
        for item in plan_raw:
            try:
                steps.append(
                    PlanStep(
                        step=item.get("step", 0),
                        action=item.get("action", ""),
                        target=item.get("target", ""),
                        value=item.get("value", ""),
                        reason=item.get("reason", ""),
                        command=item.get("command", ""),
                    )
                )
            except Exception:
                continue
        return TaskRun(
            run_id=payload.get("run_id", ""),
            intent=intent,
            plan_steps=steps,
            approved=bool(payload.get("approved")),
            mode="advanced" if self.advanced_mode else "demo",
            status=payload.get("status") or OrchestratorState.PLANNED.value,
            created_at=payload.get("created_at") or "",
            command=payload.get("command") or "",
            trace_id=payload.get("trace_id") or "",
        )

    def _load_last_run(self) -> None:
        if not hasattr(self.memory, "get_latest_task_run"):
            return
        try:
            payload = self.memory.get_latest_task_run()
        except Exception:
            return
        if not payload:
            return
        try:
            run = self._hydrate_task_run(payload)
        except Exception:
            return
        self.current_run = run
        self.pending_runs[run.run_id] = run
        if run.plan_steps:
            self._set_plan_text(self._format_plan(run.intent, run.plan_steps))
            self._reset_action_cards(run.plan_steps)
        if run.status in (OrchestratorState.PLANNED.value, OrchestratorState.APPROVED.value):
            self.approve_btn.configure(state=tk.NORMAL)
        else:
            self.approve_btn.configure(state=tk.DISABLED)

    def _set_run_status(self, run: TaskRun, status: str) -> None:
        if run.status == status:
            return
        validate_transition(run.status, status)
        run.status = status
        self.memory.update_task_run(run.run_id, status=run.status)

    def approve_run(self) -> None:
        if not self.current_run:
            self.log_line("No plan to approve.")
            return
        self.current_run.approved = True
        self._set_run_status(self.current_run, OrchestratorState.APPROVED.value)
        self.memory.update_task_run(self.current_run.run_id, approved=True)
        self.approve_btn.configure(state=tk.DISABLED)
        self.task_queue.enqueue(lambda: self._run_task_run(self.current_run))

    def edit_plan(self) -> None:
        if not self.current_run:
            return
        self.input_var.set(self.current_run.command)
        self.log_line("Plan returned to input for editing.")

    def cancel_plan(self) -> None:
        if not self.current_run:
            return
        self._set_run_status(self.current_run, OrchestratorState.STOPPED.value)
        self.current_run = None
        self._set_plan_text("")
        self._reset_action_cards([])
        self.approve_btn.configure(state=tk.DISABLED)
        self.log_line("Plan cancelled.")

    def _start_proof_pack(self, run: TaskRun) -> None:
        base = os.path.join(self.settings.data_dir, "runs", run.run_id)
        screenshots_dir = os.path.join(base, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        run.run_dir = base
        run.screenshots_dir = screenshots_dir
        run.actions_path = os.path.join(base, "actions.jsonl")
        run.events_path = os.path.join(base, "events.jsonl")
        run.extracted_path = os.path.join(base, "extracted.txt")
        self._log_event("run_start", {"run_id": run.run_id, "intent": run.intent})
        self.memory.log_nondet_input(run.run_id, "time", datetime.utcnow().isoformat() + "Z")

    def _write_summary(self, run: TaskRun) -> None:
        summary_path = os.path.join(run.run_dir, "summary.md")
        lines = [
            f"# Run {run.run_id}",
            "",
            f"Status: {run.status}",
            f"Mode: {run.mode}",
            "",
            "## Intent",
            json.dumps(run.intent, indent=2),
            "",
            "## Plan Steps",
        ]
        for step in run.plan_steps:
            lines.append(f"- {step.step}. {step.action} → {step.target} ({step.reason})")
        with open(summary_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))

    def _run_task_run(self, run: TaskRun) -> None:
        if not run.approved:
            self.log_line("Execution blocked: plan not approved.")
            return
        self.current_run = run
        if run.plan_schema and getattr(run.plan_schema, "needs_user_input", False):
            self.log_line("Execution blocked: additional clarification required.")
            try:
                self._set_run_status(run, OrchestratorState.PAUSED.value)
            except Exception:
                pass
            return
        self.stop_event.clear()
        self._set_run_status(run, OrchestratorState.RUNNING.value)
        hb = RunHeartbeat(run_id=run.run_id, status=run.status, timestamp=time.time(), trace_id=run.trace_id)
        log_audit(self.memory, "run_heartbeat", hb.__dict__, redact=getattr(self, "redact_logs", False))
        self._start_proof_pack(run)
        self._tool_calls_this_task = 0
        if run.plan_schema:
            report = self._run_plan_schema(run.plan_schema)
            run.report = report
            if report.status == "succeeded":
                self._set_run_status(run, OrchestratorState.COMPLETE.value)
            elif report.status == "needs_input":
                self._set_run_status(run, OrchestratorState.PAUSED.value)
            else:
                self._set_run_status(run, OrchestratorState.ERROR.value)
            return
        for step in run.plan_steps:
            self._current_step_id = step.step
            if self.step_approval_enabled:
                self.waiting_for_step = True
                self.step_approval_event.clear()
                self.log_line(f"Awaiting approval for step {step.step}.")
                while not self.step_approval_event.is_set():
                    time.sleep(0.2)
                    if self.stop_event.is_set():
                        self._set_run_status(run, OrchestratorState.STOPPED.value)
                        break
                if run.status == OrchestratorState.STOPPED.value:
                    break
            if self.stop_event.is_set():
                self._set_run_status(run, OrchestratorState.STOPPED.value)
                break
            self._set_action_status(step.step, "running", datetime.utcnow().isoformat() + "Z")
            self._record_action(step, "running")
            try:
                self._execute_step(step.command)
                self._set_action_status(step.step, "done", datetime.utcnow().isoformat() + "Z")
                self._record_action(step, "done")
                self._capture_step_screenshot(step)
            except Exception as exc:
                self._set_action_status(step.step, "failed", datetime.utcnow().isoformat() + "Z")
                self._record_action(step, "failed", error=str(exc))
                self._set_run_status(run, OrchestratorState.ERROR.value)
                break
            finally:
                self._current_step_id = None
            while self.pause_event.is_set():
                time.sleep(0.2)
                if self.stop_event.is_set():
                    self._set_run_status(run, OrchestratorState.STOPPED.value)
                    break
        if run.status == OrchestratorState.RUNNING.value:
            self._set_run_status(run, OrchestratorState.COMPLETE.value)
        hb = RunHeartbeat(run_id=run.run_id, status=run.status, timestamp=time.time(), trace_id=run.trace_id)
        log_audit(self.memory, "run_heartbeat", hb.__dict__, redact=getattr(self, "redact_logs", False))
        self._write_summary(run)
        if run.status == OrchestratorState.COMPLETE.value:
            try:
                recipe = {
                    "intent": run.intent,
                    "steps": [
                        {
                            "step": s.step,
                            "action": s.action,
                            "target": s.target,
                            "value": s.value,
                            "reason": s.reason,
                            "command": s.command,
                        }
                        for s in run.plan_steps
                    ],
                }
                self.memory.add_memory(
                    kind="recipe",
                    content=json.dumps(recipe),
                    tags=["recipe", "taskrun"],
                    scope="shared",
                )
            except Exception:
                pass
            try:
                skills_dir = os.path.join(self.settings.data_dir, "skills")
                os.makedirs(skills_dir, exist_ok=True)
                skill_text = "\n".join([s.command for s in run.plan_steps])
                if "def " in skill_text or ".py" in skill_text or "code" in skill_text.lower():
                    path = os.path.join(skills_dir, f"skill_{run.run_id}.txt")
                    with open(path, "w", encoding="utf-8") as handle:
                        handle.write(skill_text)
                    self.memory.add_memory(
                        kind="skill",
                        content=skill_text[:2000],
                        tags=["skill", "voyager"],
                        scope="shared",
                    )
            except Exception:
                pass
        self.log_line(f"Proof pack saved to: {run.run_dir}")


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
            run_id, step_id = self._memory_context()
            self.memory.add_memory(
                "summary",
                summary,
                ttl_seconds=self.settings.long_memory_ttl,
                run_id=run_id,
                step_id=step_id,
            )
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

    def _memory_context(self) -> tuple[str | None, int | None]:
        run_id = self.current_run.run_id if getattr(self, "current_run", None) else None
        step_id = getattr(self, "_current_step_id", None)
        return run_id, step_id

    def _start_memory_prune_loop(self) -> None:
        interval = getattr(self.settings, "memory_prune_interval_seconds", 0)
        if interval <= 0:
            return
        try:
            self.memory.prune_memories()
        except Exception:
            pass

        def _loop() -> None:
            while not self._memory_prune_stop.is_set():
                try:
                    self.memory.prune_memories()
                except Exception:
                    pass
                self._memory_prune_stop.wait(interval)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    def _start_watchers(self) -> None:
        watch_path = os.getenv("AGENTIC_WATCH_FILE", "")
        if not watch_path or not os.path.exists(watch_path):
            pass
        pattern = os.getenv("AGENTIC_WATCH_REGEX", "error|exception|traceback")
        try:
            regex = re.compile(pattern, flags=re.IGNORECASE)
        except Exception:
            regex = re.compile("error|exception|traceback", flags=re.IGNORECASE)

        def _tail() -> None:
            try:
                with open(watch_path, "r", encoding="utf-8", errors="ignore") as handle:
                    handle.seek(0, os.SEEK_END)
                    while True:
                        line = handle.readline()
                        if not line:
                            time.sleep(0.5)
                            continue
                        if regex.search(line):
                            self._log_event(
                                "ui_block",
                                {"ui": {"type": "toast", "message": line.strip(), "level": "warning"}},
                            )
            except Exception:
                return

        threading.Thread(target=_tail, daemon=True).start()

        sched_raw = os.getenv("AGENTIC_SCHEDULE_JSON", "")
        if sched_raw:
            try:
                sched = json.loads(sched_raw)
            except Exception:
                sched = []
            for item in sched:
                try:
                    interval = int(item.get("interval_s") or 60)
                    command = item.get("command") or ""
                    if not command:
                        continue
                    def _loop(cmd=command, wait=interval):
                        while True:
                            try:
                                self._orchestrate(cmd)
                            except Exception:
                                pass
                            time.sleep(max(5, wait))
                    threading.Thread(target=_loop, daemon=True).start()
                except Exception:
                    continue

    def _apply_policy_pack(self) -> None:
        policy_path = getattr(self.settings, "policy_path", "") or os.getenv("AGENTIC_POLICY_PATH", "")
        if not policy_path:
            return
        try:
            with open(policy_path, "r", encoding="utf-8") as handle:
                policy = json.load(handle)
        except Exception:
            return
        for key in ("allowed_paths", "allowed_domains", "autonomy_level", "demo_mode", "redact_logs"):
            if key in policy and policy[key] is not None:
                setattr(self.settings, key, str(policy[key]))
        if "purpose" in policy:
            self.settings.purpose = str(policy["purpose"])
        if "max_tool_calls_per_task" in policy:
            try:
                self.settings.max_tool_calls_per_task = int(policy["max_tool_calls_per_task"])
            except Exception:
                pass
        if "max_plan_steps" in policy:
            try:
                self.settings.max_plan_steps = int(policy["max_plan_steps"])
            except Exception:
                pass
        if "event_retention_seconds" in policy:
            try:
                self.settings.event_retention_seconds = int(policy["event_retention_seconds"])
            except Exception:
                pass
        self._memory_prune_thread = t



    def _agent_chat(self, instruction):
        if getattr(self, "dot_mode", False):
            return dot_ensemble(self._agent_chat_base, instruction)
        if getattr(self, "slow_mode", False):
            return slow_mode(self._agent_chat_base, instruction)
        return self._agent_chat_base(instruction)

    def _agent_chat_base(self, instruction):

        prefer_offline = getattr(self, "edge_mode", "auto") == "offline"
        model_name = _configure_agent(self.settings, instruction, prefer_offline=prefer_offline)
        safety_hits = screen_text(instruction)
        if safety_hits:
            self.log_line(f"Safety screen flagged patterns: {', '.join(safety_hits)}")

        oi_mode = (getattr(self.settings, "oi_mode", "text_only") or "text_only").lower()
        if oi_mode in ("disabled", "off", "false"):
            raise RuntimeError("open-interpreter is disabled by AGENTIC_OI_MODE")
        if oi_mode == "text_only":
            oi_interpreter.auto_run = False
            # Best-effort safety knobs if supported by open-interpreter.
            for attr in ("safe_mode", "block_code", "deny_shell"):
                if hasattr(oi_interpreter, attr):
                    try:
                        setattr(oi_interpreter, attr, True)
                    except Exception:
                        pass
        else:
            oi_interpreter.auto_run = True

        oi_interpreter.system_message = (

            "You are ChatGPT with full access to the user's computer and browser. "

            "When the user asks for actions, perform them directly. "

            "When the user asks for information or conversation, respond normally. "

            "Always be concise and confirm destructive actions."

        )
        if oi_mode == "text_only":
            oi_interpreter.system_message += (
                " IMPORTANT: Do NOT execute actions, run code, browse, or access files. "
                "Respond with text-only guidance and proposed steps."
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
        try:
            user_profile = self.memory.get_user_profile("default")
            if user_profile:
                oi_interpreter.system_message += f" User profile: {json.dumps(user_profile)}."
        except Exception:
            pass

        context = self.retriever.retrieve(instruction)

        if context:

            instruction = f"Context:\n{context}\n\nUser: {instruction}"

        self._add_message("user", instruction)

        run_id, step_id = self._memory_context()
        self.memory.add_memory(
            "short",
            f"USER: {instruction}",
            ttl_seconds=self.settings.short_memory_ttl,
            run_id=run_id,
            step_id=step_id,
        )

        extra = {"model": model_name or ""}
        self._log_event("instruction", instruction, extra)

        if getattr(self, "current_run", None):
            run_id = self.current_run.run_id
            prompt_hash = hashlib.sha256((oi_interpreter.system_message + instruction).encode("utf-8")).hexdigest()
            env_fp = f"{sys.platform}|{platform.python_version()}"
            self.memory.log_run_context(run_id, model_name or "", prompt_hash, "tools@local", env_fp)

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

        # Swarm-style handoff (detect JSON with handoff_to)
        try:
            if output.startswith("{") and output.endswith("}"):
                payload = json.loads(output)
                if payload.get("handoff_to"):
                    peer = payload.get("handoff_to")
                    msg = payload.get("message") or payload.get("text") or ""
                    if peer and msg:
                        self.a2a_net.send(peer, getattr(self, "node_name", "work"), "remote", {"type": "chat", "text": msg})
                        output = f"Handoff to {peer}: {msg}"
        except Exception:
            pass

        if output:

            self._log_event("response", output, extra)

            logging.info("response: %s", self._maybe_redact(output)[:500])

            self._add_message("assistant", output)

            run_id, step_id = self._memory_context()
            self.memory.add_memory(
                "short",
                f"ASSISTANT: {output}",
                ttl_seconds=self.settings.short_memory_ttl,
                run_id=run_id,
                step_id=step_id,
            )

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
        try:
            self.metrics.inc("tokens_in", tokens_in)
            self.metrics.inc("tokens_out", tokens_out)
        except Exception:
            pass

        return output



    def _step_to_schema(self, step_id: int, step_text: str) -> PlanStepSchema:
        raw_text = step_text
        verify = None
        if " verify:" in step_text:
            main, verify_raw = step_text.split(" verify:", 1)
            step_text = main.strip()
            verify = self._parse_verify(verify_raw)
        lowered = step_text.strip().lower()
        for name in self.tools.tools.keys():
            prefix = f"{name} "
            if lowered.startswith(prefix):
                args_str = step_text[len(prefix):].strip()
                spec = self.tools.specs.get(name)
                risk = spec.risk if spec else "safe"
                confirm = bool(getattr(spec, "confirm_required", False))
                if requires_confirmation(risk, getattr(self.settings, "autonomy_level", "semi")):
                    confirm = True
                return PlanStepSchema(
                    step_id=step_id,
                    title=f"{name} {args_str}"[:120],
                    intent="Tool call",
                    tool=name,
                    args={"raw": args_str},
                    risk=risk,
                    requires_confirmation=confirm,
                    timeout_s=90,
                    max_attempts=2,
                    verify=verify,
                )
        return PlanStepSchema(
            step_id=step_id,
            title=step_text[:120],
            intent="Agent step",
            tool="agent",
            args={"text": step_text},
            risk="safe",
            requires_confirmation=False,
            verify=verify,
        )

    def _tool_catalog(self) -> list[dict]:
        try:
            tools = UnifiedToolRegistry.from_legacy(self).list()
            if len(tools) > 40:
                tools = tools[:40]
            for t in tools:
                desc = t.get("description") or ""
                if len(desc) > 200:
                    t["description"] = desc[:200]
            return tools
        except Exception:
            return []

    def _plan_schema_to_steps(self, plan_schema: PlanSchema) -> list[PlanStep]:
        steps: list[PlanStep] = []
        for s in plan_schema.steps:
            steps.append(
                PlanStep(
                    step=s.step_id,
                    action=s.tool or "execute",
                    target=s.title,
                    value="",
                    reason=s.intent or "planned",
                    command=s.args.get("command") or f"{s.tool} {json.dumps(s.args)}".strip(),
                )
            )
        return steps

    def _resolve_entities(self, text: str) -> str:
        try:
            blob = self.memory.get("entity_aliases") or "{}"
            data = json.loads(blob)
        except Exception:
            data = {}
        if not data:
            return text
        out = text
        for alias, canonical in data.items():
            out = re.sub(rf"\\b{re.escape(alias)}\\b", canonical, out, flags=re.IGNORECASE)
        return out

    def _plan_with_llm(self, instruction: str) -> PlanSchema | None:
        instruction = self._resolve_entities(instruction)
        tools = self._tool_catalog()
        if not tools:
            return None
        prompt = (
            "Return ONLY JSON for PlanSchema. Include goal, success_criteria, steps with tool and args. "
            "Available tools:\n"
            + json.dumps(tools, indent=2)
        )
        raw = ""
        try:
            raw = self._agent_chat(prompt + "\nUser goal: " + instruction) or ""
        except Exception:
            return None
        if not raw:
            return None
        data = None
        try:
            data = json.loads(raw)
        except Exception:
            try:
                fix_prompt = "Fix this into valid PlanSchema JSON only, no prose. Content:\n" + raw
                repaired = self._agent_chat(fix_prompt) or ""
                data = json.loads(repaired)
            except Exception:
                return None
        try:
            steps = []
            for idx, s in enumerate(data.get("steps") or [], 1):
                tool = (s.get("tool") or "").strip()
                tool_meta = next((t for t in tools if t["name"] == tool), None)
                if tool and tool_meta is None:
                    tool = ""
                risk = (tool_meta or {}).get("risk_level", "safe")
                steps.append(
                    PlanStepSchema(
                        step_id=int(s.get("step_id") or idx),
                        title=s.get("title") or tool or f"step {idx}",
                        intent=s.get("intent") or "",
                        tool=tool,
                        args=s.get("args") or {},
                        risk=risk,
                        requires_confirmation=bool((tool_meta or {}).get("requires_approval", False)),
                        max_attempts=int(s.get("max_attempts") or 2),
                        timeout_s=int(s.get("timeout_s") or 90),
                        success_check=s.get("success_check") or "",
                    )
                )
            if not steps and not data.get("needs_user_input"):
                return None
            budget = data.get("budget") or {}
            plan = PlanSchema(
                run_id=data.get("run_id") or datetime.utcnow().strftime("%Y-%m-%d_%H%M%S"),
                trace_id=data.get("trace_id") or str(uuid.uuid4()),
                goal=data.get("goal") or instruction,
                success_criteria=data.get("success_criteria") or ["Task completed without errors"],
                steps=steps,
                needs_user_input=bool(data.get("needs_user_input") or False),
                questions=data.get("questions") or [],
                assumptions=data.get("assumptions") or [],
                constraints=data.get("constraints") or {},
                budget=Budget(
                    max_steps=int(budget.get("max_steps") or getattr(self.settings, "max_plan_steps", 20) or 20),
                    max_tool_calls=int(budget.get("max_tool_calls") or getattr(self.settings, "max_tool_calls_per_task", 50) or 50),
                    max_seconds=int(budget.get("max_seconds") or 900),
                ),
                created_at=time.time(),
                model=data.get("model") or "",
            )
            return self._validate_plan_schema(plan)
        except Exception:
            return None

    def _validate_plan_schema(self, plan: PlanSchema) -> PlanSchema | None:
        if not plan.goal:
            return None
        if plan.needs_user_input:
            return plan
        if not plan.steps:
            return None
        for step in plan.steps:
            if not step.tool:
                step.tool = "agent"
            if step.tool != "agent" and step.tool not in self.tools.tools:
                step.tool = "agent"
        return plan

    def _parse_verify(self, raw: str) -> Optional[VerifySchema]:
        raw = (raw or "").strip()
        if not raw:
            return None
        parts = shlex.split(raw)
        if not parts:
            return None
        vtype = parts[0].strip().lower()
        params: Dict[str, Any] = {}
        for item in parts[1:]:
            if "=" in item:
                k, v = item.split("=", 1)
                params[k.strip()] = v.strip()
        return VerifySchema(type=vtype, params=params)

    def _execute_step_schema(self, step: PlanStepSchema) -> ToolResult:
        t0 = time.time()
        ok = False
        out = ""
        err = ""
        try:
            if step.tool == "agent":
                out = self._agent_chat(step.args.get("text", "")) or ""
                ok = True
            elif step.tool == "computer":
                payload: dict = {}
                raw = step.args.get("raw") if isinstance(step.args, dict) else ""
                if raw:
                    try:
                        payload = json.loads(raw)
                    except Exception:
                        payload = {"mode": "act", "params": {"raw": raw}}
                else:
                    if isinstance(step.args, dict):
                        payload = dict(step.args)
                if "mode" not in payload:
                    payload["mode"] = "act"
                if payload.get("primary") or payload.get("fallbacks"):
                    attempts = []
                    primary = payload.get("primary") or {}
                    if primary:
                        attempts.append(primary)
                    for fb in payload.get("fallbacks") or []:
                        attempts.append(fb)
                    last_err = ""
                    for candidate in attempts:
                        action = candidate.get("action") or payload.get("action") or "click"
                        params = dict(payload.get("params") or {})
                        params.update(candidate)
                        if "text" in candidate and "selector" not in candidate:
                            params["selector"] = f"text={candidate.get('text')}"
                        if "coords" in candidate and "x" not in params and "y" not in params:
                            try:
                                params["x"], params["y"] = candidate.get("coords")
                                params["backend"] = "desktop"
                            except Exception:
                                pass
                        if "backend" not in params:
                            params["backend"] = self._get_computer_backend(step.args if isinstance(step.args, dict) else {})
                        act_payload = {"mode": "act", "action": action, "params": params}
                        try:
                            out = self._execute_tool("computer", json.dumps(act_payload)) or ""
                            ok = True
                            break
                        except Exception as exc:
                            last_err = str(exc)
                            ok = False
                    if not ok:
                        err = last_err
                else:
                    params = payload.get("params") or {}
                    if "backend" not in params:
                        params["backend"] = self._get_computer_backend(step.args if isinstance(step.args, dict) else {})
                    payload["params"] = params
                    out = self._execute_tool("computer", json.dumps(payload)) or ""
                    ok = True
            else:
                raw = step.args.get("raw", "")
                out = self._execute_tool(step.tool, raw) or ""
                ok = True
        except Exception as exc:
            err = str(exc)
            ok = False
        t1 = time.time()
        return ToolResult(
            name=step.tool,
            args=step.args,
            risk=step.risk,
            ok=ok,
            started_at=t0,
            ended_at=t1,
            output_preview=(out[:2000] if out else ""),
            error=(err[:2000] if err else ""),
            files_changed=[],
        )

    def _get_computer_backend(self, step_args: dict | None = None) -> str:
        backend = ""
        if isinstance(step_args, dict):
            backend = step_args.get("backend") or (step_args.get("params") or {}).get("backend") or ""
        if not backend:
            backend = self.memory.get("computer_backend") or os.getenv("AGENTIC_COMPUTER_BACKEND", "browser")
        backend = str(backend).strip().lower()
        return backend or "browser"

    def _desktop_requires_approval(self) -> bool:
        value = self.memory.get("computer_desktop_approval") or os.getenv("AGENTIC_DESKTOP_APPROVAL", "true")
        return str(value).lower() in ("1", "true", "yes", "on")

    def _tool_risk(self, name: str) -> str:
        spec = self.tools.specs.get(name)
        return (spec.risk if spec else "unknown") or "unknown"

    def _issue_token(self, name: str) -> None:
        self.memory.set(f"approval_token:{name}", str(time.time()))

    def _consume_token(self, name: str, ttl_seconds: int = 600) -> bool:
        key = f"approval_token:{name}"
        value = self.memory.get(key)
        if not value:
            return False
        try:
            ts = float(value)
        except Exception:
            self.memory.set(key, "")
            return False
        if time.time() - ts > ttl_seconds:
            self.memory.set(key, "")
            return False
        self.memory.set(key, "")
        return True

    def _needs_approval(self, name: str, args: dict | None = None) -> bool:
        risk = self._tool_risk(name)
        if name == "computer":
            backend = self._get_computer_backend(args or {})
            if backend == "desktop" and self._desktop_requires_approval():
                return True
        if risk == "destructive" and not self._consume_token(name):
            return True
        return requires_confirmation(risk, getattr(self.settings, "autonomy_level", "semi"))

    def _verify_step(self, step: PlanStepSchema, result: ToolResult) -> tuple[bool, str]:
        verify = step.verify
        if verify is None:
            return True, ""
        vtype = (verify.type or "").strip().lower()
        params = verify.params or {}
        if vtype == "output_contains":
            needle = (params.get("text") or "").strip()
            return (needle.lower() in (result.output_preview or "").lower()), f"output_contains:{needle}"
        if vtype == "file_exists":
            path = params.get("path") or params.get("file") or ""
            ok = bool(path) and os.path.exists(path)
            return ok, f"file_exists:{path}"
        if vtype == "dom_present":
            selector = params.get("selector") or ""
            if not selector or self.page is None:
                return False, "dom_present:missing_selector_or_page"
            try:
                count = self.page.locator(selector).count()
                return count > 0, f"dom_present:{selector}"
            except Exception as exc:
                return False, f"dom_present:error:{exc}"
        if vtype == "uia_present":
            try:
                query = params.get("query") or {}
                if isinstance(query, str):
                    try:
                        query = json.loads(query)
                    except Exception:
                        query = {"name": query}
                if not isinstance(query, dict):
                    query = {}
                found = find_uia_first(query) is not None
                return found, f"uia_present:{query}"
            except Exception as exc:
                return False, f"uia_present:error:{exc}"
        if vtype == "sql_returns":
            db_path = params.get("db_path") or ""
            query = params.get("query") or ""
            if not db_path or not query:
                return False, "sql_returns:missing_params"
            try:
                import sqlite3
                with sqlite3.connect(db_path) as conn:
                    cur = conn.execute(query)
                    row = cur.fetchone()
                return row is not None, "sql_returns:row_found" if row is not None else "sql_returns:no_rows"
            except Exception as exc:
                return False, f"sql_returns:error:{exc}"
        if vtype == "test_passes":
            cmd = params.get("command") or ""
            if not cmd:
                return False, "test_passes:missing_command"
            allowed = os.getenv("AGENTIC_ALLOWED_VERIFY", "")
            if allowed:
                allow_list = [c.strip() for c in allowed.split(";") if c.strip()]
                if cmd not in allow_list:
                    return False, "test_passes:command_not_allowed"
            try:
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=step.timeout_s)
                return proc.returncode == 0, f"test_passes:rc={proc.returncode}"
            except Exception as exc:
                return False, f"test_passes:error:{exc}"
        return False, f"verify:unknown_type:{vtype}"

    def _evaluate_success_check(self, step: PlanStepSchema, result: ToolResult) -> tuple[bool, str]:
        sc = step.success_check
        if not sc:
            return True, ""
        if isinstance(sc, dict):
            sc_type = (sc.get("type") or "").lower()
            if sc_type in ("output_contains", "file_exists", "dom_present", "uia_present", "sql_returns", "test_passes"):
                verify = VerifySchema(type=sc_type, params=sc)
                temp = PlanStepSchema(
                    step_id=step.step_id,
                    title=step.title,
                    intent=step.intent,
                    tool=step.tool,
                    args=step.args,
                    verify=verify,
                )
                return self._verify_step(temp, result)
            if sc_type == "window_title":
                target = (sc.get("value") or "").lower()
                try:
                    nodes = snapshot_uia(limit=200)
                except Exception:
                    nodes = []
                found = any(target in (n.get("title") or "").lower() for n in nodes)
                return found, f"window_title:{target}"
            if sc_type == "uia_contains":
                target = (sc.get("name") or "").lower()
                try:
                    nodes = snapshot_uia(limit=500)
                except Exception:
                    nodes = []
                found = any(target in (n.get("title") or "").lower() for n in nodes)
                return found, f"uia_contains:{target}"
            return False, f"success_check_failed:{sc}"
        if str(sc).lower() in (result.output_preview or "").lower():
            return True, f"output_contains:{sc}"
        return False, f"success_check_failed:{sc}"

    def _run_plan_schema(self, plan: PlanSchema, report: ExecutionReport | None = None, start_step_id: int | None = None) -> ExecutionReport:
        if report is None:
            report = ExecutionReport(
                run_id=plan.run_id,
                trace_id=plan.trace_id,
                goal=plan.goal,
                status="running",
                started_at=time.time(),
                ended_at=0.0,
            )
        else:
            report.status = "running"
        self._log_event("run_started", {"goal": plan.goal})
        try:
            est_tokens = estimate_tokens(plan.goal + json.dumps([s.__dict__ for s in plan.steps]))
            est_cost = estimate_cost(
                est_tokens,
                max(1, int(est_tokens * 0.3)),
                self.settings.openai_cost_input_per_million,
                self.settings.openai_cost_output_per_million,
            )
            report.cost = {"estimated_cost": est_cost, "estimated_tokens": est_tokens}
            max_cost = float(os.getenv("AGENTIC_MAX_PLAN_COST", "0") or 0)
            if max_cost and est_cost > max_cost:
                self._log_event("tool_call_blocked", {"tool": "cost_estimate", "args": report.cost})
                self.memory.set("pending_action", json.dumps({"type": "cost", "name": "plan_cost", "args": report.cost}))
                self.memory.set("pending_step_id", "1")
                self.memory.set("pending_plan_run_id", plan.run_id)
                report.status = "needs_input"
                report.failure_reason = "cost_threshold_exceeded"
                return report
        except Exception:
            pass
        if plan.needs_user_input:
            self._log_event(
                "ui_block",
                {"ui": {"type": "form", "title": "More info needed", "fields": plan.questions}},
            )
            report.status = "needs_input"
            report.failure_reason = "needs_user_input"
            return report
        tool_calls = 0
        if "per_step" not in report.cost:
            report.cost["per_step"] = []
        started = time.time()
        for step in plan.steps:
            if start_step_id and step.step_id < start_step_id:
                continue
            self._current_step_id = step.step_id
            self._write_run_state(plan, report, current_step=step.step_id)
            if len(report.steps) >= plan.budget.max_steps:
                self._current_step_id = None
                report.status = "failed"
                report.failure_reason = "Budget exceeded: max_steps"
                break
            if (time.time() - started) > plan.budget.max_seconds:
                self._current_step_id = None
                report.status = "failed"
                report.failure_reason = "Budget exceeded: max_seconds"
                break
            self._log_event(
                "step_started",
                {"title": step.title, "tool": step.tool, "risk": step.risk},
                extra={"step_id": step.step_id},
            )
            step_rep = StepReport(step_id=step.step_id, title=step.title, status="running")
            report.steps.append(step_rep)
            try:
                step_tokens = estimate_tokens(step.title + json.dumps(step.args))
                step_cost = estimate_cost(
                    step_tokens,
                    max(1, int(step_tokens * 0.3)),
                    self.settings.openai_cost_input_per_million,
                    self.settings.openai_cost_output_per_million,
                )
                report.cost["per_step"].append({"step_id": step.step_id, "tokens": step_tokens, "cost": step_cost})
            except Exception:
                pass
            if step.tool != "agent":
                tool_calls += 1
                if tool_calls > plan.budget.max_tool_calls:
                    self._current_step_id = None
                    step_rep.status = "failed"
                    report.status = "failed"
                    report.failure_reason = "Budget exceeded: max_tool_calls"
                    break
            step.requires_confirmation = step.requires_confirmation or self._needs_approval(step.tool, step.args if isinstance(step.args, dict) else {})
            if step.requires_confirmation:
                if self.memory.get(f"deny_tool:{step.tool}") == "true":
                    self._current_step_id = None
                    report.status = "needs_input"
                    step_rep.status = "skipped"
                    report.failure_reason = f"Tool {step.tool} blocked by policy"
                    break
                if self.memory.get(f"allow_tool:{step.tool}") != "true" and self.step_approval_enabled:
                    pending_args = step.args.get("raw", "") if isinstance(step.args, dict) else ""
                    if step.tool == "computer":
                        payload = {}
                        if pending_args:
                            try:
                                payload = json.loads(pending_args)
                            except Exception:
                                payload = {"mode": "act", "params": {"raw": pending_args}}
                        else:
                            if isinstance(step.args, dict):
                                payload = dict(step.args)
                        if "mode" not in payload:
                            payload["mode"] = "act"
                        params = payload.get("params") or {}
                        if "backend" not in params:
                            params["backend"] = self._get_computer_backend(step.args if isinstance(step.args, dict) else {})
                        payload["params"] = params
                        pending_args = json.dumps(payload)
                    self._log_event(
                        "tool_call_blocked",
                        {"tool": step.tool, "args": step.args},
                        extra={"step_id": step.step_id},
                    )
                    self.memory.set("pending_action", json.dumps({"type": "tool", "name": step.tool, "args": pending_args}))
                    self.memory.set("pending_step_id", str(step.step_id))
                    self.memory.set("pending_plan_run_id", plan.run_id)
                    self._current_step_id = None
                    report.status = "needs_input"
                    step_rep.status = "skipped"
                    break
            ok = False
            for attempt in range(1, step.max_attempts + 1):
                step_rep.attempts = attempt
                self._log_event(
                    "tool_call_started",
                    {"tool": step.tool, "args": step.args, "attempt": attempt},
                    extra={"step_id": step.step_id},
                )
                before_hash = ""
                if step.tool == "computer":
                    try:
                        obs = self.tools.computer.observe(os.path.join(self.settings.data_dir, "runs", plan.run_id))
                        before_hash = getattr(obs, "screenshot_hash", "") or ""
                    except Exception:
                        pass
                tr = self._execute_step_schema(step)
                step_rep.tool_results.append(tr)
                if step.tool == "computer":
                    try:
                        obs_after = self.tools.computer.observe(os.path.join(self.settings.data_dir, "runs", plan.run_id))
                        after_hash = getattr(obs_after, "screenshot_hash", "") or ""
                        expect_change = True
                        if isinstance(step.args, dict):
                            expect_change = bool(step.args.get("expect_change", True))
                        if expect_change and before_hash and after_hash and before_hash == after_hash and not step.success_check:
                            tr.ok = False
                            tr.error = "no_ui_change_detected"
                    except Exception:
                        pass
                if tr.ok and step.success_check:
                    ok_sc, evidence = self._evaluate_success_check(step, tr)
                    if not ok_sc:
                        tr.ok = False
                        tr.error = evidence or f"success_check_failed: {step.success_check}"
                self._log_event(
                    "tool_call_finished",
                    {"tool": tr.name, "ok": tr.ok, "output_preview": tr.output_preview, "error": tr.error},
                    extra={"step_id": step.step_id},
                )
                if not tr.ok:
                    backoff = 0.5
                    if isinstance(step.args, dict):
                        try:
                            backoff = float(step.args.get("backoff_s") or 0.5)
                        except Exception:
                            backoff = 0.5
                        retry = step.args.get("retry") or {}
                        if isinstance(retry, dict):
                            wait_s = float(retry.get("wait_s") or 0)
                            scroll = retry.get("scroll")
                            if scroll is not None and step.tool == "computer":
                                try:
                                    payload = {"mode": "act", "action": "scroll", "params": {"amount": int(scroll), "backend": self._get_computer_backend(step.args)}}
                                    self._execute_tool("computer", json.dumps(payload))
                                except Exception:
                                    pass
                            if wait_s > 0:
                                time.sleep(wait_s)
                    if attempt < step.max_attempts:
                        time.sleep(backoff * attempt)
                if tr.ok:
                    verified, evidence = self._verify_step(step, tr)
                    step_rep.verification_passed = verified
                    step_rep.verification_evidence = evidence
                    if not verified:
                        self._log_event(
                            "step_verify_failed",
                            {"step": step.step_id, "evidence": evidence},
                            extra={"step_id": step.step_id},
                        )
                        if attempt == step.max_attempts:
                            self._log_event(
                                "nudge",
                                {"message": f"Verification failed for step {step.step_id}. Consider alternate strategy."},
                                extra={"step_id": step.step_id},
                            )
                        continue
                    ok = True
                    break
            step_rep.status = "succeeded" if ok else "failed"
            if ok:
                step_rep.verification_passed = True
                step_rep.verification_evidence = "ok"
                if step.tool in ("copy", "move") and isinstance(step.args, dict):
                    raw = step.args.get("raw", "")
                    if "|" in raw:
                        dest = raw.split("|", 1)[1].strip()
                        if dest and not os.path.exists(dest):
                            step_rep.verification_passed = False
                            step_rep.verification_evidence = "dest_missing"
                            ok = False
                if step.tool == "delete" and isinstance(step.args, dict):
                    raw = step.args.get("raw", "").strip()
                    if raw and os.path.exists(raw):
                        step_rep.verification_passed = False
                        step_rep.verification_evidence = "delete_failed"
                        ok = False
                if not ok:
                    step_rep.status = "failed"
            if step_rep.attempts > 1:
                self._log_event(
                    "nudge",
                    {"message": f"Step {step.step_id} required {step_rep.attempts} attempts."},
                    extra={"step_id": step.step_id},
                )
            self._log_event("step_finished", {"status": step_rep.status}, extra={"step_id": step.step_id})
            if step_rep.status == "failed":
                self._current_step_id = None
                report.status = "failed"
                report.failure_reason = f"Step {step.step_id} failed: {step.title}"
                break
            self._current_step_id = None
        if report.status == "running":
            report.status = "succeeded"
        report.ended_at = time.time()
        self._log_event("run_finished", {"status": report.status, "failure_reason": report.failure_reason})
        self._write_run_state(plan, report, current_step=None)
        return report

    def _write_run_artifacts(self, plan: PlanSchema, report: ExecutionReport) -> None:
        try:
            run_id = plan.run_id
            base = os.path.join(self.settings.data_dir, "runs", run_id)
            os.makedirs(base, exist_ok=True)
            with open(os.path.join(base, "plan.json"), "w", encoding="utf-8") as handle:
                json.dump(plan, handle, default=lambda o: o.__dict__, indent=2)
            with open(os.path.join(base, "report.json"), "w", encoding="utf-8") as handle:
                json.dump(report, handle, default=lambda o: o.__dict__, indent=2)
            summary_path = os.path.join(base, "summary.md")
            lines = [
                f"# Run {run_id}",
                "",
                f"Status: {report.status}",
                "",
                "## Goal",
                plan.goal,
                "",
                "## Steps",
            ]
            for step in plan.steps:
                lines.append(f"- {step.step_id}. {step.title} (tool={step.tool}, risk={step.risk})")
            lines.append("")
            lines.append("## Result")
            lines.append(report.failure_reason or "succeeded")
            with open(summary_path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
        except Exception:
            return

    def _write_run_state(self, plan: PlanSchema, report: ExecutionReport, current_step: int | None) -> None:
        try:
            base = os.path.join(self.settings.data_dir, "runs", plan.run_id)
            os.makedirs(base, exist_ok=True)
            state = {
                "run_id": plan.run_id,
                "goal": plan.goal,
                "status": report.status,
                "current_step": current_step,
                "updated_at": time.time(),
            }
            with open(os.path.join(base, "state.json"), "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2)
        except Exception:
            return

    def _latest_observations(self, run_id: str) -> dict:
        base = os.path.join(self.settings.data_dir, "runs", run_id)
        latest_screen = ""
        latest_uia = ""
        if not os.path.isdir(base):
            return {"screenshot": "", "uia": ""}
        try:
            screens = []
            uias = []
            for name in os.listdir(base):
                path = os.path.join(base, name)
                if name.startswith("screen-") and name.endswith(".png"):
                    try:
                        screens.append((os.path.getmtime(path), path))
                    except Exception:
                        continue
                if name.startswith("uia-") and name.endswith(".json"):
                    try:
                        uias.append((os.path.getmtime(path), path))
                    except Exception:
                        continue
            if screens:
                screens.sort(key=lambda x: x[0], reverse=True)
                latest_screen = screens[0][1]
            if uias:
                uias.sort(key=lambda x: x[0], reverse=True)
                latest_uia = uias[0][1]
        except Exception:
            return {"screenshot": "", "uia": ""}
        return {"screenshot": latest_screen, "uia": latest_uia}

    def _build_reflection_prompt(self, instruction: str, plan_schema: PlanSchema, report: ExecutionReport) -> str:
        failed_step = None
        for step in report.steps:
            if step.status in ("failed", "skipped"):
                failed_step = step
        if failed_step is None and report.steps:
            failed_step = report.steps[-1]
        last_result = ""
        last_error = ""
        if failed_step and failed_step.tool_results:
            last = failed_step.tool_results[-1]
            last_result = last.output_preview or ""
            last_error = last.error or ""
        obs = self._latest_observations(plan_schema.run_id)
        constraints = plan_schema.constraints or {}
        budget = plan_schema.budget.__dict__ if plan_schema.budget else {}
        parts = [
            "Fix failures using evidence.",
            f"Original task: {instruction}",
            f"Failure reason: {report.failure_reason}",
        ]
        if failed_step:
            parts.append(f"Failed step: {failed_step.step_id} - {failed_step.title}")
        if last_error:
            parts.append("Last error:")
            parts.append(last_error)
        if last_result:
            parts.append("Last output preview:")
            parts.append(last_result[:2000])
        if obs.get("screenshot"):
            parts.append(f"Latest screenshot: {obs['screenshot']}")
        if obs.get("uia"):
            parts.append(f"Latest UIA: {obs['uia']}")
        if constraints:
            parts.append(f"Constraints: {json.dumps(constraints)}")
        if budget:
            parts.append(f"Budget: {json.dumps(budget)}")
        return "\n".join(parts)

    def _load_plan_schema_file(self, run_id: str) -> PlanSchema | None:
        base = os.path.join(self.settings.data_dir, "runs", run_id, "plan.json")
        if not os.path.exists(base):
            return None
        try:
            data = json.load(open(base, "r", encoding="utf-8"))
        except Exception:
            return None
        try:
            steps = []
            for s in data.get("steps") or []:
                steps.append(
                    PlanStepSchema(
                        step_id=int(s.get("step_id") or 0),
                        title=s.get("title") or "",
                        intent=s.get("intent") or "",
                        tool=s.get("tool") or "",
                        args=s.get("args") or {},
                        risk=s.get("risk") or "safe",
                        requires_confirmation=bool(s.get("requires_confirmation") or False),
                        max_attempts=int(s.get("max_attempts") or 2),
                        timeout_s=int(s.get("timeout_s") or 90),
                        success_check=s.get("success_check") or "",
                    )
                )
            return PlanSchema(
                run_id=data.get("run_id") or run_id,
                trace_id=data.get("trace_id") or "",
                goal=data.get("goal") or "",
                success_criteria=data.get("success_criteria") or [],
                steps=steps,
                needs_user_input=bool(data.get("needs_user_input") or False),
                questions=data.get("questions") or [],
                assumptions=data.get("assumptions") or [],
                constraints=data.get("constraints") or {},
                budget=Budget(**(data.get("budget") or {})),
                created_at=float(data.get("created_at") or 0.0),
                model=data.get("model") or "",
            )
        except Exception:
            return None

    def _load_report_file(self, run_id: str) -> ExecutionReport | None:
        path = os.path.join(self.settings.data_dir, "runs", run_id, "report.json")
        if not os.path.exists(path):
            return None
        try:
            data = json.load(open(path, "r", encoding="utf-8"))
        except Exception:
            return None
        try:
            steps = []
            for s in data.get("steps") or []:
                step = StepReport(
                    step_id=int(s.get("step_id") or 0),
                    title=s.get("title") or "",
                    status=s.get("status") or "running",
                    verification_passed=bool(s.get("verification_passed") or False),
                    verification_evidence=s.get("verification_evidence") or "",
                )
                steps.append(step)
            return ExecutionReport(
                run_id=data.get("run_id") or run_id,
                trace_id=data.get("trace_id") or "",
                goal=data.get("goal") or "",
                status=data.get("status") or "running",
                started_at=float(data.get("started_at") or 0.0),
                ended_at=float(data.get("ended_at") or 0.0),
                steps=steps,
                files_changed=data.get("files_changed") or [],
                tests_run=data.get("tests_run") or [],
                cost=data.get("cost") or {},
                confidence=float(data.get("confidence") or 0.0),
                next_actions=data.get("next_actions") or [],
                failure_reason=data.get("failure_reason") or "",
            )
        except Exception:
            return None
    def _diff_runs(self, run_a: str, run_b: str) -> str:
        base = os.path.join(self.settings.data_dir, "runs")
        def load_json(path: str):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    return json.load(handle)
            except Exception:
                return {}
        a_plan = load_json(os.path.join(base, run_a, "plan.json"))
        b_plan = load_json(os.path.join(base, run_b, "plan.json"))
        a_rep = load_json(os.path.join(base, run_a, "report.json"))
        b_rep = load_json(os.path.join(base, run_b, "report.json"))
        lines = [
            f"Run A: {run_a}",
            f"Run B: {run_b}",
            "",
            f"Status: {a_rep.get('status')} -> {b_rep.get('status')}",
            f"Steps: {len(a_plan.get('steps', []))} -> {len(b_plan.get('steps', []))}",
            f"Files changed: {len(a_rep.get('files_changed', []))} -> {len(b_rep.get('files_changed', []))}",
        ]
        a_steps = a_plan.get("steps", [])
        b_steps = b_plan.get("steps", [])
        if a_steps and b_steps:
            lines.append("")
            lines.append("Step titles diff:")
            max_len = max(len(a_steps), len(b_steps))
            for i in range(max_len):
                a_title = a_steps[i].get("title") if i < len(a_steps) else "<missing>"
                b_title = b_steps[i].get("title") if i < len(b_steps) else "<missing>"
                if a_title != b_title:
                    lines.append(f"- {i+1}: {a_title} -> {b_title}")
        return "\n".join(lines)

    def _execute_tool(self, name: str, args: str, confirm: bool = False, dry_run: bool = False):

        if not hasattr(self, "_tool_calls_this_task"):
            self._tool_calls_this_task = 0
        max_calls = getattr(self.settings, "max_tool_calls_per_task", 0)
        if max_calls and self._tool_calls_this_task >= max_calls:
            self.metrics.inc("tool_budget_exceeded")
            raise RuntimeError("Tool call budget exceeded for this task")
        self._tool_calls_this_task += 1
        self.metrics.add_tool_call(name)

        run_id = self.current_run.run_id if getattr(self, "current_run", None) else ""
        step_id = getattr(self, "_current_step_id", None)
        spec = self.tools.specs.get(name)
        tool_call = ToolCall(
            name=name,
            args=args,
            risk=spec.risk if spec else "unknown",
            run_id=run_id,
            step_id=step_id,
            timestamp=time.time(),
            dry_run=dry_run,
            trace_id=getattr(self.current_run, "trace_id", "") if getattr(self, "current_run", None) else "",
        )
        try:
            self.workflow.record_tool(name, args, "call")
        except Exception:
            pass
        log_audit(self.memory, "tool_call", tool_call.__dict__, redact=getattr(self, "redact_logs", False))
        if getattr(self, "replay_mode", False):
            dry_run = True
        trace_id = tool_call.trace_id
        with self.otel.span("tool_call", trace_id=trace_id, attributes={"tool": name, "risk": tool_call.risk}):
            return execute_tool(
                self.tools,
                name,
                args,
                self.settings.autonomy_level,
                confirm=confirm,
                dry_run=dry_run,
            )



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
        try:
            self.workflow.record_step(step, "run")
        except Exception:
            pass

        if "pip install" in lowered or "python -m pip install" in lowered:
            allow = os.getenv("AGENTIC_ALLOWED_PIP", "")
            allowed = [p.strip().lower() for p in allow.split(",") if p.strip()]
            if allowed:
                ok = any(pkg in lowered for pkg in allowed)
                if not ok:
                    raise RuntimeError("pip install blocked by allowlist")

        if os.getenv("AGENTIC_DEBATE", "false").lower() in ("1", "true", "yes", "on"):
            risky = any(k in lowered for k in ("delete", "drop", "format", "rm ", "wipe", "destroy"))
            if risky and not self._debate_step(step):
                raise RuntimeError("Debate protocol rejected this action as unsafe.")

        if lowered.startswith("delegate:"):
            rest = step.split(":", 1)[1].strip()
            parts = rest.split(" ", 1)
            if len(parts) < 2:
                raise RuntimeError("delegate requires: delegate:<peer> <task>")
            peer = parts[0].strip()
            task = parts[1].strip()
            payload = {"type": "plan", "text": task}
            self.a2a_net.send(peer, getattr(self, "node_name", "work"), "remote", payload)
            self.log_line(f"Delegated to {peer}: {task}")
            return

        if lowered.startswith("simulate "):
            payload = step[len("simulate "):].strip()
            if not payload or " " not in payload:
                raise RuntimeError("simulate requires: simulate <tool> <args>")
            name, args = payload.split(" ", 1)
            out = self._execute_tool(name.strip(), args.strip(), dry_run=True)
            self.log_line(out)
            return

        if lowered.startswith("alias_add "):
            raw = step[len("alias_add "):].strip()
            if "|" not in raw:
                raise RuntimeError("alias_add requires: alias_add alias | canonical")
            alias, canonical = [s.strip() for s in raw.split("|", 1)]
            try:
                blob = self.memory.get("entity_aliases") or "{}"
                data = json.loads(blob)
            except Exception:
                data = {}
            data[alias.lower()] = canonical
            self.memory.set("entity_aliases", json.dumps(data))
            self.log_line(f"Alias added: {alias} -> {canonical}")
            return

        if lowered.startswith("alias_list"):
            blob = self.memory.get("entity_aliases") or "{}"
            self.log_line(blob)
            return

        if lowered.startswith("fork "):
            run_id = step[len("fork "):].strip()
            if not run_id:
                raise RuntimeError("fork requires: fork <run_id>")
            src = os.path.join(self.settings.data_dir, "runs", run_id)
            if not os.path.isdir(src):
                raise RuntimeError("fork failed: run not found")
            new_id = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
            dst = os.path.join(self.settings.data_dir, "runs", new_id)
            shutil.copytree(src, dst)
            self.log_line(f"Forked run {run_id} -> {new_id}")
        if lowered.startswith("diff_runs "):
            parts = step.split()
            if len(parts) < 3:
                raise RuntimeError("diff_runs requires: diff_runs <run_a> <run_b>")
            out = self._diff_runs(parts[1], parts[2])
            self.log_line(out)
            return

        if lowered.startswith("uia_snapshot"):
            parts = step.split(" ", 1)
            target = parts[1].strip() if len(parts) > 1 else ""
            if not target:
                target = os.path.join(self.settings.data_dir, "uia_snapshot.json")
            saved = write_snapshot(target)
            self.log_line(f"UIA snapshot saved: {saved}")
            return

        if lowered.startswith("som_detect "):
            parts = step.split(" ", 2)
            if len(parts) < 2:
                raise RuntimeError("som_detect requires: som_detect <image_path> [out_path]")
            image_path = parts[1].strip()
            out_path = parts[2].strip() if len(parts) > 2 else image_path + ".som.json"
            endpoint = os.getenv("AGENTIC_SOM_ENDPOINT", "").strip()
            if not endpoint:
                raise RuntimeError("AGENTIC_SOM_ENDPOINT not set")
            saved = som_save(endpoint, image_path, out_path)
            self.log_line(f"SOM saved: {saved}")
            return

        if lowered.startswith("browser_use "):
            task = step[len("browser_use "):].strip()
            if not task:
                raise RuntimeError("browser_use requires a task")
            out = self.browser_use.run(task)
            self.log_line(out)
            return

        if lowered.startswith("workflow_use "):
            rest = step[len("workflow_use "):].strip()
            if not rest:
                raise RuntimeError("workflow_use requires: workflow_use <workflow_path> [goal]")
            parts = rest.split(" ", 1)
            wf = parts[0].strip()
            goal = parts[1].strip() if len(parts) > 1 else ""
            out = self.workflow_use.run(wf, goal=goal)
            self.log_line(out)
            return

        if lowered.startswith("resume "):
            run_id = step[len("resume "):].strip()
            if not run_id:
                raise RuntimeError("resume requires: resume <run_id>")
            plan = self._load_plan_schema_file(run_id)
            if not plan:
                raise RuntimeError("resume failed: plan.json not found")
            report = self._load_report_file(run_id)
            state_path = os.path.join(self.settings.data_dir, "runs", run_id, "state.json")
            start_step = None
            try:
                if os.path.exists(state_path):
                    state = json.load(open(state_path, "r", encoding="utf-8"))
                    cur = state.get("current_step")
                    if cur:
                        start_step = int(cur) + 1
            except Exception:
                start_step = None
            if getattr(self, "current_run", None):
                self.current_run.plan_schema = plan
                self.current_run.report = report
            resumed = self._run_plan_schema(plan, report=report, start_step_id=start_step)
            if getattr(self, "current_run", None):
                self.current_run.report = resumed
            self.log_line(f"Resumed {run_id}: {resumed.status}")
            return

        if lowered.startswith("cancel "):
            run_id = step[len("cancel "):].strip()
            if not run_id:
                raise RuntimeError("cancel requires: cancel <run_id>")
            if getattr(self, "current_run", None) and self.current_run.run_id == run_id:
                self._set_run_status(self.current_run, OrchestratorState.STOPPED.value)
            self.log_line(f"Cancelled {run_id}")
            return

        if lowered.startswith("replay "):
            run_id = step[len("replay "):].strip()
            if not run_id:
                raise RuntimeError("replay requires: replay <run_id>")
            events_path = os.path.join(self.settings.data_dir, "runs", run_id, "events.jsonl")
            if not os.path.exists(events_path):
                raise RuntimeError("replay failed: events.jsonl not found")
            dry_run = os.getenv("AGENTIC_REPLAY_DRY_RUN", "true").lower() in ("1", "true", "yes", "on")
            with open(events_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        event = json.loads(line)
                    except Exception:
                        continue
                    if event.get("event_type") == "tool_call_started":
                        payload = event.get("payload") or {}
                        tool = payload.get("tool")
                        args = payload.get("args")
                        if tool:
                            try:
                                self._execute_tool(tool, json.dumps(args) if isinstance(args, dict) else str(args), dry_run=dry_run)
                            except Exception:
                                continue
            self.log_line(f"Replay complete for {run_id}")
            return

        if lowered.startswith("submit_form "):
            payload = step[len("submit_form "):].strip()
            if not payload:
                raise RuntimeError("submit_form requires json payload")
            try:
                data = json.loads(payload)
            except Exception:
                raise RuntimeError("submit_form payload must be json")
            self.memory.set("last_form", json.dumps(data))
            self.log_line("Form submitted.")
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
                            try:
                                summary = self._agent_chat(f"Summarize new file: {full}")
                                if summary:
                                    self._broadcast_memory_sync({"kind": "file_summary", "content": summary})
                            except Exception:
                                pass

                            count += 1

                        except Exception:

                            continue

                self.log_line(f"Indexed {count} files")

                return

            self.rag.index_file(path)
            try:
                summary = self._agent_chat(f"Summarize new file: {path}")
                if summary:
                    self._broadcast_memory_sync({"kind": "file_summary", "content": summary})
            except Exception:
                pass

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
            if answer:
                self._append_extracted(answer)

            return



        if lowered.startswith("deep_research "):

            question = step[len("deep_research "):].strip()

            output = self.deep_research.run(question)

            self.log_line(output)
            if output:
                self._append_extracted(output)

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

        if lowered.startswith("hybrid_rag "):
            query = step[len("hybrid_rag "):].strip()
            evidence = self.rag.hybrid_search(query, self.graph, limit=7)
            if not evidence:
                self.log_line("No evidence found. Index documents first.")
                return
            ev_text = "\n".join(f"- {e['source']}: {e['text'][:200]}" for e in evidence)
            prompt = (
                "Answer using the hybrid evidence below. "
                "Cite sources by name.\n\nEvidence:\n" + ev_text
            )
            answer = self._agent_chat(prompt)
            self.log_line(answer or "Agent task completed")
            if answer:
                self._append_extracted(answer)
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
            if answer:
                self._append_extracted(answer)
            return

        if lowered.startswith("analysis_plan "):
            question = step[len("analysis_plan "):].strip()
            prompt = ("Create a rigorous analysis plan with steps, data needed, "
                      "verification checks, and expected outputs for: " + question)
            answer = self._agent_chat(prompt)
            self.log_line(answer or "Agent task completed")
            if answer:
                self._append_extracted(answer)
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
            run_id, step_id = self._memory_context()
            self.memory.add_memory(
                "lab_note",
                note,
                ttl_seconds=self.settings.long_memory_ttl,
                run_id=run_id,
                step_id=step_id,
            )
            self.log_line("Lab note saved.")
            return

        if lowered.startswith("a2a_send "):
            payload = step[len("a2a_send "):].strip()
            if not payload or " " not in payload:
                raise RuntimeError("a2a_send requires: a2a_send <peer> <message>")
            peer, message = payload.split(" ", 1)
            sender = getattr(self, "node_name", "work")
            self.a2a_net.send(peer.strip(), sender, "remote", message.strip())
            self.log_line(f"A2A sent to {peer}.")
            return

        if lowered.startswith("a2a_broadcast "):
            message = step[len("a2a_broadcast "):].strip()
            if not message:
                raise RuntimeError("a2a_broadcast requires: a2a_broadcast <message>")
            sender = getattr(self, "node_name", "work")
            self.a2a_net.broadcast(sender, "remote", message.strip())
            self.log_line("A2A broadcast sent.")
            return

        if lowered == "a2a_peers":
            if not self.a2a_net.peers:
                self.log_line("No A2A peers configured.")
                return
            lines = [f"{name} -> {host}:{port}" for name, (host, port) in self.a2a_net.peers.items()]
            self.log_line("\n".join(lines))
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
                AgentRole("Planner", "Create a brief plan.", allowed_tools=["plan", "analyze"]),
                AgentRole("Builder", "Execute the plan or draft the solution.", allowed_tools=["shell", "files", "computer"]),
                AgentRole("Reviewer", "Review for issues and improvements.", allowed_tools=["analyze"]),
            ]
            for role in roles:
                self._log_event("agent_handoff", {"role": role.name, "tools": role.allowed_tools})
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
            if text:
                self._append_extracted(text)

            return

        if lowered.startswith("screenshot "):
            path = step[len("screenshot "):].strip()
            try:
                saved = capture_screenshot(path)
                self.log_line(f"Screenshot saved: {saved}")
                if self.current_run and self.current_run.screenshots_dir:
                    stamp = datetime.utcnow().strftime("%H%M%S")
                    target = os.path.join(self.current_run.screenshots_dir, f"{stamp}-desktop.png")
                    try:
                        exec_files.copy_path(saved, target)
                    except Exception:
                        pass
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

        if lowered.startswith("mcp_resources "):
            provider = step[len("mcp_resources "):].strip()
            try:
                result = self.mcp.list_resources(provider)
                self.log_line(json.dumps(result))
            except Exception as exc:
                self.log_line(f"mcp_resources error: {exc}")
            return

        if lowered == "mcp_providers":
            try:
                result = self.mcp.list_providers()
                self.log_line(json.dumps(result))
            except Exception as exc:
                self.log_line(f"mcp_providers error: {exc}")
            return

        if lowered.startswith("mcp_prompts "):
            provider = step[len("mcp_prompts "):].strip()
            try:
                result = self.mcp.list_prompts(provider)
                self.log_line(json.dumps(result))
            except Exception as exc:
                self.log_line(f"mcp_prompts error: {exc}")
            return

        if lowered.startswith("mcp_tools "):
            provider = step[len("mcp_tools "):].strip()
            try:
                result = self.mcp.list_tools(provider)
                self.log_line(json.dumps(result))
            except Exception as exc:
                self.log_line(f"mcp_tools error: {exc}")
            return

        if lowered.startswith("lsp_find "):
            name = step[len("lsp_find "):].strip()
            root = self.settings.allowed_paths or os.getcwd()
            try:
                results = find_symbol_def(root, name)
                self.log_line(json.dumps(results))
            except Exception as exc:
                self.log_line(f"lsp_find error: {exc}")
            return

        if lowered.startswith("lsp_inherits "):
            base = step[len("lsp_inherits "):].strip()
            root = self.settings.allowed_paths or os.getcwd()
            try:
                results = find_inherits(root, base)
                self.log_line(json.dumps(results))
            except Exception as exc:
                self.log_line(f"lsp_inherits error: {exc}")
            return

        if lowered.startswith("workflow "):
            raw = step[len("workflow "):].strip()
            if "|" not in raw:
                self.log_line("workflow requires: workflow name | payload")
                return
            name, payload = [s.strip() for s in raw.split("|", 1)]
            try:
                output = run_workflow(name, payload, data_dir=self.settings.data_dir)
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

        if lowered.startswith("graph_add "):
            raw = step[len("graph_add "):].strip()
            if "|" not in raw:
                self.log_line("graph_add requires: graph_add name | type")
                return
            name, etype = [s.strip() for s in raw.split("|", 1)]
            entity_id = self.graph.add_entity(name, etype)
            self.log_line(f"Graph entity added: {entity_id}")
            return

        if lowered.startswith("graph_edge "):
            raw = step[len("graph_edge "):].strip()
            if "|" not in raw:
                self.log_line("graph_edge requires: graph_edge src | rel | dst")
                return
            parts = [s.strip() for s in raw.split("|")]
            if len(parts) != 3:
                self.log_line("graph_edge requires: graph_edge src | rel | dst")
                return
            src, rel, dst = parts
            src_id = self.graph.add_entity(src, "concept")
            dst_id = self.graph.add_entity(dst, "concept")
            edge_id = self.graph.add_edge(src_id, rel, dst_id)
            self.log_line(f"Graph edge added: {edge_id}")
            return

        if lowered.startswith("sandbox_run "):
            code = step[len("sandbox_run "):].strip()
            if self.demo_mode:
                self.log_line("sandbox_run blocked in DEMO MODE.")
                return
            try:
                self._terminal_queue.put("[sandbox] running...\n")
                output_buf = io.StringIO()
                with contextlib.redirect_stdout(output_buf), contextlib.redirect_stderr(output_buf):
                    result = run_python(code)
                out_text = output_buf.getvalue()
                if out_text:
                    for line in out_text.splitlines():
                        self._terminal_queue.put(line + "\n")
                self._terminal_queue.put("[sandbox] done\n")
                self.log_line(json.dumps(result))
            except Exception as exc:
                self._terminal_queue.put(f"[sandbox] error: {exc}\n")
                self.log_line(f"sandbox_run error: {exc}")
            return

        if lowered == "fishbowl":
            events = self.memory.get_recent_events(10)
            self.log_line(json.dumps(events))
            return

        if lowered.startswith("step_approval "):
            value = step.split(" ", 1)[1].strip().lower() if " " in step else ""
            if value in ("on", "true", "1"):
                self.step_approval_enabled = True
            elif value in ("off", "false", "0"):
                self.step_approval_enabled = False
            else:
                self.log_line("step_approval requires: step_approval on|off")
                return
            if hasattr(self, "step_approval_var"):
                self.step_approval_var.set(self.step_approval_enabled)
            self.log_line("Step approvals enabled." if self.step_approval_enabled else "Step approvals disabled.")
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

        lowered_instr = instruction.strip().lower()
        if lowered_instr in ("confirm", "approve_once", "approve_always", "approve_never"):

            pending = self.memory.get("pending_action")

            if not pending:

                return "No pending action to confirm."

            payload = json.loads(pending)

            self.memory.set("pending_action", "")

            if payload.get("type") == "tool":

                name = payload.get("name")

                args = payload.get("args")

                if lowered_instr == "approve_always" and name:
                    self.memory.set(f"allow_tool:{name}", "true")
                if lowered_instr == "approve_never" and name:
                    self.memory.set(f"deny_tool:{name}", "true")
                    return f"Denied tool {name}."
                if self._tool_risk(name) == "destructive":
                    self._issue_token(name)
                out = self._execute_tool(name, args, confirm=True)
                try:
                    pending_step = self.memory.get("pending_step_id")
                    pending_run = self.memory.get("pending_plan_run_id")
                    if pending_step and pending_run and getattr(self, "current_run", None):
                        if self.current_run.run_id == pending_run and getattr(self.current_run, "plan_schema", None):
                            start_step = int(pending_step) + 1
                            self.memory.set("pending_step_id", "")
                            self.memory.set("pending_plan_run_id", "")
                            report = self._run_plan_schema(self.current_run.plan_schema, report=self.current_run.report, start_step_id=start_step)
                            self.current_run.report = report
                except Exception:
                    pass

                return out

            if payload.get("type") == "cost":
                try:
                    pending_step = self.memory.get("pending_step_id")
                    pending_run = self.memory.get("pending_plan_run_id")
                    if pending_step and pending_run and getattr(self, "current_run", None):
                        if self.current_run.run_id == pending_run and getattr(self.current_run, "plan_schema", None):
                            start_step = int(pending_step)
                            self.memory.set("pending_step_id", "")
                            self.memory.set("pending_plan_run_id", "")
                            report = self._run_plan_schema(self.current_run.plan_schema, report=self.current_run.report, start_step_id=start_step)
                            self.current_run.report = report
                except Exception:
                    pass
                return "Cost approved."

            return "Nothing to confirm."

        plan_schema = None
        if os.getenv("AGENTIC_LLM_PLANNER", "true").lower() in ("1", "true", "yes", "on"):
            plan_schema = self._plan_with_llm(instruction)
        plan = self.planner.plan(instruction) if plan_schema is None else []
        if plan_schema is None and plan:
            max_steps = getattr(self.settings, "max_plan_steps", 0)
            if max_steps and len(plan) > max_steps:
                self._log_event(
                    "plan_guard",
                    {
                        "limit": max_steps,
                        "original_steps": len(plan),
                    },
                )
                plan = plan[:max_steps]
                self.log_line(f"Plan truncated to {max_steps} steps due to budget.")

            run_id = getattr(self.current_run, "run_id", datetime.utcnow().strftime("%Y-%m-%d_%H%M%S"))
            trace_id = getattr(self.current_run, "trace_id", str(uuid.uuid4()))
            steps = [self._step_to_schema(i + 1, s) for i, s in enumerate(plan)]
            plan_schema = PlanSchema(
                run_id=run_id,
                trace_id=trace_id,
                goal=instruction,
                success_criteria=["No errors and user intent satisfied"],
                steps=steps,
                constraints={"demo_mode": self.demo_mode},
                budget=Budget(
                    max_steps=getattr(self.settings, "max_plan_steps", 20) or 20,
                    max_tool_calls=int(getattr(self.settings, "max_tool_calls_per_task", 50) or 50),
                    max_seconds=900,
                ),
                created_at=time.time(),
                model=getattr(self.settings, "openai_model", ""),
            )
        if plan_schema:
            if getattr(self, "current_run", None):
                if not plan_schema.run_id:
                    plan_schema.run_id = self.current_run.run_id
                if not plan_schema.trace_id:
                    plan_schema.trace_id = self.current_run.trace_id
                self.current_run.plan_schema = plan_schema

            self._log_event(
                "plan_created",
                {
                    "goal": plan_schema.goal,
                    "steps": [
                        {
                            "step_id": st.step_id,
                            "title": st.title,
                            "tool": st.tool,
                            "risk": st.risk,
                            "confirm": st.requires_confirmation,
                        }
                        for st in plan_schema.steps
                    ],
                    "budget": plan_schema.budget.__dict__,
                },
            )

            report = self._run_plan_schema(plan_schema)
            if getattr(self, "current_run", None):
                self.current_run.report = report
                self._write_run_artifacts(plan_schema, report)

            if report.status in ("failed", "error"):
                # One reflection pass: replan based on failure evidence.
                reflect_prompt = self._build_reflection_prompt(instruction, plan_schema, report)
                reflect_plan = self.planner.plan(reflect_prompt)
                if reflect_plan:
                    steps = [self._step_to_schema(i + 1, s) for i, s in enumerate(reflect_plan)]
                    plan_schema = PlanSchema(
                        run_id=plan_schema.run_id,
                        trace_id=plan_schema.trace_id,
                        goal=reflect_prompt,
                        success_criteria=["No errors and user intent satisfied"],
                        steps=steps,
                        constraints={"demo_mode": self.demo_mode},
                        budget=plan_schema.budget,
                        created_at=time.time(),
                        model=getattr(self.settings, "openai_model", ""),
                    )
                    report = self._run_plan_schema(plan_schema)
                    if getattr(self, "current_run", None):
                        self.current_run.report = report
                        self._write_run_artifacts(plan_schema, report)

            return "Done." if report.status == "succeeded" else f"Run ended: {report.status}"

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
        self._attach_network_logger()

    def _attach_network_logger(self) -> None:
        if not self.page:
            return
        enabled = os.getenv("AGENTIC_NET_LOG", "false").lower() in ("1", "true", "yes", "on")
        if not enabled:
            return
        log_path = os.path.join(self.settings.data_dir, "net_log.jsonl")

        def _handler(response):
            try:
                headers = response.headers or {}
                ctype = headers.get("content-type", "")
                if "application/json" not in ctype:
                    return
                data = response.json()
                payload = {
                    "ts": time.time(),
                    "url": response.url,
                    "status": response.status,
                    "method": response.request.method,
                    "data": data,
                }
                with open(log_path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload) + "\n")
            except Exception:
                return

        try:
            self.page.on("response", _handler)
        except Exception:
            return



    def cleanup(self):

        try:

            self._memory_prune_stop.set()
            try:
                self.a2a_net.stop()
            except Exception:
                pass
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

        run = self._create_task_run(cmd)
        self.current_run = run
        self._set_plan_text(self._format_plan(run.intent, run.plan_steps))
        self._reset_action_cards(run.plan_steps)
        self.approve_btn.configure(state=tk.NORMAL)
        self.log_line("Plan ready. Review and click Approve & Run.")



    def _execute(self, cmd: str):

        try:

            if not self.current_run or not self.current_run.approved:
                self.log_line("Execution blocked: approve the plan first.")
                return

            self.metrics.inc("tasks_total")

            start = time.time()

            lowered = cmd.lower().strip()

            self._tool_calls_this_task = 0

            if not hasattr(self, "purpose"):
                self.purpose = ""
            if not hasattr(self, "redact_logs"):
                self.redact_logs = False

            if "remember" in lowered or "note this" in lowered:

                run_id, step_id = self._memory_context()
                self.memory.add_memory(
                    "long",
                    cmd,
                    ttl_seconds=self.settings.long_memory_ttl,
                    run_id=run_id,
                    step_id=step_id,
                )

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

            if lowered.startswith("workflow_record"):
                parts = cmd.split(" ", 2)
                action = parts[1].strip().lower() if len(parts) > 1 else ""
                if action == "start" and len(parts) > 2:
                    name = parts[2].strip()
                    self.workflow.start(name)
                    self.log_line(f"Workflow recording started: {name}")
                elif action == "stop":
                    name = self.workflow.stop()
                    self.log_line(f"Workflow saved: {name}" if name else "No active workflow.")
                elif action == "list":
                    items = self.workflow.list()
                    self.log_line("Workflows: " + (", ".join(items) if items else "none"))
                else:
                    self.log_line("Usage: workflow_record start <name> | stop | list")
                return

            if lowered.startswith("workflow_run "):
                name = cmd.split(" ", 1)[1].strip()
                data = self.workflow.load(name)
                if not data:
                    self.log_line(f"Workflow not found: {name}")
                    return
                for item in data.get("steps", []):
                    if item.get("type") == "step":
                        try:
                            self._execute_step(item.get("command", ""))
                        except Exception as exc:
                            self.log_line(f"Workflow step failed: {exc}")
                            break
                self.log_line(f"Workflow run complete: {name}")
                return

            if lowered.startswith("vla"):
                parts = cmd.split(" ", 2)
                action = parts[1].strip().lower() if len(parts) > 1 else ""
                if action in ("start", "on"):
                    if len(parts) > 2:
                        self.vla_driver.set_goal(parts[2])
                    self.vla_driver.start()
                elif action in ("stop", "off"):
                    self.vla_driver.stop()
                elif action == "pause":
                    self.vla_driver.pause()
                elif action == "resume":
                    self.vla_driver.resume()
                elif action == "goal" and len(parts) > 2:
                    self.vla_driver.set_goal(parts[2])
                elif action in ("status", ""):
                    self.log_line(json.dumps(self.vla_driver.status(), indent=2))
                else:
                    self.log_line("Usage: vla start|stop|pause|resume|goal <text>|status")
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
                manager = AgentRole("Manager", "Plan only. Assign tasks to workers.", allowed_tools=[])
                workers = [
                    AgentRole("Builder", "Execute assigned work only.", allowed_tools=["files", "sandbox", "browser", "computer"]),
                    AgentRole("Reviewer", "Review the output only; no tool use.", allowed_tools=[]),
                    AgentRole("Security", "Check for security risks; no tool use.", allowed_tools=[]),
                    AgentRole("QA", "Validate correctness and edge cases.", allowed_tools=[]),
                ]
                orchestrator = ManagerWorkerOrchestrator(self._agent_chat)
                output = orchestrator.run(manager, workers, task)
                for role in [manager] + workers:
                    self._log_event("agent_handoff", {"role": role.name, "tools": role.allowed_tools})
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
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/favicon.ico":

                self._send(HTTPStatus.NO_CONTENT, b"", "image/x-icon")

                return

            if path == "/health":

                self._send(HTTPStatus.OK, b"ok", "text/plain")

                return

            if path == "/api/metrics":
                body = json.dumps(app.metrics.snapshot()).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/trace":
                body = json.dumps(app.memory.recent_events(50)).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/jobs":
                body = json.dumps(app.jobs.list(20)).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/models":
                body = json.dumps(app.memory.model_summary(20)).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/a2a":
                body = json.dumps(app.a2a.recent(20)).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/tools":
                specs = []
                try:
                    for name, spec in app.tools.specs.items():
                        specs.append(
                            {
                                "name": name,
                                "risk": getattr(spec, "risk", ""),
                                "arg_hint": getattr(spec, "arg_hint", ""),
                                "splitter": getattr(spec, "splitter", ""),
                            }
                        )
                except Exception:
                    specs = []
                body = json.dumps(specs).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/config":
                try:
                    data = app.settings.__dict__
                except Exception:
                    data = {}
                body = json.dumps(data).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/log_tail":
                limit = 200
                try:
                    limit = int(self.headers.get("X-Lines", "200"))
                except Exception:
                    limit = 200
                lines = []
                try:
                    if os.path.exists(app.settings.log_file):
                        with open(app.settings.log_file, "r", encoding="utf-8", errors="ignore") as handle:
                            lines = handle.read().splitlines()[-limit:]
                except Exception:
                    lines = []
                body = json.dumps({"lines": lines}).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/vla_latest":
                img = ""
                try:
                    vla_dir = os.path.join(app.settings.data_dir, "vla")
                    if os.path.isdir(vla_dir):
                        files = [f for f in os.listdir(vla_dir) if f.endswith(".png")]
                        if files:
                            files.sort(key=lambda f: os.path.getmtime(os.path.join(vla_dir, f)))
                            latest = os.path.join(vla_dir, files[-1])
                            with open(latest, "rb") as handle:
                                b64 = base64.b64encode(handle.read()).decode("ascii")
                            img = f"data:image/png;base64,{b64}"
                except Exception:
                    img = ""
                body = json.dumps({"image": img}).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/graph":
                nodes = []
                edges = {}
                try:
                    nodes.append({"id": app.node_name, "label": app.node_name, "type": "local"})
                    for peer in app.a2a_net.peers:
                        nodes.append({"id": peer, "label": peer, "type": "peer"})
                    msgs = app.a2a.recent(200)
                    for m in msgs:
                        s = m.get("sender")
                        r = m.get("receiver")
                        key = f"{s}->{r}"
                        edges[key] = edges.get(key, 0) + 1
                except Exception:
                    pass
                payload = {
                    "nodes": nodes,
                    "edges": [{"source": k.split("->")[0], "target": k.split("->")[1], "count": v} for k, v in edges.items()],
                }
                body = json.dumps(payload).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/rag_sources":
                sources = []
                try:
                    sources = app.rag.list_sources()
                except Exception:
                    sources = []
                body = json.dumps(sources).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/roles":
                roles = []
                try:
                    if hasattr(app.team, "roles"):
                        roles = [{"id": r.name, "label": r.label} for r in app.team.roles]
                except Exception:
                    roles = []
                body = json.dumps(roles).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/pending_runs":
                pending = []
                try:
                    for run_id, run in app.pending_runs.items():
                        steps = []
                        for step in getattr(run, "plan_steps", []) or []:
                            if isinstance(step, dict):
                                steps.append(step)
                            else:
                                steps.append({
                                    "step": getattr(step, "step", 0),
                                    "action": getattr(step, "action", ""),
                                    "target": getattr(step, "target", ""),
                                    "value": getattr(step, "value", ""),
                                    "reason": getattr(step, "reason", ""),
                                    "command": getattr(step, "command", ""),
                                })
                        pending.append({
                            "run_id": run_id,
                            "intent": getattr(run, "intent", ""),
                            "plan_steps": steps,
                        })
                except Exception:
                    pending = []
                body = json.dumps(pending).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/user_profile":
                profile = {}
                try:
                    profile = app.memory.get_user_profile("default")
                except Exception:
                    profile = {}
                body = json.dumps(profile).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/runs":
                runs = []
                try:
                    base = os.path.join(app.settings.data_dir, "runs")
                    runs = [summarize_run(os.path.join(base, d)) for d in list_run_dirs(base)]
                except Exception:
                    runs = []
                body = json.dumps(runs).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/api/run_diff":
                qs = parse_qs(parsed.query or "")
                run_a = (qs.get("run_a") or [""])[0]
                run_b = (qs.get("run_b") or [""])[0]
                if not run_a or not run_b:
                    self._send(HTTPStatus.BAD_REQUEST, b"missing run ids", "text/plain")
                    return
                diff_text = app._diff_runs(run_a, run_b)
                body = json.dumps({"diff": diff_text}).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path.startswith("/assets/"):
                try:
                    rel_path = path.lstrip("/")
                    ui_root = os.path.abspath(os.path.join(app.settings.data_dir, "..", "ui", "control_plane"))
                    asset_path = os.path.abspath(os.path.join(ui_root, rel_path))
                    if not asset_path.startswith(ui_root):
                        self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")
                        return
                    if not os.path.exists(asset_path):
                        self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")
                        return
                    ext = os.path.splitext(asset_path)[1].lower()
                    content_type = {
                        ".js": "text/javascript",
                        ".css": "text/css",
                        ".map": "application/json",
                        ".svg": "image/svg+xml",
                        ".png": "image/png",
                        ".ico": "image/x-icon",
                    }.get(ext, "application/octet-stream")
                    with open(asset_path, "rb") as handle:
                        data = handle.read()
                    self._send(HTTPStatus.OK, data, content_type)
                except Exception:
                    self._send(HTTPStatus.INTERNAL_SERVER_ERROR, b"asset error", "text/plain")
                return
            if path == "/api/cockpit":
                payload = {
                    "metrics": app.metrics.snapshot(),
                    "a2a": app.a2a.recent(20),
                    "events": app.memory.recent_events(50),
                }
                body = json.dumps(payload).encode("utf-8")
                self._send(HTTPStatus.OK, body, "application/json")
                return
            if path == "/dashboard":
                try:
                    ui_path = os.path.join(app.settings.data_dir, "..", "ui", "control_plane", "index.html")
                    ui_path = os.path.abspath(ui_path)
                    with open(ui_path, "r", encoding="utf-8") as handle:
                        html = handle.read()
                except Exception:
                    html = "<h2>Control Plane UI not found.</h2>"
                self._send(HTTPStatus.OK, html.encode("utf-8"), "text/html")
                return
            if path != "/":

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

    <button onclick="sendCmd()">Plan</button>
    <button onclick="approve()">Approve & Run</button>
    <button onclick="approveStep()">Approve Step</button>

    <pre id="plan"></pre>
    <pre id="out"></pre>

    <pre id="metrics"></pre>

    <script>

      let lastRunId = "";
      async function sendCmd() {

        const cmd = document.getElementById('cmd').value;

        const res = await fetch('/api/command', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ command: cmd })

        });

        const data = await res.json();
        lastRunId = data.run_id || '';
        document.getElementById('plan').textContent = data.plan || '';

        await refreshMetrics();

      }

      async function approve() {
        if (!lastRunId) return;
        const res = await fetch('/api/approve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run_id: lastRunId })
        });
        const data = await res.json();
        document.getElementById('out').textContent = JSON.stringify(data, null, 2);
        await refreshMetrics();
      }

      async function approveStep() {
        const res = await fetch('/api/approve_step', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
        const data = await res.json();
        document.getElementById('out').textContent = JSON.stringify(data, null, 2);
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

            if self.path not in ("/api/command", "/api/approve", "/api/approve_step", "/api/config", "/api/memory_search"):

                self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")

                return

            try:

                length = int(self.headers.get("Content-Length", "0"))

                raw = self.rfile.read(length).decode("utf-8", errors="ignore")

                payload = json.loads(raw) if raw else {}

                command = (payload.get("command") or "").strip()

                if self.path == "/api/config":
                    updates = payload.get("updates") or {}
                    if not isinstance(updates, dict):
                        self._send(HTTPStatus.BAD_REQUEST, b"updates must be object", "text/plain")
                        return
                    applied = {}
                    for key, value in updates.items():
                        if not isinstance(key, str):
                            continue
                        if not hasattr(app.settings, key):
                            continue
                        setattr(app.settings, key, value)
                        applied[key] = value
                    body = json.dumps({"status": "applied", "applied": applied}).encode("utf-8")
                    self._send(HTTPStatus.OK, body, "application/json")
                    return
                if self.path == "/api/memory_search":
                    query = (payload.get("query") or "").strip()
                    if not query:
                        self._send(HTTPStatus.BAD_REQUEST, b"missing query", "text/plain")
                        return
                    try:
                        results = app.memory.search_memory(query, limit=8, scope="shared")
                    except Exception:
                        results = []
                    body = json.dumps(results).encode("utf-8")
                    self._send(HTTPStatus.OK, body, "application/json")
                    return

                if self.path == "/api/approve":
                    run_id = (payload.get("run_id") or "").strip()
                    run = app.pending_runs.get(run_id)
                    if not run:
                        self._send(HTTPStatus.BAD_REQUEST, b"missing run_id", "text/plain")
                        return
                    run.approved = True
                    app.current_run = run
                    app.task_queue.enqueue(lambda: app._run_task_run(run))
                    body = json.dumps({"status": "queued", "run_id": run_id}).encode("utf-8")
                    self._send(HTTPStatus.OK, body, "application/json")
                    return
                if self.path == "/api/approve_step":
                    app.step_approval_event.set()
                    app.waiting_for_step = False
                    body = json.dumps({"status": "approved"}).encode("utf-8")
                    self._send(HTTPStatus.OK, body, "application/json")
                    return

                if not command:

                    self._send(HTTPStatus.BAD_REQUEST, b"missing command", "text/plain")

                    return

                run = app._create_task_run(command)
                app.current_run = run
                plan_text = app._format_plan(run.intent, run.plan_steps)
                body = json.dumps({"run_id": run.run_id, "plan": plan_text}).encode("utf-8")

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





def _auto_launch_local_dual_peers(settings) -> bool:
    enabled = os.getenv("AGENTIC_LOCAL_DUAL_PEERS", "false").lower() in ("1", "true", "yes", "on")
    if not enabled:
        return False
    node_name = os.getenv("AGENTIC_NODE_NAME", "") or getattr(settings, "node_name", "")
    if node_name and node_name not in ("work",):
        return False
    hidden = os.getenv("AGENTIC_LOCAL_DUAL_PEERS_HIDDEN", "false").lower() in ("1", "true", "yes", "on")
    script_name = "launch_local_dual_peers_hidden.ps1" if hidden else "launch_local_dual_peers.ps1"
    script_path = os.path.join(os.getcwd(), "scripts", script_name)
    if not os.path.exists(script_path):
        return False
    try:
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hidden else 0,
        )
        return True
    except Exception:
        return False



def main():

    settings = get_settings()
    if _auto_launch_local_dual_peers(settings):
        return

    if os.getenv("AGENTIC_UI", "nicegui").lower() == "nicegui":
        try:
            from dashboard import run_dashboard
            run_dashboard()
            return
        except Exception:
            pass


    setup_logging(settings.log_file)

    root = tk.Tk()
    engine = AgentEngine(settings)
    app = AgentApp(root, settings, engine)

    _start_web_server(app)

    app.log_line("OpenAI key loaded: " + ("yes" if os.getenv("OPENAI_API_KEY") else "no"))



    def on_close():

        app.cleanup()

        root.destroy()



    root.protocol("WM_DELETE_WINDOW", on_close)

    root.mainloop()





if __name__ == "__main__":

    main()

