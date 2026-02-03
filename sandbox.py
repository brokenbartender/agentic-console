from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Dict, Any


DEFAULT_TIMEOUT = 10


def run_python(code: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    if not code.strip():
        raise RuntimeError("sandbox_run requires code")
    env = {"PYTHONIOENCODING": "utf-8"}
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            ["python", "-c", code],
            cwd=tmp,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
