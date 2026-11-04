"""Tests for the PolicyEngine."""
import pytest

from memory_guardian.core.policy import PolicyConfig, PolicyEngine, _is_name_protected
from memory_guardian.models.process import ProcessStatus, RiskLevel


def test_system_process_is_always_protected(make_process):
    engine = PolicyEngine()
    lsass = make_process(pid=800, name="lsass.exe")
    assert engine.is_protected(lsass)


def test_ide_is_always_protected(make_process):
    engine = PolicyEngine()
    vscode = make_process(pid=900, name="Code.exe")
    assert engine.is_protected(vscode)


def test_metatrader_is_always_protected(make_process):
    engine = PolicyEngine()
    mt5 = make_process(pid=1100, name="terminal64.exe")
    assert engine.is_protected(mt5)


def test_python_runtime_is_protected(make_process):
    engine = PolicyEngine()
    py = make_process(pid=200, name="python.exe")
    assert engine.is_protected(py)


def test_unknown_app_not_protected(make_process):
    engine = PolicyEngine()
    app = make_process(pid=5000, name="my_random_app.exe")
    assert not engine.is_protected(app)


def test_allowlist_works(make_process):
    cfg = PolicyConfig(allowlist=["cleanup_tool.exe"])
    engine = PolicyEngine(cfg)
    app = make_process(pid=5001, name="cleanup_tool.exe")
    assert engine.is_allowlisted(app)


def test_allowlist_pattern_works(make_process):
    cfg = PolicyConfig(allowlist_patterns=[r"^temp_"])
    engine = PolicyEngine(cfg)
    app = make_process(pid=5002, name="temp_worker.exe")
    assert engine.is_allowlisted(app)


def test_readonly_prevents_termination(make_process):
    cfg = PolicyConfig(readonly_mode=True, allowlist=["app.exe"])
    engine = PolicyEngine(cfg)
    app = make_process(pid=5003, name="app.exe")
    allowed, reason = engine.can_terminate(app)
    assert not allowed
    assert "read-only" in reason.lower()


def test_not_in_allowlist_prevents_termination(make_process):
    cfg = PolicyConfig(readonly_mode=False, dry_run=False)
    engine = PolicyEngine(cfg)
    app = make_process(pid=5004, name="unknown.exe")
    allowed, reason = engine.can_terminate(app)
    assert not allowed
    assert "allowlist" in reason.lower()


def test_protected_process_cannot_be_terminated_even_in_allowlist(make_process):
    cfg = PolicyConfig(readonly_mode=False, dry_run=False, allowlist=["lsass.exe"])
    engine = PolicyEngine(cfg)
    lsass = make_process(pid=800, name="lsass.exe")
    allowed, reason = engine.can_terminate(lsass)
    assert not allowed
    assert "protected" in reason.lower()


def test_evaluate_returns_risk_object(make_process):
    engine = PolicyEngine()
    app = make_process(pid=5005, name="app.exe", memory_mb=800.0)
    risk = engine.evaluate(app, RiskLevel.HIGH, ["High memory"])
    assert risk.process.pid == 5005
    assert risk.risk_level == RiskLevel.HIGH
    assert "protected" not in risk.action_recommended or risk.is_protected
