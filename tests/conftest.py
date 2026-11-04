"""Shared pytest fixtures."""
import time
from unittest.mock import MagicMock

import psutil
import pytest

from memory_guardian.models.process import ProcessInfo, ProcessStatus
from memory_guardian.models.snapshot import MemoryStats, SwapStats, SystemSnapshot


def _make_process(
    pid: int = 1234,
    name: str = "test_app.exe",
    status: ProcessStatus = ProcessStatus.RUNNING,
    cpu_percent: float = 1.0,
    memory_mb: float = 100.0,
    age_hours: float = 0.5,
) -> ProcessInfo:
    return ProcessInfo(
        pid=pid,
        name=name,
        status=status,
        cpu_percent=cpu_percent,
        memory_mb=memory_mb,
        memory_percent=memory_mb / 32768 * 100,
        create_time=time.time() - age_hours * 3600,
        cmdline=[name],
        username="testuser",
        num_threads=4,
    )


def _make_snapshot(
    memory_pct: float = 50.0,
    processes: list = None,
) -> SystemSnapshot:
    total = 32768.0
    used = total * memory_pct / 100
    return SystemSnapshot(
        timestamp=time.time(),
        memory=MemoryStats(
            total_mb=total,
            available_mb=total - used,
            used_mb=used,
            percent=memory_pct,
        ),
        swap=SwapStats(total_mb=16384.0, used_mb=0.0, free_mb=16384.0, percent=0.0),
        cpu_percent=10.0,
        processes=processes or [],
    )


@pytest.fixture
def make_process():
    return _make_process


@pytest.fixture
def make_snapshot():
    return _make_snapshot
