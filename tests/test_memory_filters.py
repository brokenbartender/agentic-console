import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from memory import MemoryStore


class TestMemoryFilters(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "memory.db")
        self.store = MemoryStore(self.db_path, embedding_dim=32)

    def tearDown(self):
        self.tmp.cleanup()

    def test_scope_and_confidence_filters(self):
        self.store.add_memory("note", "alpha shared", scope="shared", confidence=0.9)
        self.store.add_memory("note", "alpha private", scope="private", confidence=0.9)
        self.store.add_memory("note", "alpha low", scope="shared", confidence=0.1)
        results = self.store.search_memory("alpha", scope="shared")
        contents = [r["content"] for r in results]
        self.assertIn("alpha shared", contents)
        self.assertNotIn("alpha private", contents)
        self.assertNotIn("alpha low", contents)

    def test_quarantine_filter(self):
        self.store.add_memory("note", "alpha quarantined", status="quarantined")
        results = self.store.search_memory("alpha", include_quarantined=False)
        self.assertEqual(len([r for r in results if r["content"] == "alpha quarantined"]), 0)
        results = self.store.search_memory("alpha", include_quarantined=True)
        self.assertIn("alpha quarantined", [r["content"] for r in results])

    def test_acl_and_failed_run_filter(self):
        self.store.add_memory("note", "alpha acl", acl={"users": ["user1"]}, user_id="user1")
        self.store.add_memory("note", "alpha fail", run_id="run-fail")
        cur = self.store._conn.cursor()
        cur.execute(
            "INSERT INTO task_runs (run_id, created_at, status, approved, command, intent_json, plan_json, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("run-fail", 0.0, "failed", 0, "", "", "", 0.0),
        )
        self.store._conn.commit()

        results = self.store.search_memory("alpha", user_id="user2")
        contents = [r["content"] for r in results]
        self.assertNotIn("alpha acl", contents)
        self.assertNotIn("alpha fail", contents)


if __name__ == "__main__":
    unittest.main()
