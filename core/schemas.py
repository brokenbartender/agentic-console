from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ToolCall:
    name: str
    args: str
    risk: str
    run_id: str
    step_id: int | None
    timestamp: float
    dry_run: bool = False


@dataclass
class TaskEvent:
    event_type: str
    run_id: str
    step_id: int | None
    payload: Dict[str, Any]
    timestamp: float


@dataclass
class PolicyViolation:
    rule: str
    severity: str
    run_id: str
    step_id: int | None
    timestamp: float
    details: Dict[str, Any]


@dataclass
class RunHeartbeat:
    run_id: str
    status: str
    timestamp: float
