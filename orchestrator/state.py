from __future__ import annotations

from enum import Enum


class OrchestratorState(str, Enum):
    PLANNED = "planned"
    APPROVED = "approved"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETE = "complete"
    ERROR = "error"


_ALLOWED = {
    OrchestratorState.PLANNED: {OrchestratorState.APPROVED, OrchestratorState.STOPPED, OrchestratorState.ERROR},
    OrchestratorState.APPROVED: {
        OrchestratorState.RUNNING,
        OrchestratorState.PAUSED,
        OrchestratorState.STOPPED,
        OrchestratorState.ERROR,
    },
    OrchestratorState.RUNNING: {
        OrchestratorState.PAUSED,
        OrchestratorState.STOPPED,
        OrchestratorState.COMPLETE,
        OrchestratorState.ERROR,
    },
    OrchestratorState.PAUSED: {OrchestratorState.RUNNING, OrchestratorState.STOPPED, OrchestratorState.ERROR},
    OrchestratorState.STOPPED: {OrchestratorState.ERROR, OrchestratorState.COMPLETE},
    OrchestratorState.COMPLETE: set(),
    OrchestratorState.ERROR: set(),
}


def validate_transition(current: str, target: str) -> None:
    try:
        cur = OrchestratorState(current)
        nxt = OrchestratorState(target)
    except Exception as exc:
        raise RuntimeError(f"Invalid orchestrator state: {current} -> {target}") from exc
    if nxt not in _ALLOWED.get(cur, set()):
        raise RuntimeError(f"Invalid state transition: {cur.value} -> {nxt.value}")
