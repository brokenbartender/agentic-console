from __future__ import annotations

import os
import json
from typing import List

from memory import _embed_text, _cosine


class RagStore:
    def __init__(self, memory) -> None:
        self.memory = memory
        self._init()

    def _init(self) -> None:
        cur = self.memory._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding TEXT NOT NULL
            )
            """
        )
        self.memory._conn.commit()

    def index_text(self, source: str, text: str) -> int:
        emb = _embed_text(text, self.memory.embedding_dim)
        cur = self.memory._conn.cursor()
        cur.execute(
            "INSERT INTO rag_chunks (source, text, embedding) VALUES (?, ?, ?)",
            (source, text, json.dumps(emb)),
        )
        self.memory._conn.commit()
        return cur.lastrowid

    def index_file(self, path: str) -> int:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            text = handle.read()
        return self.index_text(os.path.basename(path), text)

    def search(self, query: str, limit: int = 5) -> List[dict]:
        qvec = _embed_text(query, self.memory.embedding_dim)
        cur = self.memory._conn.cursor()
        cur.execute("SELECT id, source, text, embedding FROM rag_chunks")
        rows = cur.fetchall()
        scored = []
        for _id, source, text, emb_json in rows:
            try:
                emb = json.loads(emb_json)
            except Exception:
                continue
            score = _cosine(qvec, emb)
            if score <= 0:
                continue
            scored.append({"id": _id, "source": source, "text": text, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]
