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
