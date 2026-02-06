import threading
import time
import os
from datetime import datetime
from typing import Dict, List, Optional

import tkinter as tk

from config import get_settings
from engine import AgentEngine
from orchestrator.state import OrchestratorState
from app import AgentApp, TaskRun
from tools.registry import UnifiedToolRegistry


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

    def plan_task(self, user_intent: str) -> TaskRun:
        self.log(f"Planning: {user_intent}", type="agent")
        run = self.app._create_task_run(user_intent)
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

    def _execution_loop(self, run: TaskRun) -> None:
        self.log("Starting execution...", type="info")
        self.app._run_task_run(run)
        self._sync_from_app()

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
