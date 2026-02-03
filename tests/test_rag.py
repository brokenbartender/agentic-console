import os
import tempfile
import unittest

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from memory import MemoryStore
from rag import RagStore


class TestRagStore(unittest.TestCase):
    def test_source_rank_and_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "mem.db")
            mem = MemoryStore(db_path, embedding_dim=32)
            try:
                rag = RagStore(mem)
                rag.index_text("alpha.txt", "hello world", source_rank=1.0)
                rag.index_text("beta.txt", "another doc", source_rank=1.0)
                updated = rag.set_source_rank("alpha.txt", 1.6)
                self.assertGreaterEqual(updated, 1)
                sources = {s["source"]: s for s in rag.list_sources()}
                self.assertIn("alpha.txt", sources)
                self.assertGreaterEqual(sources["alpha.txt"]["avg_rank"], 1.5)
            finally:
                mem._conn.close()


if __name__ == "__main__":
    unittest.main()
