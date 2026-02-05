from __future__ import annotations

import os
from executor.shell import run_subprocess
import tempfile
from typing import Dict, Any


DEFAULT_TIMEOUT = 10


def run_python(code: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    if not code.strip():
        raise RuntimeError("sandbox_run requires code")
    env = {"PYTHONIOENCODING": "utf-8"}
    with tempfile.TemporaryDirectory() as tmp:
        return run_subprocess(
            ["python", "-c", code],
            cwd=tmp,
            env=env,
            timeout=timeout,
            text=True,
        )
