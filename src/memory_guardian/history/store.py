"""SQLite-based historical snapshot store."""
from __future__ import annotations

import datetime
import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List, Optional

from ..models.snapshot import SystemSnapshot

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at TEXT    NOT NULL,
    label       TEXT,
    memory_pct  REAL    NOT NULL,
    available_mb REAL   NOT NULL,
    total_mb    REAL    NOT NULL,
    swap_pct    REAL    NOT NULL,
    cpu_pct     REAL    NOT NULL,
    process_count INTEGER NOT NULL,
    payload     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_recorded_at ON snapshots (recorded_at);
"""


class HistoryStore:
    """Persist and query system snapshots in a local SQLite database."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def save(self, snapshot: SystemSnapshot) -> int:
        ts = datetime.datetime.fromtimestamp(snapshot.timestamp).isoformat()
        payload = json.dumps(snapshot.to_dict())
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO snapshots
                  (recorded_at, label, memory_pct, available_mb, total_mb,
                   swap_pct, cpu_pct, process_count, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    snapshot.label,
                    snapshot.memory.percent,
                    snapshot.memory.available_mb,
                    snapshot.memory.total_mb,
                    snapshot.swap.percent,
                    snapshot.cpu_percent,
                    len(snapshot.processes),
                    payload,
                ),
            )
            return cur.lastrowid  # type: ignore

    def recent(self, limit: int = 100) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM snapshots ORDER BY recorded_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def memory_trend(self, hours: int = 24) -> List[dict]:
        since = (
            datetime.datetime.now() - datetime.timedelta(hours=hours)
        ).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT recorded_at, memory_pct, available_mb, swap_pct, cpu_pct
                FROM snapshots
                WHERE recorded_at >= ?
                ORDER BY recorded_at ASC
                """,
                (since,),
            ).fetchall()
        return [dict(r) for r in rows]

    def purge_old(self, retention_days: int = 30) -> int:
        cutoff = (
            datetime.datetime.now() - datetime.timedelta(days=retention_days)
        ).isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM snapshots WHERE recorded_at < ?", (cutoff,)
            )
            return cur.rowcount
