"""Tests for the Reporter."""
import json
import tempfile
from pathlib import Path

from memory_guardian.core.analyzer import AnalysisResult
from memory_guardian.core.reporter import Reporter


def test_snapshot_summary_contains_expected_fields(make_snapshot):
    reporter = Reporter()
    snap = make_snapshot(memory_pct=65.0)
    output = reporter.snapshot_summary(snap)
    assert "RAM" in output
    assert "%" in output
    assert "Procs" in output


def test_analysis_report_shows_alerts(make_snapshot):
    reporter = Reporter()
    result = AnalysisResult(
        snapshot_time=__import__("time").time(),
        total_memory_percent=90.0,
        alerts=["WARNING: RAM at 90%"],
    )
    output = reporter.analysis_report(result)
    assert "WARNING" in output
    assert "90%" in output


def test_to_json_is_valid(make_snapshot):
    reporter = Reporter()
    snap = make_snapshot()
    result = AnalysisResult(
        snapshot_time=snap.timestamp,
        total_memory_percent=snap.memory.percent,
    )
    js = reporter.to_json(snap, result)
    data = json.loads(js)
    assert "snapshot" in data
    assert "analysis" in data


def test_save_report_creates_file(make_snapshot):
    reporter = Reporter()
    with tempfile.TemporaryDirectory() as tmp:
        path = reporter.save_report("hello world", Path(tmp), prefix="test")
        assert path.exists()
        assert path.read_text() == "hello world"


def test_save_json_report_creates_json_file(make_snapshot):
    reporter = Reporter()
    with tempfile.TemporaryDirectory() as tmp:
        path = reporter.save_json_report('{"x":1}', Path(tmp), prefix="json_test")
        assert path.suffix == ".json"
        assert path.exists()
