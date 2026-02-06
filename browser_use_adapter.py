from __future__ import annotations

from typing import Any, Optional


class BrowserUseAdapter:
    def __init__(self) -> None:
        self._agent = None
        try:
            from browser_use import Agent  # type: ignore
            self._agent = Agent
        except Exception:
            self._agent = None

    def run(self, task: str) -> str:
        if self._agent is None:
            raise RuntimeError("browser-use not installed")
        try:
            agent = self._agent()
            result = agent.run(task)  # type: ignore[attr-defined]
            return str(result)
        except Exception as exc:
            return f"browser-use error: {exc}"


class WorkflowUseAdapter:
    def __init__(self) -> None:
        self._module: Optional[Any] = None
        try:
            import workflow_use  # type: ignore

            self._module = workflow_use
        except Exception:
            self._module = None

    def run(self, workflow_path: str, goal: str = "") -> str:
        if self._module is None:
            raise RuntimeError("workflow-use not installed")
        try:
            return str(self._module.run(workflow_path, goal=goal))
        except Exception as exc:
            return f"workflow-use error: {exc}"
