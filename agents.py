from __future__ import annotations

import re
from typing import List


class PlannerAgent:
    def __init__(self, tool_prefixes: List[str]) -> None:
        self.tool_prefixes = tuple(tool_prefixes)

    def plan(self, instruction: str) -> List[str]:
        lowered = instruction.strip().lower()
        if lowered.startswith(self.tool_prefixes):
            return [instruction]

        # Delegate patterns
        m = re.search(r"delegate\s+to\s+(\w+)\s*:\s*(.+)", instruction, flags=re.IGNORECASE)
        if not m:
            m = re.search(r"delegate\s+(\w+)\s*:\s*(.+)", instruction, flags=re.IGNORECASE)
        if not m:
            m = re.search(r"\[delegate:(\w+)\]\s*(.+)", instruction, flags=re.IGNORECASE)
        if m:
            peer = m.group(1).strip()
            task = m.group(2).strip()
            return [f"delegate:{peer} {task}"]

        if " and " in lowered or " then " in lowered:
            parts = re.split(r"\bthen\b|\band\b", instruction, flags=re.IGNORECASE)
            steps = [p.strip() for p in parts if p.strip()]
            if len(steps) > 1:
                return steps
        return []


class RetrieverAgent:
    def __init__(self, memory) -> None:
        self.memory = memory

    def retrieve(self, query: str, limit: int = 5) -> str:
        results = self.memory.search_memory(query, limit=limit)
        if not results:
            return ""
        lines = []
        for item in results:
            lines.append(f"- ({item['kind']}) {item['content']}")
        return "\n".join(lines)


class VerifierAgent:
    def verify(self, steps: List[str]) -> str:
        if not steps:
            return ""
        return "Verified steps: " + ", ".join(steps)


class ExecutorAgent:
    def __init__(self, execute_step) -> None:
        self.execute_step = execute_step

    def run(self, steps: List[str]) -> None:
        for step in steps:
            self.execute_step(step)
