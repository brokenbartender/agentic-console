from __future__ import annotations

import os
import json
from typing import List

from memory import _embed_text, _cosine
from data_constitution import check_text


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
                embedding TEXT NOT NULL,
                source_path TEXT,
                chunk_index INTEGER,
                chunk_start INTEGER,
                chunk_end INTEGER,
                metadata TEXT,
                source_rank REAL DEFAULT 1.0,
                created_at TEXT
            )
            """
        )
        self._migrate()
        self.memory._conn.commit()

    def _migrate(self) -> None:
        cur = self.memory._conn.cursor()
        cur.execute("PRAGMA table_info(rag_chunks)")
        cols = {row[1] for row in cur.fetchall()}
        if "source_path" not in cols:
            cur.execute("ALTER TABLE rag_chunks ADD COLUMN source_path TEXT")
        if "chunk_index" not in cols:
            cur.execute("ALTER TABLE rag_chunks ADD COLUMN chunk_index INTEGER")
        if "chunk_start" not in cols:
            cur.execute("ALTER TABLE rag_chunks ADD COLUMN chunk_start INTEGER")
        if "chunk_end" not in cols:
            cur.execute("ALTER TABLE rag_chunks ADD COLUMN chunk_end INTEGER")
        if "metadata" not in cols:
            cur.execute("ALTER TABLE rag_chunks ADD COLUMN metadata TEXT")
        if "source_rank" not in cols:
            cur.execute("ALTER TABLE rag_chunks ADD COLUMN source_rank REAL DEFAULT 1.0")
        if "created_at" not in cols:
            cur.execute("ALTER TABLE rag_chunks ADD COLUMN created_at TEXT")

    def _current_source_rank(self, source: str) -> float:
        cur = self.memory._conn.cursor()
        cur.execute("SELECT AVG(source_rank) FROM rag_chunks WHERE source = ?", (source,))
        row = cur.fetchone()
        if not row or row[0] is None:
            return 1.0
        try:
            return float(row[0])
        except Exception:
            return 1.0

    def index_text(
        self,
        source: str,
        text: str,
        source_path: str | None = None,
        chunk_index: int | None = None,
        chunk_start: int | None = None,
        chunk_end: int | None = None,
        metadata: dict | None = None,
        source_rank: float | None = None,
    ) -> int:
        emb = _embed_text(text, self.memory.embedding_dim)
        if source_rank is None:
            source_rank = self._current_source_rank(source)
        created_at = None
        try:
            import datetime as _dt
            created_at = _dt.datetime.utcnow().isoformat()
        except Exception:
            created_at = None
        cur = self.memory._conn.cursor()
        cur.execute(
            """
            INSERT INTO rag_chunks (
                source, text, embedding, source_path, chunk_index, chunk_start, chunk_end,
                metadata, source_rank, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source,
                text,
                json.dumps(emb),
                source_path,
                chunk_index,
                chunk_start,
                chunk_end,
                json.dumps(metadata or {}),
                source_rank,
                created_at,
            ),
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
        issues = check_text(text)
        if issues:
            raise RuntimeError("Data constitution blocked indexing: " + "; ".join(issues))
        try:
            stat = os.stat(path)
            metadata = {
                "path": path,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "ext": ext,
            }
        except Exception:
            metadata = {"path": path, "ext": ext}
        # chunking for provenance and retrieval quality
        chunk_size = 1000
        count = 0
        for idx, i in enumerate(range(0, len(text), chunk_size)):
            chunk = text[i : i + chunk_size]
            if chunk.strip():
                self.index_text(
                    os.path.basename(path),
                    chunk,
                    source_path=path,
                    chunk_index=idx,
                    chunk_start=i,
                    chunk_end=i + len(chunk),
                    metadata=metadata,
                )
                count += 1
        return count

    def list_sources(self) -> List[dict]:
        cur = self.memory._conn.cursor()
        cur.execute(
            """
            SELECT source, COUNT(*), AVG(source_rank), MAX(created_at)
            FROM rag_chunks
            GROUP BY source
            ORDER BY AVG(source_rank) DESC, COUNT(*) DESC
            """
        )
        rows = cur.fetchall()
        sources = []
        for source, count, avg_rank, last_seen in rows:
            sources.append(
                {
                    "source": source,
                    "chunks": int(count or 0),
                    "avg_rank": float(avg_rank or 0.0),
                    "last_seen": last_seen or "",
                }
            )
        return sources

    def set_source_rank(self, source: str, rank: float) -> int:
        cur = self.memory._conn.cursor()
        cur.execute("UPDATE rag_chunks SET source_rank = ? WHERE source = ?", (rank, source))
        self.memory._conn.commit()
        return cur.rowcount

    def stats(self) -> dict:
        cur = self.memory._conn.cursor()
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT source) FROM rag_chunks")
        total, sources = cur.fetchone()
        return {"chunks": total or 0, "sources": sources or 0}

    def search(self, query: str, limit: int = 5) -> List[dict]:
        qvec = _embed_text(query, self.memory.embedding_dim)
        cur = self.memory._conn.cursor()
        cur.execute(
            """
            SELECT id, source, text, embedding, source_rank, source_path,
                   chunk_index, chunk_start, chunk_end, metadata
            FROM rag_chunks
            """
        )
        rows = cur.fetchall()
        scored = []
        for _id, source, text, emb_json, source_rank, source_path, chunk_index, chunk_start, chunk_end, metadata in rows:
            try:
                emb = json.loads(emb_json)
            except Exception:
                continue
            score = _cosine(qvec, emb)
            if score <= 0:
                continue
            try:
                rank = float(source_rank) if source_rank is not None else 1.0
            except Exception:
                rank = 1.0
            rank = max(0.0, min(rank, 2.0))
            weight = 0.5 + 0.5 * rank
            weighted = score * weight
            try:
                metadata_obj = json.loads(metadata) if metadata else {}
            except Exception:
                metadata_obj = {}
            scored.append(
                {
                    "id": _id,
                    "source": source,
                    "text": text,
                    "score": score,
                    "weighted_score": weighted,
                    "source_rank": rank,
                    "source_path": source_path or "",
                    "chunk_index": chunk_index,
                    "chunk_start": chunk_start,
                    "chunk_end": chunk_end,
                    "metadata": metadata_obj,
                }
            )
        scored.sort(key=lambda x: x["weighted_score"], reverse=True)
        return scored[:limit]

    def hybrid_search(self, query: str, graph_store, limit: int = 5) -> List[dict]:
        results = self.search(query, limit=limit)
        try:
            entities = graph_store.find_entities(query)
        except Exception:
            entities = []
        if not entities:
            return results
        expanded_query = query + " " + " ".join(entities)
        graph_results = self.search(expanded_query, limit=limit)
        merged = {r["id"]: r for r in results}
        for item in graph_results:
            merged.setdefault(item["id"], item)
        merged_list = list(merged.values())
        merged_list.sort(key=lambda x: x["weighted_score"], reverse=True)
        return merged_list[:limit]
