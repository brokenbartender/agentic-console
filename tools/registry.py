from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from tools import ToolRegistry as LegacyToolRegistry


@dataclass
class UnifiedTool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    risk_level: str
    requires_approval: bool
    handler: Callable[..., Any] | None = None


class UnifiedToolRegistry:
    def __init__(self) -> None:
        self.tools: Dict[str, UnifiedTool] = {}

    def register(self, tool: UnifiedTool) -> None:
        self.tools[tool.name] = tool

    def list(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
                "risk_level": t.risk_level,
                "requires_approval": t.requires_approval,
            }
            for t in self.tools.values()
        ]

    @classmethod
    def from_legacy(cls, app) -> "UnifiedToolRegistry":
        reg = cls()
        legacy = LegacyToolRegistry(app)
        for name, spec in legacy.specs.items():
            reg.register(
                UnifiedTool(
                    name=name,
                    description=spec.arg_hint or name,
                    input_schema={"type": "string", "description": spec.arg_hint},
                    risk_level=spec.risk,
                    requires_approval=bool(spec.confirm_required),
                )
            )
        return reg
