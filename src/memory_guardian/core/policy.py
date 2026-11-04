"""Security policy engine — decides what may be terminated."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set

from ..models.process import ProcessInfo, ProcessRisk, RiskLevel

logger = logging.getLogger(__name__)

# Hard-coded protected names (Windows system + security essentials).
# These can never be killed regardless of config.
_ALWAYS_PROTECTED_NAMES: Set[str] = {
    # Windows core
    "system", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "lsaiso.exe", "svchost.exe",
    "dwm.exe", "ntoskrnl.exe", "registry", "memory compression",
    # Security / AV
    "msseces.exe", "msmpeng.exe", "securityhealthservice.exe",
    "mrt.exe", "smartscreen.exe", "audiodg.exe",
    # Windows Update / Store
    "wuauclt.exe", "musnotification.exe", "trustedinstaller.exe",
    # Explorer shell
    "explorer.exe", "shellexperiencehost.exe", "startmenuexperiencehost.exe",
    # Task scheduler
    "taskhost.exe", "taskhostw.exe", "taskeng.exe",
}

# Protected patterns — regex applied to process name (lowercase)
_ALWAYS_PROTECTED_PATTERNS: List[str] = [
    r"^antivirus",
    r"^avg",
    r"^avast",
    r"^bitdefender",
    r"^kaspersky",
    r"^malwarebytes",
    r"^norton",
    r"^mcafee",
    r"^eset",
    r"^sophos",
    r"^windowsdefender",
    # IDEs and dev tools — users invest state in these
    r"^code(\.exe)?$",     # VS Code
    r"^devenv$",           # Visual Studio
    r"^idea64",            # IntelliJ
    r"^pycharm",
    r"^webstorm",
    r"^rider",
    r"^clion",
    r"^studio64",          # Android Studio
    r"^eclipse",
    # Agents and orchestrators
    r"^claude",
    r"^cursor",
    r"^aao",
    r"^copilot",
    # MetaTrader
    r"^terminal64",
    r"^terminal\.exe",
    r"^metatrader",
    r"^mt5",
    r"^mt4",
    # Python / Node build processes
    r"^python",
    r"^python3",
    r"^node",
    r"^npm",
    r"^pytest",
    r"^coverage",
    # Databases
    r"^postgres",
    r"^mysqld",
    r"^mongod",
    r"^redis",
    r"^sqlite",
    # VMs / containers
    r"^vmware",
    r"^virtualbox",
    r"^docker",
    r"^wslhost",
    r"^vmmem",
]

_COMPILED_PROTECTED = [re.compile(p) for p in _ALWAYS_PROTECTED_PATTERNS]


def _is_name_protected(name: str) -> bool:
    lower = name.lower()
    if lower in _ALWAYS_PROTECTED_NAMES:
        return True
    return any(pat.search(lower) for pat in _COMPILED_PROTECTED)


@dataclass
class PolicyConfig:
    """Runtime policy configuration loaded from YAML."""
    readonly_mode: bool = True
    dry_run: bool = True
    extra_protected_names: List[str] = field(default_factory=list)
    extra_protected_patterns: List[str] = field(default_factory=list)
    allowlist: List[str] = field(default_factory=list)
    allowlist_patterns: List[str] = field(default_factory=list)
    max_memory_mb_before_action: float = 28_000.0
    min_risk_level_for_action: str = "high"


class PolicyEngine:
    """Evaluates which processes may be acted upon and recommends actions."""

    def __init__(self, config: Optional[PolicyConfig] = None) -> None:
        self._cfg = config or PolicyConfig()
        self._extra_protected: Set[str] = {
            n.lower() for n in self._cfg.extra_protected_names
        }
        self._extra_patterns = [
            re.compile(p) for p in self._cfg.extra_protected_patterns
        ]
        self._allowlist: Set[str] = {n.lower() for n in self._cfg.allowlist}
        self._allowlist_patterns = [
            re.compile(p) for p in self._cfg.allowlist_patterns
        ]

    def is_protected(self, proc: ProcessInfo) -> bool:
        lower = proc.exe_lower
        if _is_name_protected(lower):
            return True
        if lower in self._extra_protected:
            return True
        return any(pat.search(lower) for pat in self._extra_patterns)

    def is_allowlisted(self, proc: ProcessInfo) -> bool:
        lower = proc.exe_lower
        if lower in self._allowlist:
            return True
        return any(pat.search(lower) for pat in self._allowlist_patterns)

    def evaluate(
        self,
        proc: ProcessInfo,
        risk_level: RiskLevel,
        reasons: List[str],
    ) -> ProcessRisk:
        protected = self.is_protected(proc)
        allowlisted = self.is_allowlisted(proc)

        if protected:
            action = "none (protected)"
        elif self._cfg.readonly_mode:
            action = "none (read-only mode)"
        elif self._cfg.dry_run:
            action = "dry-run: would terminate gracefully" if allowlisted else "none (not in allowlist)"
        else:
            action = "terminate gracefully" if allowlisted else "none (not in allowlist)"

        return ProcessRisk(
            process=proc,
            risk_level=risk_level,
            reasons=reasons,
            action_recommended=action,
            is_protected=protected,
            is_allowlisted=allowlisted,
        )

    def can_terminate(self, proc: ProcessInfo) -> tuple[bool, str]:
        """Return (allowed, reason) for a termination request."""
        if self._cfg.readonly_mode:
            return False, "Read-only mode is active"
        if self.is_protected(proc):
            return False, f"Process '{proc.name}' is protected"
        if not self.is_allowlisted(proc):
            return False, f"Process '{proc.name}' is not in the allowlist"
        return True, "OK"
