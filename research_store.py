from __future__ import annotations

import time
import sqlite3
from typing import List, Dict


class ResearchStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._init()

    def _init(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS hypotheses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                text TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                title TEXT NOT NULL,
                plan TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT
            )
            """
        )
        self._conn.commit()

    def add_hypothesis(self, text: str, status: str = "proposed") -> int:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO hypotheses (created_at, text, status) VALUES (?, ?, ?)",
            (time.time(), text, status),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_hypotheses(self, limit: int = 20) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, created_at, text, status FROM hypotheses ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {"id": rid, "created_at": created_at, "text": text, "status": status}
            for (rid, created_at, text, status) in rows
        ]

    def add_experiment(self, title: str, plan: str, status: str = "planned") -> int:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO experiments (created_at, title, plan, status, notes) VALUES (?, ?, ?, ?, ?)",
            (time.time(), title, plan, status, ""),
        )
        self._conn.commit()
        return cur.lastrowid

    def update_experiment(self, exp_id: int, status: str, notes: str) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE experiments SET status=?, notes=? WHERE id=?",
            (status, notes, exp_id),
        )
        self._conn.commit()

    def list_experiments(self, limit: int = 20) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, created_at, title, plan, status, notes FROM experiments ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": rid,
                "created_at": created_at,
                "title": title,
                "plan": plan,
                "status": status,
                "notes": notes or "",
            }
            for (rid, created_at, title, plan, status, notes) in rows
        ]
