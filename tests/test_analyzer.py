"""Tests for the MemoryAnalyzer."""
import time

import pytest

from memory_guardian.core.analyzer import MemoryAnalyzer, _LEAK_MIN_SNAPSHOTS
from memory_guardian.models.process import ProcessStatus, RiskLevel


def test_analyze_no_alerts_on_healthy_snapshot(make_snapshot):
    analyzer = MemoryAnalyzer()
    snap = make_snapshot(memory_pct=40.0)
    result = analyzer.analyze(snap)
    assert not result.alerts
    assert not result.zombie_processes
    assert not result.potential_leaks


def test_analyze_high_memory_alert(make_snapshot):
    analyzer = MemoryAnalyzer()
    snap = make_snapshot(memory_pct=90.0)
    result = analyzer.analyze(snap)
    assert any("WARNING" in a or "CRITICAL" in a for a in result.alerts)


def test_analyze_critical_memory_alert(make_snapshot):
    analyzer = MemoryAnalyzer()
    snap = make_snapshot(memory_pct=96.0)
    result = analyzer.analyze(snap)
    assert any("CRITICAL" in a for a in result.alerts)


def test_zombie_detected(make_snapshot, make_process):
    analyzer = MemoryAnalyzer()
    zombie = make_process(pid=999, status=ProcessStatus.ZOMBIE)
    snap = make_snapshot(processes=[zombie])
    result = analyzer.analyze(snap)
    assert result.zombie_processes
    assert result.zombie_processes[0].pid == 999
    assert any("zombie" in a.lower() for a in result.alerts)


def test_no_leak_on_first_snapshot(make_snapshot, make_process):
    analyzer = MemoryAnalyzer()
    proc = make_process(pid=100, memory_mb=200.0)
    snap = make_snapshot(processes=[proc])
    result = analyzer.analyze(snap)
    assert not result.potential_leaks


def test_sustained_growth_flagged_as_leak(make_snapshot, make_process):
    analyzer = MemoryAnalyzer()
    # Feed _LEAK_MIN_SNAPSHOTS + 1 snapshots with growing memory
    for i in range(_LEAK_MIN_SNAPSHOTS + 2):
        mb = 200.0 + i * 50
        proc = make_process(pid=100, memory_mb=mb)
        snap = make_snapshot(processes=[proc])
        analyzer.analyze(snap)

    result = analyzer.analyze(make_snapshot(processes=[make_process(pid=100, memory_mb=600.0)]))
    assert any(p.pid == 100 for p, _ in result.potential_leaks)


def test_classify_zombie_risk(make_process):
    analyzer = MemoryAnalyzer()
    zombie = make_process(pid=5, status=ProcessStatus.ZOMBIE, memory_mb=10.0)
    level, reasons = analyzer.classify_process_risk(zombie)
    assert level == RiskLevel.HIGH
    assert any("zombie" in r.lower() for r in reasons)


def test_classify_critical_memory(make_process):
    analyzer = MemoryAnalyzer()
    heavy = make_process(pid=6, memory_mb=2000.0)
    level, reasons = analyzer.classify_process_risk(heavy)
    assert level == RiskLevel.CRITICAL


def test_classify_no_risk_on_normal_process(make_process):
    analyzer = MemoryAnalyzer()
    normal = make_process(pid=7, memory_mb=50.0, cpu_percent=5.0)
    level, reasons = analyzer.classify_process_risk(normal)
    assert level == RiskLevel.NONE
