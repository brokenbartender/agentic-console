from __future__ import annotations

from .content_pipeline import run_content_pipeline
from .triage_pipeline import run_triage_pipeline
from .graph_pipeline import run_graph_workflow
from .waterfall_pipeline import run_waterfall_pipeline


WORKFLOWS = {
    "content": run_content_pipeline,
    "triage": run_triage_pipeline,
    "graph": run_graph_workflow,
    "waterfall": run_waterfall_pipeline,
}


def run_workflow(name: str, payload: str, data_dir: str | None = None) -> str:
    if name not in WORKFLOWS:
        raise RuntimeError(f"Unknown workflow: {name}")
    fn = WORKFLOWS[name]
    if name == "graph":
        if not data_dir:
            raise RuntimeError("graph workflow requires data_dir")
        return fn(payload, data_dir)
    return fn(payload)
