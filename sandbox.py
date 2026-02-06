from __future__ import annotations

import os
import shutil
from executor.shell import run_subprocess
import tempfile
from typing import Dict, Any


DEFAULT_TIMEOUT = 10


def run_python(code: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    if not code.strip():
        raise RuntimeError("sandbox_run requires code")
    env = {"PYTHONIOENCODING": "utf-8"}
    use_docker = os.getenv("AGENTIC_SANDBOX_DOCKER", "false").lower() in ("1", "true", "yes", "on")
    docker_img = os.getenv("AGENTIC_SANDBOX_IMAGE", "python:3.11-slim")
    with tempfile.TemporaryDirectory() as tmp:
        if use_docker and shutil.which("docker"):
            return run_subprocess(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-i",
                    "-v",
                    f"{tmp}:/work",
                    "-w",
                    "/work",
                    docker_img,
                    "python",
                    "-c",
                    code,
                ],
                cwd=tmp,
                env=env,
                timeout=timeout,
                text=True,
            )
        return run_subprocess(
            ["python", "-c", code],
            cwd=tmp,
            env=env,
            timeout=timeout,
            text=True,
        )
