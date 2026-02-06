from __future__ import annotations

import time
import json
from typing import List, Dict


class A2ABus:
    def __init__(self, memory) -> None:
        self.memory = memory
        self._init()

    def _init(self) -> None:
        cur = self.memory._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS a2a_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                message TEXT NOT NULL
            )
            """
        )
        self.memory._conn.commit()

    def send(self, sender: str, receiver: str, message: str) -> int:
        cur = self.memory._conn.cursor()
        cur.execute(
            "INSERT INTO a2a_messages (timestamp, sender, receiver, message) VALUES (?, ?, ?, ?)",
            (time.time(), sender, receiver, message),
        )
        self.memory._conn.commit()
        return cur.lastrowid

    def recent(self, limit: int = 20) -> List[Dict[str, str]]:
        cur = self.memory._conn.cursor()
        cur.execute(
            "SELECT timestamp, sender, receiver, message FROM a2a_messages ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {
                "timestamp": r[0],
                "sender": r[1],
                "receiver": r[2],
                "message": r[3],
            }
            for r in rows
        ]


class Handoff:
    def __init__(self, to: str, message: str) -> None:
        self.to = to
        self.message = message


class Result:
    def __init__(self, message: str = "", handoff_to: str | None = None) -> None:
        self.message = message
        self.handoff_to = handoff_to
