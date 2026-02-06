from __future__ import annotations

from .graph_workflow import StateGraph, Checkpointer


def run_graph_workflow(payload: str, data_dir: str) -> str:
    # Example graph: parse -> process -> summarize
    g = StateGraph()

    def parse(state):
        state["parsed"] = state.get("input", "")
        return state

    def process(state):
        state["processed"] = state.get("parsed", "").upper()
        return state

    def summarize(state):
        state["summary"] = f"Summary: {state.get('processed', '')[:120]}"
        return state

    g.add_node("parse", parse)
    g.add_node("process", process)
    g.add_node("summarize", summarize)
    g.add_edge("parse", "process")
    g.add_edge("process", "summarize")

    ck = Checkpointer(f"{data_dir}/graph_checkpoints.db")
    state = {"input": payload}
    out = g.run("parse", state, checkpointer=ck, key="default")
    return out.get("summary", "")
