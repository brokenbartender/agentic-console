"""
Central executor entrypoint for tool execution.
Phase 2: all tool calls should pass through this function.
"""

from __future__ import annotations

from typing import Any

from tools import ToolRegistry, ToolContext
from policy import requires_confirmation


def execute_tool(
    tools: ToolRegistry,
    name: str,
    args: str,
    autonomy_level: str,
    confirm: bool = False,
    dry_run: bool = False,
) -> Any:
    spec = tools.specs.get(name)
    if spec and requires_confirmation(spec.risk, autonomy_level) and not confirm:
        from tools import ToolNeedsConfirmation

        raise ToolNeedsConfirmation(f"Tool '{name}' requires confirmation.")
    ctx = ToolContext(confirm=confirm, dry_run=dry_run, via_executor=True)
    return tools.execute(name, args, ctx)
