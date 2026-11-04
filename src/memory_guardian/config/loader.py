"""YAML configuration loader with deep-merge of defaults."""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .defaults import DEFAULT_CONFIG
from ..core.policy import PolicyConfig

logger = logging.getLogger(__name__)

_SEARCH_PATHS = [
    Path.home() / ".memory-guardian" / "config.yaml",
    Path.cwd() / "memory-guardian.yaml",
    Path.cwd() / ".memory-guardian.yaml",
]


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load and merge configuration. Falls back to defaults if no file found."""
    cfg = copy.deepcopy(DEFAULT_CONFIG)

    candidates = [path] if path else _SEARCH_PATHS
    for candidate in candidates:
        if candidate and candidate.exists():
            try:
                with candidate.open("r", encoding="utf-8") as fh:
                    user_cfg = yaml.safe_load(fh) or {}
                cfg = _deep_merge(cfg, user_cfg)
                logger.info("Loaded config from %s", candidate)
            except Exception as exc:
                logger.warning("Could not load config from %s: %s", candidate, exc)
            break

    return cfg


def build_policy_config(cfg: Dict[str, Any]) -> PolicyConfig:
    p = cfg.get("policy", {})
    return PolicyConfig(
        readonly_mode=p.get("readonly_mode", True),
        dry_run=p.get("dry_run", True),
        extra_protected_names=p.get("protected_names", []),
        extra_protected_patterns=p.get("protected_patterns", []),
        allowlist=p.get("allowlist", []),
        allowlist_patterns=p.get("allowlist_patterns", []),
        max_memory_mb_before_action=p.get("max_memory_mb_before_action", 28000.0),
        min_risk_level_for_action=p.get("min_risk_level_for_action", "high"),
    )
