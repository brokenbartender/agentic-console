from __future__ import annotations


def choose_model(instruction: str) -> str:
    lowered = instruction.lower()
    if "code" in lowered or "python" in lowered or "script" in lowered:
        return "coding"
    if "why" in lowered or "reason" in lowered or "analyze" in lowered:
        return "reasoning"
    return "default"
