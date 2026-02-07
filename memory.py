from __future__ import annotations

import os
import sqlite3
import time
import json
import math
import hashlib
import re
from typing import Optional, List, Dict, Any
from privacy import redact_text, contains_sensitive


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
        self._allowed_scopes = {"shared", "private"}
        self._allowed_statuses = {"active", "quarantined", "deprecated"}

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
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                schema_version TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS debug_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                schema_version TEXT
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
                tags TEXT,
                source TEXT,
                confidence REAL,
                relevance REAL,
                user_id TEXT,
                project_id TEXT,
                acl TEXT,
                scope TEXT DEFAULT 'shared',
                status TEXT DEFAULT 'active',
                quarantine_reason TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_refs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER NOT NULL,
                run_id TEXT,
                step_id INTEGER,
                tool_call_id TEXT
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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                severity TEXT NOT NULL,
                summary TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                name TEXT NOT NULL,
                notes TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS personas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                constraints TEXT,
                owner TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS long_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                title TEXT NOT NULL,
                milestones TEXT,
                status TEXT NOT NULL,
                last_checkin REAL NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS oversight_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                rule TEXT NOT NULL,
                severity TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bdi_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                kind TEXT NOT NULL,
                text TEXT NOT NULL,
                owner TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS action_space (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                label TEXT NOT NULL,
                notes TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS task_runs (
                run_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                status TEXT NOT NULL,
                approved INTEGER NOT NULL,
                command TEXT NOT NULL,
                intent_json TEXT,
                plan_json TEXT,
                updated_at REAL NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                run_id TEXT,
                status TEXT NOT NULL,
                metadata TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS run_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                model_id TEXT,
                prompt_hash TEXT,
                tool_versions TEXT,
                env_fingerprint TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS nondet_inputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                timestamp REAL NOT NULL,
                source TEXT,
                payload TEXT
            )
            """
        )
        self._conn.commit()
        self._migrate_memories()
        self._ensure_indexes()

    def _migrate_memories(self) -> None:
        cur = self._conn.cursor()
        cur.execute("PRAGMA table_info(memories)")
        cols = {row[1] for row in cur.fetchall()}
        if "scope" not in cols:
            cur.execute("ALTER TABLE memories ADD COLUMN scope TEXT DEFAULT 'shared'")
        if "status" not in cols:
            cur.execute("ALTER TABLE memories ADD COLUMN status TEXT DEFAULT 'active'")
        if "quarantine_reason" not in cols:
            cur.execute("ALTER TABLE memories ADD COLUMN quarantine_reason TEXT")
        if "source" not in cols:
            cur.execute("ALTER TABLE memories ADD COLUMN source TEXT")
        if "confidence" not in cols:
            cur.execute("ALTER TABLE memories ADD COLUMN confidence REAL")
        if "relevance" not in cols:
            cur.execute("ALTER TABLE memories ADD COLUMN relevance REAL")
        if "user_id" not in cols:
            cur.execute("ALTER TABLE memories ADD COLUMN user_id TEXT")
        if "project_id" not in cols:
            cur.execute("ALTER TABLE memories ADD COLUMN project_id TEXT")
        if "acl" not in cols:
            cur.execute("ALTER TABLE memories ADD COLUMN acl TEXT")
        self._conn.commit()

    def _ensure_indexes(self) -> None:
        cur = self._conn.cursor()
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_memories_exp ON memories(expires_at)")
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_source ON rag_chunks(source)")
        except sqlite3.OperationalError:
            # rag_chunks table is created by RagStore; skip if it doesn't exist yet.
            pass
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

    def log_audit(self, event_type: str, payload: str, schema_version: str = "v1") -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO audit_logs (timestamp, event_type, payload, schema_version) VALUES (?, ?, ?, ?)",
            (time.time(), event_type, payload, schema_version),
        )
        self._conn.commit()

    def log_debug(self, event_type: str, payload: str, schema_version: str = "v1") -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO debug_logs (timestamp, event_type, payload, schema_version) VALUES (?, ?, ?, ?)",
            (time.time(), event_type, payload, schema_version),
        )
        self._conn.commit()

    def get_recent_events(self, limit: int = 20) -> List[Dict]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT timestamp, event_type, payload FROM events ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        events: List[Dict] = []
        for ts, etype, payload in rows:
            try:
                payload_obj = json.loads(payload)
            except Exception:
                payload_obj = {"raw": payload}
            events.append({"timestamp": ts, "type": etype, "payload": payload_obj})
        return events

    def purge_events(self, retention_seconds: Optional[int]) -> None:
        if retention_seconds is None or retention_seconds <= 0:
            return
        cutoff = time.time() - retention_seconds
        cur = self._conn.cursor()
        cur.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))
        self._conn.commit()

    def purge_audit_logs(self, retention_seconds: Optional[int]) -> None:
        if retention_seconds is None or retention_seconds <= 0:
            return
        cutoff = time.time() - retention_seconds
        cur = self._conn.cursor()
        cur.execute("DELETE FROM audit_logs WHERE timestamp < ?", (cutoff,))
        self._conn.commit()

    def purge_debug_logs(self, retention_seconds: Optional[int]) -> None:
        if retention_seconds is None or retention_seconds <= 0:
            return
        cutoff = time.time() - retention_seconds
        cur = self._conn.cursor()
        cur.execute("DELETE FROM debug_logs WHERE timestamp < ?", (cutoff,))
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

    def add_incident(self, severity: str, summary: str) -> int:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO incidents (timestamp, severity, summary) VALUES (?, ?, ?)",
            (time.time(), severity, summary),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_incidents(self, limit: int = 20) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, timestamp, severity, summary FROM incidents ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {"id": rid, "timestamp": ts, "severity": severity, "summary": summary}
            for (rid, ts, severity, summary) in rows
        ]

    def add_evaluation(self, name: str, notes: str | None = None) -> int:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO evaluations (timestamp, name, notes) VALUES (?, ?, ?)",
            (time.time(), name, notes or ""),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_evaluations(self, limit: int = 20) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, timestamp, name, notes FROM evaluations ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {"id": rid, "timestamp": ts, "name": name, "notes": notes or ""}
            for (rid, ts, name, notes) in rows
        ]

    def add_persona(self, name: str, role: str, constraints: str | None = None, owner: str | None = None) -> int:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO personas (timestamp, name, role, constraints, owner) VALUES (?, ?, ?, ?, ?)",
            (time.time(), name, role, constraints or "", owner or ""),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_personas(self, limit: int = 20) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, timestamp, name, role, constraints, owner FROM personas ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": rid,
                "timestamp": ts,
                "name": name,
                "role": role,
                "constraints": constraints or "",
                "owner": owner or "",
            }
            for (rid, ts, name, role, constraints, owner) in rows
        ]

    def add_long_run(self, title: str, milestones: str | None = None) -> int:
        now = time.time()
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO long_runs (timestamp, title, milestones, status, last_checkin) VALUES (?, ?, ?, ?, ?)",
            (now, title, milestones or "", "active", now),
        )
        self._conn.commit()
        return cur.lastrowid

    def update_long_run(self, run_id: int, status: str, note: str | None = None) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE long_runs SET status=?, milestones=?, last_checkin=? WHERE id=?",
            (status, note or "", time.time(), run_id),
        )
        self._conn.commit()

    def list_long_runs(self, limit: int = 20) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, timestamp, title, milestones, status, last_checkin FROM long_runs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": rid,
                "timestamp": ts,
                "title": title,
                "milestones": milestones or "",
                "status": status,
                "last_checkin": last_checkin,
            }
            for (rid, ts, title, milestones, status, last_checkin) in rows
        ]

    def add_oversight_rule(self, rule: str, severity: str) -> int:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO oversight_rules (timestamp, rule, severity) VALUES (?, ?, ?)",
            (time.time(), rule, severity),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_oversight_rules(self, limit: int = 20) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, timestamp, rule, severity FROM oversight_rules ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {"id": rid, "timestamp": ts, "rule": rule, "severity": severity}
            for (rid, ts, rule, severity) in rows
        ]

    def begin_transaction(self, run_id: str | None, metadata: str = "") -> int:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO transactions (created_at, run_id, status, metadata) VALUES (?, ?, ?, ?)",
            (time.time(), run_id or "", "prepared", metadata),
        )
        self._conn.commit()
        return cur.lastrowid

    def commit_transaction(self, tx_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE transactions SET status=? WHERE id=?", ("committed", tx_id))
        self._conn.commit()

    def rollback_transaction(self, tx_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE transactions SET status=? WHERE id=?", ("rolled_back", tx_id))
        self._conn.commit()

    def log_run_context(
        self,
        run_id: str,
        model_id: str,
        prompt_hash: str,
        tool_versions: str,
        env_fingerprint: str,
    ) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO run_context (run_id, timestamp, model_id, prompt_hash, tool_versions, env_fingerprint) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, time.time(), model_id, prompt_hash, tool_versions, env_fingerprint),
        )
        self._conn.commit()

    def log_nondet_input(self, run_id: str, source: str, payload: str) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO nondet_inputs (run_id, timestamp, source, payload) VALUES (?, ?, ?, ?)",
            (run_id, time.time(), source, payload),
        )
        self._conn.commit()

    def create_task_run(
        self,
        run_id: str,
        status: str,
        approved: bool,
        command: str,
        intent_json: str,
        plan_json: str,
    ) -> None:
        cur = self._conn.cursor()
        now = time.time()
        cur.execute(
            """
            INSERT INTO task_runs (run_id, created_at, status, approved, command, intent_json, plan_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, now, status, int(approved), command, intent_json, plan_json, now),
        )
        self._conn.commit()

    def update_task_run(
        self,
        run_id: str,
        status: str | None = None,
        approved: bool | None = None,
        intent_json: str | None = None,
        plan_json: str | None = None,
    ) -> None:
        cur = self._conn.cursor()
        fields = []
        values = []
        if status is not None:
            fields.append("status=?")
            values.append(status)
        if approved is not None:
            fields.append("approved=?")
            values.append(int(approved))
        if intent_json is not None:
            fields.append("intent_json=?")
            values.append(intent_json)
        if plan_json is not None:
            fields.append("plan_json=?")
            values.append(plan_json)
        if not fields:
            return
        fields.append("updated_at=?")
        values.append(time.time())
        values.append(run_id)
        cur.execute(f"UPDATE task_runs SET {', '.join(fields)} WHERE run_id=?", values)
        self._conn.commit()

    def get_task_run(self, run_id: str) -> Optional[Dict]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT run_id, created_at, status, approved, command, intent_json, plan_json, updated_at "
            "FROM task_runs WHERE run_id=?",
            (run_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "run_id": row[0],
            "created_at": row[1],
            "status": row[2],
            "approved": bool(row[3]),
            "command": row[4],
            "intent_json": row[5] or "",
            "plan_json": row[6] or "",
            "updated_at": row[7],
        }

    def get_latest_task_run(self) -> Optional[Dict]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT run_id, created_at, status, approved, command, intent_json, plan_json, updated_at "
            "FROM task_runs ORDER BY updated_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "run_id": row[0],
            "created_at": row[1],
            "status": row[2],
            "approved": bool(row[3]),
            "command": row[4],
            "intent_json": row[5] or "",
            "plan_json": row[6] or "",
            "updated_at": row[7],
        }

    def add_bdi(self, kind: str, text: str, owner: str | None = None) -> int:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO bdi_entries (timestamp, kind, text, owner) VALUES (?, ?, ?, ?)",
            (time.time(), kind, text, owner or ""),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_bdi(self, kind: str, limit: int = 20) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, timestamp, kind, text, owner FROM bdi_entries WHERE kind=? ORDER BY id DESC LIMIT ?",
            (kind, limit),
        )
        rows = cur.fetchall()
        return [
            {"id": rid, "timestamp": ts, "kind": k, "text": text, "owner": owner or ""}
            for (rid, ts, k, text, owner) in rows
        ]

    def add_action_space(self, name: str, description: str) -> int:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO action_space (timestamp, name, description) VALUES (?, ?, ?)",
            (time.time(), name, description),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_action_space(self, limit: int = 50) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, timestamp, name, description FROM action_space ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {"id": rid, "timestamp": ts, "name": name, "description": desc}
            for (rid, ts, name, desc) in rows
        ]

    def remove_action_space(self, name: str) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM action_space WHERE name=?", (name,))
        self._conn.commit()

    def add_checkpoint(self, label: str, notes: str | None = None) -> int:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO checkpoints (timestamp, label, notes) VALUES (?, ?, ?)",
            (time.time(), label, notes or ""),
        )
        self._conn.commit()
        return cur.lastrowid

    def update_checkpoint(self, checkpoint_id: int, notes: str) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE checkpoints SET notes=? WHERE id=?",
            (notes, checkpoint_id),
        )
        self._conn.commit()

    def list_checkpoints(self, limit: int = 20) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, timestamp, label, notes FROM checkpoints ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {"id": rid, "timestamp": ts, "label": label, "notes": notes or ""}
            for (rid, ts, label, notes) in rows
        ]

    def get_user_profile(self, user_id: str = "default") -> Dict[str, str]:
        cur = self._conn.cursor()
        cur.execute("SELECT payload FROM user_profiles WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if not row:
            return {}
        try:
            return json.loads(row[0])
        except Exception:
            return {}

    def update_user_profile(self, updates: Dict[str, str], user_id: str = "default") -> None:
        current = self.get_user_profile(user_id)
        current.update(updates or {})
        payload = json.dumps(current)
        cur = self._conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO user_profiles (user_id, payload, updated_at) VALUES (?, ?, ?)",
            (user_id, payload, time.time()),
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

    def add_memory(
        self,
        kind: str,
        content: str,
        tags: Optional[List[str]] = None,
        ttl_seconds: Optional[int] = None,
        scope: str = "shared",
        source: str = "inference",
        confidence: float = 0.5,
        relevance: float = 0.5,
        user_id: str | None = None,
        project_id: str | None = None,
        acl: Optional[Dict[str, Any]] = None,
        status: str = "active",
        quarantine_reason: str | None = None,
        run_id: str | None = None,
        step_id: int | None = None,
        tool_call_id: str | None = None,
    ) -> None:
        if user_id is None:
            user_id = os.getenv("AGENTIC_USER_ID", "default")
        if project_id is None:
            project_id = os.getenv("AGENTIC_PROJECT_ID", "")
        if scope not in self._allowed_scopes:
            raise ValueError(f"Invalid memory scope: {scope}")
        if status not in self._allowed_statuses:
            raise ValueError(f"Invalid memory status: {status}")
        if contains_sensitive(content):
            content = redact_text(content)
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        embedding = _embed_text(content, self.embedding_dim)
        payload = json.dumps(embedding)
        tags_blob = json.dumps(tags or [])
        cur = self._conn.cursor()
        acl_blob = json.dumps(acl or {})
        cur.execute(
            "INSERT INTO memories (kind, content, embedding, created_at, expires_at, tags, source, confidence, relevance, user_id, project_id, acl, scope, status, quarantine_reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (kind, content, payload, time.time(), expires_at, tags_blob, source, confidence, relevance, user_id, project_id, acl_blob, scope, status, quarantine_reason),
        )
        memory_id = cur.lastrowid
        if run_id or step_id or tool_call_id:
            cur.execute(
                "INSERT INTO memory_refs (memory_id, run_id, step_id, tool_call_id) VALUES (?, ?, ?, ?)",
                (memory_id, run_id, step_id, tool_call_id),
            )
        self._conn.commit()

    def purge_expired(self) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at < ?", (time.time(),))
        self._conn.commit()

    def prune_memories(self) -> None:
        # Phase 6: enforce TTL-based pruning for all expired memories.
        self.purge_expired()

    def search_memory(
        self,
        query: str,
        limit: int = 5,
        scope: str = "shared",
        include_quarantined: bool = False,
        min_confidence: float = 0.2,
        user_id: str | None = None,
        project_id: str | None = None,
        exclude_failed_runs: bool = True,
    ) -> List[Dict[str, str]]:
        if scope not in self._allowed_scopes and scope != "all":
            raise ValueError(f"Invalid memory scope: {scope}")
        self.purge_expired()
        qvec = _embed_text(query, self.embedding_dim)
        cur = self._conn.cursor()
        clauses = []
        params: list = []
        if not include_quarantined:
            clauses.append("status = ?")
            params.append("active")
        if scope != "all":
            clauses.append("scope = ?")
            params.append(scope)
        if min_confidence is not None:
            clauses.append("(confidence IS NULL OR confidence >= ?)")
            params.append(min_confidence)
        if user_id:
            clauses.append("(user_id IS NULL OR user_id = ?)")
            params.append(user_id)
        if project_id:
            clauses.append("(project_id IS NULL OR project_id = ?)")
            params.append(project_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cur.execute(f"SELECT id, kind, content, embedding, created_at, tags FROM memories {where}", params)
        rows = cur.fetchall()
        failed_runs = set()
        if exclude_failed_runs:
            try:
                cur.execute("SELECT run_id FROM task_runs WHERE status IN ('error','failed','stopped')")
                failed_runs = {row[0] for row in cur.fetchall() if row[0]}
            except Exception:
                failed_runs = set()
        scored = []
        for memory_id, kind, content, emb_json, created_at, tags_blob in rows:
            try:
                emb = json.loads(emb_json)
            except Exception:
                continue
            # ACL filter
            try:
                cur.execute("SELECT acl FROM memories WHERE id=?", (memory_id,))
                acl_blob = cur.fetchone()
                if acl_blob and acl_blob[0]:
                    acl = json.loads(acl_blob[0])
                    users = acl.get("users") or []
                    if user_id and users and user_id not in users:
                        continue
            except Exception:
                pass
            if exclude_failed_runs and failed_runs:
                try:
                    cur.execute("SELECT run_id FROM memory_refs WHERE memory_id=?", (memory_id,))
                    refs = [row[0] for row in cur.fetchall() if row[0]]
                    if any(r in failed_runs for r in refs):
                        continue
                except Exception:
                    pass
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
