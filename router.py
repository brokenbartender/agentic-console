from __future__ import annotations

import os
from memory import _embed_text, _cosine


_LABELS = {
    "coding": "code python script implement debug refactor",
    "reasoning": "analyze why reason explain evaluate compare",
    "default": "general chat answer respond",
}


def choose_model(instruction: str) -> str:
    dims = int(os.getenv("AGENTIC_EMBEDDING_DIM", "256"))
    qvec = _embed_text(instruction, dims)
    best = ("default", 0.0)
    for name, seed in _LABELS.items():
        score = _cosine(qvec, _embed_text(seed, dims))
        if score > best[1]:
            best = (name, score)
    if best[1] < 0.05:
        lowered = instruction.lower()
        if "code" in lowered or "python" in lowered or "script" in lowered:
            return "coding"
        if "why" in lowered or "reason" in lowered or "analyze" in lowered:
            return "reasoning"
        return "default"
    return best[0]
