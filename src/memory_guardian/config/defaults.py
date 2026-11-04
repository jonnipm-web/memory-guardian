"""Default configuration values."""

DEFAULT_CONFIG: dict = {
    "monitoring": {
        "interval_seconds": 60,
        "snapshot_interval_seconds": 300,
        "history_retention_days": 30,
    },
    "policy": {
        "readonly_mode": True,
        "dry_run": True,
        "max_memory_mb_before_action": 28000,
        "min_risk_level_for_action": "high",
        "protected_names": [],
        "protected_patterns": [],
        "allowlist": [],
        "allowlist_patterns": [],
    },
    "alerts": {
        "memory_warning_percent": 85,
        "memory_critical_percent": 95,
        "swap_warning_percent": 50,
        "log_level": "INFO",
    },
    "output": {
        "reports_dir": "~/.memory-guardian/reports",
        "history_db": "~/.memory-guardian/history.db",
        "log_file": "~/.memory-guardian/memory-guardian.log",
    },
    "daemon": {
        "pid_file": "~/.memory-guardian/daemon.pid",
        "enabled": False,
    },
}
