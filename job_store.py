from __future__ import annotations

import sqlite3
import time
from typing import List, Dict


class JobStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._init()

    def _init(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                status TEXT NOT NULL,
                command TEXT NOT NULL,
                result TEXT
            )
            """
        )
        self._conn.commit()

    def create(self, command: str) -> int:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO jobs (created_at, status, command) VALUES (?, ?, ?)",
            (time.time(), "running", command),
        )
        self._conn.commit()
        return cur.lastrowid

    def update(self, job_id: int, status: str, result: str = "") -> None:
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE jobs SET status=?, result=? WHERE id=?",
            (status, result, job_id),
        )
        self._conn.commit()

    def list(self, limit: int = 20) -> List[Dict[str, str]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, created_at, status, command, result FROM jobs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "created_at": r[1],
                "status": r[2],
                "command": r[3],
                "result": r[4] or "",
            }
            for r in rows
        ]
