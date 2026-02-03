from __future__ import annotations

import sqlite3
from typing import List, Dict


class GraphStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._init()

    def _init(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                src_id INTEGER NOT NULL,
                rel TEXT NOT NULL,
                dst_id INTEGER NOT NULL
            )
            """
        )
        self.conn.commit()

    def add_entity(self, name: str, entity_type: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO graph_entities (name, entity_type) VALUES (?, ?)",
            (name, entity_type),
        )
        self.conn.commit()
        return cur.lastrowid

    def add_edge(self, src_id: int, rel: str, dst_id: int) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO graph_edges (src_id, rel, dst_id) VALUES (?, ?, ?)",
            (src_id, rel, dst_id),
        )
        self.conn.commit()
        return cur.lastrowid

    def neighbors(self, name: str) -> List[Dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM graph_entities WHERE name = ?", (name,))
        row = cur.fetchone()
        if not row:
            return []
        entity_id = row[0]
        cur.execute(
            """
            SELECT e2.name, e2.entity_type, g.rel
            FROM graph_edges g
            JOIN graph_entities e2 ON e2.id = g.dst_id
            WHERE g.src_id = ?
            """,
            (entity_id,),
        )
        results = []
        for name, etype, rel in cur.fetchall():
            results.append({"name": name, "type": etype, "rel": rel})
        return results
