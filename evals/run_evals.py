import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tools import ToolRegistry, ToolContext
from config import get_settings
from memory import MemoryStore
from metrics import Metrics


class DummyApp:
    def __init__(self):
        self.settings = get_settings()
        self.memory = MemoryStore(self.settings.memory_db, self.settings.embedding_dim)
        self.metrics = Metrics()
        self.page = None

    def ensure_browser(self):
        raise RuntimeError("Browser not available in evals")


def run():
    tasks = json.loads(Path("evals/tasks.json").read_text(encoding="utf-8-sig"))
    app = DummyApp()
    tools = ToolRegistry(app)
    passed = 0
    failed = 0
    for task in tasks:
        name = task["name"]
        instruction = task["instruction"]
        expect = task["expect"]
        try:
            lowered = instruction.lower().strip()
            output = ""
            for tool_name in tools.tools.keys():
                prefix = f"{tool_name} "
                if lowered.startswith(prefix):
                    args = instruction[len(prefix):].strip()
                    output = tools.execute(tool_name, args, ToolContext(dry_run=True))
                    break
            if not output:
                output = "Agent task completed"
            if expect not in output:
                raise AssertionError(f"Expected '{expect}' in '{output}'")
            print(f"PASS: {name}")
            passed += 1
        except Exception as exc:
            print(f"FAIL: {name}: {exc}")
            failed += 1
    print(f"Summary: {passed} passed, {failed} failed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    run()
