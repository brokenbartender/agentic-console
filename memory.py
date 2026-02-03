from __future__ import annotations

import os
import sqlite3
import time
import json
import math
import hashlib
import re
from typing import Optional, List, Dict


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def _embed_text(text: str, dims: int) -> List[int]:
    vec = [0] * dims
    for tok in _tokenize(text):
        h = hashlib.sha1(tok.encode("utf-8")).hexdigest()
        idx = int(h, 16) % dims
        vec[idx] += 1
    return vec


def _cosine(a: List[int], b: List[int]) -> float:
    dot = 0
    na = 0
    nb = 0
    for i in range(len(a)):
        av = a[i]
        bv = b[i]
        dot += av * bv
        na += av * av
        nb += bv * bv
    if na == 0 or nb == 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


class MemoryStore:
    def __init__(self, db_path: str, embedding_dim: int = 256) -> None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self.embedding_dim = embedding_dim
        self._init()

    def _init(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS kv (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL,
                tags TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS model_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                model TEXT NOT NULL,
                tokens_in INTEGER NOT NULL,
                tokens_out INTEGER NOT NULL,
                cost REAL NOT NULL,
                latency REAL NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                rating INTEGER NOT NULL,
                notes TEXT
            )
            """
        )
        self._conn.commit()

    def set(self, key: str, value: str) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO kv (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, time.time()),
        )
        self._conn.commit()

    def get(self, key: str) -> Optional[str]:
        cur = self._conn.cursor()
        cur.execute("SELECT value FROM kv WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def log_event(self, event_type: str, payload: str) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO events (timestamp, event_type, payload) VALUES (?, ?, ?)",
            (time.time(), event_type, payload),
        )
        self._conn.commit()

    def purge_events(self, retention_seconds: Optional[int]) -> None:
        if retention_seconds is None or retention_seconds <= 0:
            return
        cutoff = time.time() - retention_seconds
        cur = self._conn.cursor()
        cur.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))
        self._conn.commit()

    def log_model_run(self, model: str, tokens_in: int, tokens_out: int, cost: float, latency: float) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO model_runs (timestamp, model, tokens_in, tokens_out, cost, latency) VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), model, tokens_in, tokens_out, cost, latency),
        )
        self._conn.commit()

    def model_summary(self, limit: int = 50) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT model, COUNT(*), AVG(latency), SUM(tokens_in), SUM(tokens_out), SUM(cost) "
            "FROM model_runs GROUP BY model ORDER BY COUNT(*) DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {
                "model": model,
                "runs": int(runs),
                "avg_latency": float(avg_latency or 0),
                "tokens_in": int(tokens_in or 0),
                "tokens_out": int(tokens_out or 0),
                "cost": float(cost or 0),
            }
            for (model, runs, avg_latency, tokens_in, tokens_out, cost) in rows
        ]

    def add_feedback(self, rating: int, notes: str | None = None) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO feedback (timestamp, rating, notes) VALUES (?, ?, ?)",
            (time.time(), rating, notes or ""),
        )
        self._conn.commit()

    def recent_events(self, limit: int = 50) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT timestamp, event_type, payload FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {"timestamp": ts, "event_type": et, "payload": payload}
            for (ts, et, payload) in rows
        ]

    def add_memory(self, kind: str, content: str, tags: Optional[List[str]] = None, ttl_seconds: Optional[int] = None) -> None:
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        embedding = _embed_text(content, self.embedding_dim)
        payload = json.dumps(embedding)
        tags_blob = json.dumps(tags or [])
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO memories (kind, content, embedding, created_at, expires_at, tags) VALUES (?, ?, ?, ?, ?, ?)",
            (kind, content, payload, time.time(), expires_at, tags_blob),
        )
        self._conn.commit()

    def purge_expired(self) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at < ?", (time.time(),))
        self._conn.commit()

    def search_memory(self, query: str, limit: int = 5) -> List[Dict[str, str]]:
        self.purge_expired()
        qvec = _embed_text(query, self.embedding_dim)
        cur = self._conn.cursor()
        cur.execute("SELECT kind, content, embedding, created_at, tags FROM memories")
        rows = cur.fetchall()
        scored = []
        for kind, content, emb_json, created_at, tags_blob in rows:
            try:
                emb = json.loads(emb_json)
            except Exception:
                continue
            score = _cosine(qvec, emb)
            if score <= 0:
                continue
            scored.append({
                "kind": kind,
                "content": content,
                "score": score,
                "created_at": created_at,
                "tags": tags_blob or "[]",
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]
