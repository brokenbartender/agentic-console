import threading
import time
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

import tkinter as tk

from config import get_settings
from engine import AgentEngine
from orchestrator.state import OrchestratorState
from app import AgentApp, TaskRun, PlanStep
from tools.registry import UnifiedToolRegistry
from core.schemas import (
    PlanSchema,
    PlanStepSchema,
    ExecutionReport,
    StepReport,
    ToolResult,
    Budget,
)
from agents import PlannerAgent, RetrieverAgent, VerifierAgent
from core.run_state import list_run_dirs, summarize_run, load_json


class _DummyWidget:
    def configure(self, **_kwargs):
        return


class HeadlessApp(AgentApp):
    def _build_ui(self):
        self.input_var = tk.StringVar()
        self.advanced_var = tk.BooleanVar(value=False)
        self.step_approval_var = tk.BooleanVar(value=False)
        self.approve_btn = _DummyWidget()
        self.plan_text = None
        self.action_cards = []

    def _set_plan_text(self, _text: str) -> None:
        return

    def _reset_action_cards(self, _items: List) -> None:
        return

    def log_line(self, message):
        if hasattr(self, "_controller") and self._controller:
            self._controller.log(message, type="info")
        else:
            return

    def _log_event(self, event_type: str, payload) -> None:
        if hasattr(self, "_controller") and self._controller:
            self._controller.log(f"{event_type}", type="event", details=payload)
        return


