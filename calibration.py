from __future__ import annotations

from typing import List


def confidence_from_evidence(evidence: List[dict]) -> float:
    if not evidence:
        return 0.0
    # Simple heuristic: more evidence and higher average score -> higher confidence.
    avg = sum(item.get("score", 0.0) for item in evidence) / len(evidence)
    return min(1.0, 0.2 + avg)
