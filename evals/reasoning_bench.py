import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import app as app_mod
from config import get_settings


def run():
    settings = get_settings()
    bench = json.loads(Path("evals/reasoning_bench.json").read_text(encoding="utf-8-sig"))
    # We use a lightweight agent call if OPENAI/OLLAMA configured; otherwise skip.
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("OLLAMA_MODEL")):
        print("reasoning_bench skipped: no model configured")
        return

    # Use app agent chat directly
    memory = app_mod.MemoryStore(settings.memory_db, settings.embedding_dim)
    app = app_mod.AgentApp.__new__(app_mod.AgentApp)
    app.settings = settings
    app.memory = memory
    app.metrics = app_mod.Metrics()
    app.rag = app_mod.RagStore(memory)
    app.retriever = app_mod.RetrieverAgent(memory)

    passed = 0
    failed = 0
    for task in bench["tasks"]:
        ans = app._agent_chat(task["question"]) or ""
        if task["expected"].lower() in ans.lower():
            passed += 1
        else:
            failed += 1
    print(f"reasoning_bench: {passed} passed, {failed} failed")


if __name__ == "__main__":
    run()
