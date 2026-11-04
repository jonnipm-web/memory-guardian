"""Tests for the HistoryStore."""
import tempfile
import time
from pathlib import Path

import pytest

from memory_guardian.history.store import HistoryStore


def test_save_and_retrieve(make_snapshot):
    with tempfile.TemporaryDirectory() as tmp:
        store = HistoryStore(Path(tmp) / "test.db")
        snap = make_snapshot(memory_pct=55.0)
        rowid = store.save(snap)
        assert rowid > 0
        rows = store.recent(limit=10)
        assert len(rows) == 1
        assert rows[0]["memory_pct"] == pytest.approx(55.0, abs=0.1)


def test_memory_trend_returns_time_ordered(make_snapshot):
    with tempfile.TemporaryDirectory() as tmp:
        store = HistoryStore(Path(tmp) / "test.db")
        for pct in [40.0, 50.0, 60.0]:
            store.save(make_snapshot(memory_pct=pct))
        trend = store.memory_trend(hours=1)
        assert len(trend) == 3
        pcts = [r["memory_pct"] for r in trend]
        assert pcts == sorted(pcts)


def test_purge_removes_old_records(make_snapshot):
    with tempfile.TemporaryDirectory() as tmp:
        store = HistoryStore(Path(tmp) / "test.db")
        store.save(make_snapshot())
        # Artificially age the record
        import sqlite3
        conn = sqlite3.connect(str(Path(tmp) / "test.db"))
        conn.execute(
            "UPDATE snapshots SET recorded_at = '2000-01-01T00:00:00'"
        )
        conn.commit()
        conn.close()
        removed = store.purge_old(retention_days=1)
        assert removed == 1
        assert store.recent() == []


def test_multiple_saves_dont_conflict(make_snapshot):
    with tempfile.TemporaryDirectory() as tmp:
        store = HistoryStore(Path(tmp) / "test.db")
        for _ in range(5):
            store.save(make_snapshot())
        assert len(store.recent(limit=10)) == 5
