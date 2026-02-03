from __future__ import annotations

import re
from typing import List


SAFE_BLOCKLIST = [
    r"rm\s+-rf",
    r"format\s+c:",
    r"del\s+/s",
]


def screen_text(text: str) -> List[str]:
    hits = []
    for pattern in SAFE_BLOCKLIST:
        if re.search(pattern, text, re.IGNORECASE):
            hits.append(pattern)
    return hits
