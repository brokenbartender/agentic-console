from __future__ import annotations


def run_waterfall_pipeline(task: str) -> str:
    if not task:
        raise RuntimeError("workflow waterfall requires a task")
    phases = [
        "Design",
        "Implementation",
        "Testing",
        "Documentation",
    ]
    lines = ["Waterfall Workflow"]
    for p in phases:
        lines.append(f"- {p}: {task}")
    return "\n".join(lines)
