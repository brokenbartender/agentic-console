import sqlite3
import unittest

from cognitive import slow_mode, dot_ensemble
from graph_rag import GraphStore
from rag import RagStore


class CognitiveGraphTests(unittest.TestCase):
    def test_slow_mode_calls(self):
        calls = []

        def dummy(prompt: str) -> str:
            calls.append(prompt)
            return f"ok-{len(calls)}"

        out = slow_mode(dummy, "hello", passes=3)
        self.assertEqual(out, "ok-3")
        self.assertEqual(len(calls), 3)

    def test_dot_ensemble_selects(self):
        def dummy(prompt: str) -> str:
            lower = prompt.lower()
            if lower.startswith("draft 1"):
                return "alpha"
            if lower.startswith("draft 2"):
                return "beta"
            if lower.startswith("draft 3"):
                return "gamma"
            if "evaluate the drafts" in lower:
                return "Draft 2 is best"
            return "unknown"

        out = dot_ensemble(dummy, "question", n=3)
        self.assertEqual(out, "beta")

    def test_graph_store_neighbors(self):
        conn = sqlite3.connect(":memory:")
        store = GraphStore(conn)
        a_id = store.add_entity("Alpha", "concept")
        b_id = store.add_entity("Beta", "concept")
        store.add_edge(a_id, "related_to", b_id)
        neighbors = store.neighbors("Alpha")
        self.assertEqual(
            neighbors,
            [{"name": "Beta", "type": "concept", "rel": "related_to"}],
        )

    def test_hybrid_search(self):
        class DummyMemory:
            def __init__(self):
                self._conn = sqlite3.connect(":memory:")
                self.embedding_dim = 4

        mem = DummyMemory()
        rag = RagStore(mem)
        graph = GraphStore(mem._conn)
        rag.index_text("source.txt", "Alpha mentions Beta")
        graph.add_entity("Alpha", "concept")
        results = rag.hybrid_search("Alpha", graph, limit=3)
        self.assertTrue(len(results) >= 1)


if __name__ == "__main__":
    unittest.main()
