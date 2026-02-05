"""
Centralized subprocess execution.
Phase 2: all subprocess calls should route through here.
"""

from __future__ import annotations

import subprocess
from typing import Dict, Any, List, Optional


def run_subprocess(
    args: List[str],
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    timeout: Optional[int] = None,
    text: bool = True,
) -> Dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=text,
        timeout=timeout,
    )
    return {
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip() if text else proc.stdout,
        "stderr": (proc.stderr or "").strip() if text else proc.stderr,
    }
