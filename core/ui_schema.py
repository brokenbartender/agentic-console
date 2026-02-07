from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal

UIBlockType = Literal[
    "table",
    "form",
    "approval",
    "diff",
    "timeline",
    "toast",
    "image",
    "cards",
]


@dataclass
class UIAction:
    type: Literal["tool_call", "approve", "navigate", "set_state"]
    label: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UIBlock:
    id: str
    type: UIBlockType
    data: Dict[str, Any] = field(default_factory=dict)
    actions: List[UIAction] = field(default_factory=list)


@dataclass
class UIPatch:
    id: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceUpdate:
    message: str
    level: str = "info"
