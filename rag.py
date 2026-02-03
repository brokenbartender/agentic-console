from __future__ import annotations

import os
import json
from typing import List

from memory import _embed_text, _cosine


def _read_pdf_text(path: str, max_pages: int = 30) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        return ""
    try:
        reader = PdfReader(path)
    except Exception:
        return ""
    parts = []
    pages = reader.pages[:max_pages]
    for page in pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text:
            parts.append(text)
    return "\n".join(parts)


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
        text = ""
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            text = _read_pdf_text(path)
            if not text:
                try:
                    from multimodal import ocr_pdf
                    text = ocr_pdf(path, pages=2)
                except Exception:
                    text = ""
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                text = handle.read()
        if not text:
            raise RuntimeError("No text extracted for indexing.")
        # chunking for provenance and retrieval quality
        chunk_size = 1000
        count = 0
        for i in range(0, len(text), chunk_size):
            chunk = text[i : i + chunk_size]
            if chunk.strip():
                self.index_text(os.path.basename(path), chunk)
                count += 1
        return count

    def stats(self) -> dict:
        cur = self.memory._conn.cursor()
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT source) FROM rag_chunks")
        total, sources = cur.fetchone()
        return {"chunks": total or 0, "sources": sources or 0}

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
