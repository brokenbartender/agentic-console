import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {
    "tests",
    "evals",
    "docs",
    "build",
    "dist",
    "tmp",
    "data",
    "__pycache__",
}


def _iter_py_files():
    for path in ROOT.rglob("*.py"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        yield path


class EnforcementTests(unittest.TestCase):
    def test_no_subprocess_outside_executor(self):
        offenders = []
        for path in _iter_py_files():
            if path.parts[-2:] == ("executor", "shell.py"):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "import subprocess" in text or "subprocess." in text:
                offenders.append(str(path))
        self.assertFalse(offenders, f"Subprocess usage outside executor/shell.py: {offenders}")

    def test_no_os_system(self):
        offenders = []
        for path in _iter_py_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "os.system(" in text:
                offenders.append(str(path))
        self.assertFalse(offenders, f"os.system usage is forbidden: {offenders}")

    def test_no_shutil_outside_executor_files(self):
        offenders = []
        for path in _iter_py_files():
            if path.parts[-2:] == ("executor", "files.py"):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "import shutil" in text or "shutil." in text:
                offenders.append(str(path))
        self.assertFalse(offenders, f"shutil usage outside executor/files.py: {offenders}")

    def test_tool_execute_must_use_executor(self):
        offenders = []
        for path in _iter_py_files():
            if path.parts[-2:] == ("executor", "execute.py"):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "tools.execute(" in text:
                offenders.append(str(path))
        self.assertFalse(offenders, f"Direct tools.execute usage is forbidden: {offenders}")

    def test_workflows_cannot_import_tools_or_executor(self):
        offenders = []
        for path in (ROOT / "workflows").rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "import tools" in text or "from tools" in text:
                offenders.append(str(path))
            if "import executor" in text or "from executor" in text:
                offenders.append(str(path))
        self.assertFalse(offenders, f"Workflow files importing tools/executor: {offenders}")
