from __future__ import annotations

from .content_pipeline import run_content_pipeline
from .triage_pipeline import run_triage_pipeline


WORKFLOWS = {
    "content": run_content_pipeline,
    "triage": run_triage_pipeline,
}


def run_workflow(name: str, payload: str) -> str:
    if name not in WORKFLOWS:
        raise RuntimeError(f"Unknown workflow: {name}")
    return WORKFLOWS[name](payload)
