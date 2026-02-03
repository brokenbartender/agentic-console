from __future__ import annotations

import re
from pathlib import Path
from typing import List


DEFAULT_MIN_CHARS = 200


def load_constitution(path: str | None = None) -> List[re.Pattern]:
    if path is None:
        path = str(Path(__file__).resolve().parent / "docs" / "data_constitution.md")
    rules: List[re.Pattern] = []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except Exception:
        return rules
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("block:"):
            pattern = line.split(":", 1)[1].strip()
            try:
                rules.append(re.compile(pattern))
            except re.error:
                continue
    return rules


def check_text(text: str, min_chars: int = DEFAULT_MIN_CHARS, path: str | None = None) -> List[str]:
    issues: List[str] = []
    if not text or len(text.strip()) < min_chars:
        issues.append("Document too short to index.")
        return issues
    for rule in load_constitution(path):
        if rule.search(text):
            issues.append(f"Blocked by constitution rule: {rule.pattern}")
    return issues
