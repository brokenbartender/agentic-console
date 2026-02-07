from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal

Risk = Literal["safe", "caution", "danger"]
StepStatus = Literal["planned", "running", "succeeded", "failed", "skipped"]
RunStatus = Literal["planned", "running", "needs_input", "succeeded", "failed", "cancelled", "complete", "error", "stopped"]
VerifyType = Literal["uia_present", "dom_present", "file_exists", "sql_returns", "test_passes", "output_contains"]


@dataclass
class Budget:
    max_steps: int = 20
    max_tool_calls: int = 50
    max_seconds: int = 900
    max_tokens: int = 200_000


@dataclass
class PlanStepSchema:
    step_id: int
    title: str
    intent: str
    tool: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    risk: Risk = "safe"
    requires_confirmation: bool = False
    max_attempts: int = 2
    timeout_s: int = 90
    success_check: str = ""
    verify: Optional["VerifySchema"] = None
    fallback: Optional["PlanStepSchema"] = None


@dataclass
class VerifySchema:
    type: VerifyType
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanSchema:
    run_id: str
    trace_id: str
    goal: str
    success_criteria: List[str]
    steps: List[PlanStepSchema]
    needs_user_input: bool = False
    questions: List[Dict[str, Any]] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    budget: Budget = field(default_factory=Budget)
    created_at: float = 0.0
    model: str = ""
    needs_user_input: bool = False
    questions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ToolResult:
    name: str
    args: Dict[str, Any]
    risk: Risk
    ok: bool
    started_at: float
    ended_at: float
    output_preview: str = ""
    error: str = ""
    artifacts: Dict[str, Any] = field(default_factory=dict)
    files_changed: List[str] = field(default_factory=list)


@dataclass
class StepReport:
    step_id: int
    title: str
    status: StepStatus
    attempts: int = 0
    tool_results: List[ToolResult] = field(default_factory=list)
    notes: str = ""
    files_changed: List[str] = field(default_factory=list)
    verification_passed: bool = False
    verification_evidence: str = ""


@dataclass
class ExecutionReport:
    run_id: str
    trace_id: str
    goal: str
    status: RunStatus
    started_at: float
    ended_at: float
    steps: List[StepReport] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    tests_run: List[str] = field(default_factory=list)
    cost: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    next_actions: List[str] = field(default_factory=list)
    failure_reason: str = ""