class HeadlessController:
    """
    The 'Brain' of the operation.
    Manages the Agent Loop without any UI dependencies.
    """
    def __init__(self) -> None:
        self.settings = get_settings()
        self.engine = AgentEngine(self.settings)
        self.memory = self.engine.memory
        self.activity_log: List[Dict] = []

        self.root = tk.Tk()
        self.root.withdraw()
        self.app = HeadlessApp(self.root, self.settings, self.engine)
        self.app._controller = self
        self._tools = UnifiedToolRegistry.from_legacy(self.app)

        self.planner = PlannerAgent(list(self.app.tools.tools.keys()))
        self.retriever = RetrieverAgent(self.memory)
        self.verifier = VerifierAgent()

        self.current_run: Optional[TaskRun] = None
        self.pending_runs: Dict[str, TaskRun] = {}

    def log(self, message: str, type: str = "info", details=None) -> None:
        event = {
            "ts": datetime.now().strftime("%H:%M:%S"),
            "message": message,
            "type": type,
            "details": details,
        }
        self.activity_log.append(event)
        if len(self.activity_log) > 500:
            self.activity_log.pop(0)

    def _sync_from_app(self) -> None:
        self.current_run = self.app.current_run
        self.pending_runs = dict(self.app.pending_runs)

    def _tool_info(self) -> List[Dict[str, Any]]:
        return self._tools.list()

    def _plan_with_llm(self, user_intent: str) -> Optional[PlanSchema]:
        tools = self._tool_info()
        prompt = (
            "You are the Planner. Return ONLY JSON for PlanSchema. "
            "Include goal, success_criteria, steps with tool and args. "
            "Available tools:\n" + json.dumps(tools, indent=2)
        )
        try:
            raw = self.app._agent_chat(prompt + "\nUser goal: " + user_intent)
        except Exception:
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except Exception:
            return None
        try:
            steps = []
            for idx, s in enumerate(data.get("steps") or [], 1):
                tool = (s.get("tool") or "").strip()
                tool_meta = next((t for t in tools if t["name"] == tool), None)
                steps.append(
                    PlanStepSchema(
                        step_id=int(s.get("step_id") or idx),
                        title=s.get("title") or tool or f"step {idx}",
                        intent=s.get("intent") or "",
                        tool=tool,
                        args=s.get("args") or {},
                        risk=(tool_meta or {}).get("risk_level", "safe"),
                        requires_confirmation=bool((tool_meta or {}).get("requires_approval", False)),
                        max_attempts=int(s.get("max_attempts") or 2),
                        timeout_s=int(s.get("timeout_s") or 90),
                        success_check=s.get("success_check") or "",
                    )
                )
            if not steps:
                return None
            return PlanSchema(
                run_id=data.get("run_id") or datetime.utcnow().strftime("%Y-%m-%d_%H%M%S"),
                trace_id=data.get("trace_id") or "",
                goal=data.get("goal") or user_intent,
                success_criteria=data.get("success_criteria") or ["Task completed without errors"],
                steps=steps,
                assumptions=data.get("assumptions") or [],
                constraints=data.get("constraints") or {},
                budget=Budget(**(data.get("budget") or {})),
                created_at=time.time(),
                model=data.get("model") or "",
            )
        except Exception:
            return None

    def _plan_fallback(self, user_intent: str) -> PlanSchema:
        steps_raw = self.planner.plan(user_intent) or [user_intent]
        steps = []
        for idx, raw in enumerate(steps_raw, 1):
            tool = raw.split(" ", 1)[0].strip()
            tool_meta = next((t for t in self._tool_info() if t["name"] == tool), None)
            steps.append(
                PlanStepSchema(
                    step_id=idx,
                    title=raw,
                    intent=raw,
                    tool=tool if tool_meta else "",
                    args={"command": raw},
                    risk=(tool_meta or {}).get("risk_level", "safe"),
                    requires_confirmation=bool((tool_meta or {}).get("requires_approval", False)),
                )
            )
        return PlanSchema(
            run_id=datetime.utcnow().strftime("%Y-%m-%d_%H%M%S"),
            trace_id="",
            goal=user_intent,
            success_criteria=["Task completed without errors"],
            steps=steps,
            budget=Budget(),
            created_at=time.time(),
        )

    def _build_plan_schema(self, user_intent: str) -> PlanSchema:
        plan = self._plan_with_llm(user_intent)
        if plan:
            return plan
        return self._plan_fallback(user_intent)

    def plan_task(self, user_intent: str) -> TaskRun:
        self.log(f"Planning: {user_intent}", type="agent")
        plan_schema = self._build_plan_schema(user_intent)
        run = self.app._create_task_run(user_intent)
        run.plan_schema = plan_schema
        run.plan_steps = [
            PlanStep(
                step=s.step_id,
                action=s.tool or "execute",
                target=s.intent,
                value="",
                reason=s.intent or "planned",
                command=s.args.get("command") or f"{s.tool} {json.dumps(s.args)}".strip(),
            )
            for s in plan_schema.steps
        ]
        self.current_run = run
        self.pending_runs[run.run_id] = run
        self.log(f"Plan created with {len(run.plan_steps)} steps.", type="success")
        return run

    def approve_run(self, run_id: str) -> None:
        run = self.pending_runs.get(run_id)
        if not run:
            return
        run.approved = True
        self.app._set_run_status(run, OrchestratorState.APPROVED.value)
        self.memory.update_task_run(run.run_id, approved=True)
        self.log(f"Run {run_id} approved.", type="success")
        threading.Thread(target=self._execution_loop, args=(run,), daemon=True).start()

    def reject_run(self, run_id: str) -> None:
        run = self.pending_runs.get(run_id)
        if not run:
            return
        self.app._set_run_status(run, OrchestratorState.STOPPED.value)
        self.log(f"Run {run_id} rejected.", type="warning")

    def _execute_plan(self, run: TaskRun) -> ExecutionReport:
        plan = run.plan_schema
        if not plan:
            return ExecutionReport(run_id=run.run_id, trace_id=run.trace_id, goal=run.command, status="failed", started_at=time.time(), ended_at=time.time(), failure_reason="missing plan")
        report = ExecutionReport(
            run_id=run.run_id,
            trace_id=run.trace_id,
            goal=plan.goal,
            status="running",
            started_at=time.time(),
            ended_at=0.0,
        )
        tool_calls = 0
        for step in plan.steps:
            step_report = StepReport(step_id=step.step_id, title=step.title, status="running")
            report.steps.append(step_report)
            for attempt in range(1, step.max_attempts + 1):
                step_report.attempts = attempt
                tool_calls += 1
                if tool_calls > plan.budget.max_tool_calls:
                    step_report.status = "failed"
                    report.status = "failed"
                    report.failure_reason = "Budget exceeded: max_tool_calls"
                    break
                command = step.args.get("command")
                if not command:
                    if step.tool:
                        command = step.tool + " " + (step.args.get("raw") or "")
                    else:
                        command = step.intent
                t0 = time.time()
                ok = False
                err = ""
                out_preview = ""
                try:
                    # Observe before UI actions if using computer tool.
                    if step.tool == "computer":
                        try:
                            self.app._execute_tool("computer", json.dumps({"mode": "observe", "out_dir": os.path.join(self.settings.data_dir, "runs", run.run_id)}))
                        except Exception:
                            pass
                    self.app._execute_step(command)
                    if step.tool == "computer":
                        try:
                            self.app._execute_tool("computer", json.dumps({"mode": "observe", "out_dir": os.path.join(self.settings.data_dir, "runs", run.run_id)}))
                        except Exception:
                            pass
                    ok = True
                    out_preview = f"{command}"
                except Exception as exc:
                    ok = False
                    err = str(exc)
                t1 = time.time()
                tr = ToolResult(
                    name=step.tool or "command",
                    args=step.args,
                    risk=step.risk,
                    ok=ok,
                    started_at=t0,
                    ended_at=t1,
                    output_preview=out_preview[:2000],
                    error=err[:2000],
                )
                step_report.tool_results.append(tr)
                if ok:
                    step_report.status = "succeeded"
                    break
            if step_report.status != "succeeded":
                report.status = "failed"
                report.failure_reason = f"Step {step.step_id} failed"
                break
            step_report.status = "succeeded"
        if report.status == "running":
            report.status = "succeeded"
        report.ended_at = time.time()
        return report

    def _execution_loop(self, run: TaskRun) -> None:
        self.log("Starting execution...", type="info")
        report = self._execute_plan(run)
        run.report = report
        if report.status in ("failed", "error"):
            self.app._set_run_status(run, OrchestratorState.ERROR.value)
        else:
            self.app._set_run_status(run, OrchestratorState.COMPLETE.value)
        self._sync_from_app()

    def run_two_agent(self, task: str, max_loops: int = 2) -> ExecutionReport:
        retr = self.retriever.retrieve(task)
        context = f"Context:\n{retr}\n" if retr else ""
        run = self.plan_task(context + task)
        report = self._execute_plan(run)
        if report.status != "succeeded" and max_loops > 1:
            # Replan once using failure reason
            replan_intent = f"Fix failures: {report.failure_reason}\nOriginal task: {task}"
            run = self.plan_task(replan_intent)
            report = self._execute_plan(run)
        return report

    def get_run_status(self, run_id: str) -> str:
        run = self.pending_runs.get(run_id) or self.current_run
        if not run:
            return "unknown"
        return run.status

    def build_summary(self, run_id: str) -> str:
        run = self.pending_runs.get(run_id) or self.current_run
        if not run:
            return "No run found."
        lines = [
            f"Run {run.run_id}",
            f"Status: {run.status}",
            "",
            "What I did:",
        ]
        for step in run.plan_steps:
            lines.append(f"- {step.step}. {step.action} → {step.target} ({step.reason})")
        return "\n".join(lines)

    def describe_agent(self) -> Dict:
        roles = []
        try:
            if hasattr(self.app, "team") and hasattr(self.app.team, "roles"):
                roles = [r.name for r in self.app.team.roles]
        except Exception:
            roles = []
        return {
            "role": "primary",
            "goals": ["Execute user tasks safely"],
            "tools": self._tools.list(),
            "memory": {"shared": True},
            "policies": {"autonomy": self.settings.autonomy_level},
            "status": {
                "current_run": self.current_run.run_id if self.current_run else None,
                "pending": len(self.pending_runs),
                "roles": roles,
            },
        }

    def memory_snapshot(self) -> Dict:
        profile = self.memory.get_user_profile("default")
        return {"profile": profile}

    def search_memory(self, query: str):
        return self.memory.search_memory(query, limit=8, scope="shared")

    def pin_memory(self, text: str) -> None:
        self.memory.add_memory("pin", text, ttl_seconds=self.settings.long_memory_ttl)

    def clear_memory(self) -> None:
        self.memory.update_user_profile({}, user_id="default")

    def edit_profile(self, key: str, value: str) -> None:
        self.memory.update_user_profile({key: value}, user_id="default")

    def list_workflows(self) -> List[str]:
        wf_dir = os.path.join(os.getcwd(), "workflows")
        if not os.path.isdir(wf_dir):
            return []
        return [os.path.join(wf_dir, name) for name in os.listdir(wf_dir) if name.endswith(".py")]

    def run_workflow(self, path: str, goal: str = "") -> str:
        try:
            return self.app.workflow_use.run(path, goal=goal)
        except Exception as exc:
            return f"workflow error: {exc}"

    def save_workflow(self, name: str) -> str:
        run = self.current_run
        if not run or not getattr(run, "actions_path", ""):
            return "No run actions to save."
        wf_dir = os.path.join(os.getcwd(), "workflows")
        os.makedirs(wf_dir, exist_ok=True)
        target = os.path.join(wf_dir, f"{name}.jsonl")
        try:
            with open(run.actions_path, "r", encoding="utf-8") as src, open(target, "w", encoding="utf-8") as dst:
                dst.write(src.read())
            return f"Saved workflow {target}"
        except Exception as exc:
            return f"workflow save error: {exc}"

    def set_step_approval(self, enabled: bool) -> None:
        self.app.step_approval_enabled = bool(enabled)
        try:
            if hasattr(self.app, "step_approval_var"):
                self.app.step_approval_var.set(self.app.step_approval_enabled)
        except Exception:
            pass

    def save_canvas(self, text: str) -> str:
        run = self.current_run
        if not run:
            return ""
        base = os.path.join(self.settings.data_dir, "runs", run.run_id)
        os.makedirs(base, exist_ok=True)
        path = os.path.join(base, "canvas.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text or "")
        return path

    def load_canvas(self) -> str:
        run = self.current_run
        if not run:
            return ""
        path = os.path.join(self.settings.data_dir, "runs", run.run_id, "canvas.md")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return handle.read()
        except Exception:
            return ""

    def list_runs(self) -> List[Dict[str, Any]]:
        base = os.path.join(self.settings.data_dir, "runs")
        return [summarize_run(os.path.join(base, d)) for d in list_run_dirs(base)]

    def load_run_goal(self, run_id: str) -> str:
        base = os.path.join(self.settings.data_dir, "runs", run_id)
        plan = load_json(os.path.join(base, "plan.json"))
        return plan.get("goal", "")

    def stop(self) -> None:
        try:
            self.app.cleanup()
        finally:
            self.root.destroy()


if __name__ == "__main__":
    ctrl = HeadlessController()
    print("Headless controller running.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        ctrl.stop()
