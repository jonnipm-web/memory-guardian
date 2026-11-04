"""Tests for config loading and merging."""
import tempfile
from pathlib import Path

import pytest
import yaml

from memory_guardian.config import build_policy_config, load_config
from memory_guardian.config.defaults import DEFAULT_CONFIG


def test_load_config_returns_defaults_when_no_file():
    cfg = load_config(Path("/nonexistent/path/config.yaml"))
    assert cfg["policy"]["readonly_mode"] is True
    assert cfg["policy"]["dry_run"] is True


def test_load_config_merges_user_values():
    with tempfile.NamedTemporaryFile(
        suffix=".yaml", mode="w", delete=False, encoding="utf-8"
    ) as f:
        yaml.dump({"policy": {"readonly_mode": False, "allowlist": ["app.exe"]}}, f)
        tmp = Path(f.name)

    cfg = load_config(tmp)
    assert cfg["policy"]["readonly_mode"] is False
    assert "app.exe" in cfg["policy"]["allowlist"]
    # untouched defaults still present
    assert cfg["policy"]["dry_run"] is True
    tmp.unlink()


def test_build_policy_config_from_cfg():
    cfg = load_config(Path("/nonexistent"))
    pc = build_policy_config(cfg)
    assert pc.readonly_mode is True
    assert pc.dry_run is True


def test_deep_merge_does_not_mutate_defaults():
    original_allowlist = DEFAULT_CONFIG["policy"]["allowlist"].copy()
    with tempfile.NamedTemporaryFile(
        suffix=".yaml", mode="w", delete=False, encoding="utf-8"
    ) as f:
        yaml.dump({"policy": {"allowlist": ["extra.exe"]}}, f)
        tmp = Path(f.name)
    load_config(tmp)
    assert DEFAULT_CONFIG["policy"]["allowlist"] == original_allowlist
    tmp.unlink()
