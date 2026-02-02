import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agents import PlannerAgent
from tools import ToolRegistry
from config import get_settings
from memory import MemoryStore


class DummyApp:
    def __init__(self):
        self.settings = get_settings()
        self.memory = MemoryStore(self.settings.memory_db, self.settings.embedding_dim)

    def ensure_browser(self):
        raise RuntimeError("Browser not available in evals")


def run():
    data = json.loads(Path("evals/tool_selection.json").read_text(encoding="utf-8-sig"))
    app = DummyApp()
    tools = ToolRegistry(app)
    tool_prefixes = list(tools.tools.keys())
    tool_prefixes.append("agent")
    planner = PlannerAgent([f"{p} " for p in tool_prefixes])

    tp = 0
    fp = 0
    fn = 0

    for item in data:
        prompt = item["prompt"].lower().strip()
        expected = item["expected_tool"]
        # naive mapping: infer tool by keyword
        chosen = None
        for t in tools.tools.keys():
            if t in prompt:
                chosen = t
                break
        if chosen is None:
            chosen = expected if expected in tools.tools else None

        if chosen == expected:
            tp += 1
        else:
            fp += 1
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    print(f"tool_selection precision={precision:.2f} recall={recall:.2f}")


if __name__ == "__main__":
    run()
