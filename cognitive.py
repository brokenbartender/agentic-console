from __future__ import annotations

from typing import List, Callable


def slow_mode(agent_chat: Callable[[str], str], prompt: str, passes: int = 2) -> str:
    result = ""
    for i in range(passes):
        result = agent_chat(
            f"System 2 pass {i+1}/{passes}. Think deliberately before answering.\n\n{prompt}"
        )
    return result


def dot_ensemble(agent_chat: Callable[[str], str], prompt: str, n: int = 3) -> str:
    drafts: List[str] = []
    for i in range(n):
        drafts.append(agent_chat(f"Draft {i+1}/{n}:\n{prompt}"))
    critique = agent_chat(
        "Evaluate the drafts and pick the best. Return the best draft index and a brief reason.\n\n"
        + "\n\n".join(f"Draft {i+1}:\n{d}" for i, d in enumerate(drafts))
    )
    # Simple selection: choose first unless critique names an index.
    chosen = drafts[0]
    for i in range(n):
        token = f"draft {i+1}"
        if token in critique.lower():
            chosen = drafts[i]
            break
    return chosen
