"""Process data models."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ProcessStatus(str, Enum):
    RUNNING = "running"
    SLEEPING = "sleeping"
    IDLE = "idle"
    WAITING = "waiting"
    ZOMBIE = "zombie"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __lt__(self, other: "RiskLevel") -> bool:
        order = list(RiskLevel)
        return order.index(self) < order.index(other)

    def __le__(self, other: "RiskLevel") -> bool:
        return self == other or self < other

    def __gt__(self, other: "RiskLevel") -> bool:
        return not self <= other

    def __ge__(self, other: "RiskLevel") -> bool:
        return not self < other


@dataclass
class ProcessInfo:
    pid: int
    name: str
    status: ProcessStatus
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    create_time: float
    cmdline: List[str] = field(default_factory=list)
    username: Optional[str] = None
    num_threads: int = 0
    open_files_count: int = 0
    connections_count: int = 0

    @property
    def age_seconds(self) -> float:
        return time.time() - self.create_time

    @property
    def age_hours(self) -> float:
        return self.age_seconds / 3600

    @property
    def exe_lower(self) -> str:
        return self.name.lower()

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "name": self.name,
            "status": self.status.value,
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_mb": round(self.memory_mb, 2),
            "memory_percent": round(self.memory_percent, 2),
            "age_hours": round(self.age_hours, 2),
            "num_threads": self.num_threads,
        }


@dataclass
class ProcessRisk:
    process: ProcessInfo
    risk_level: RiskLevel
    reasons: List[str] = field(default_factory=list)
    action_recommended: str = "none"
    is_protected: bool = False
    is_allowlisted: bool = False

    def to_dict(self) -> dict:
        return {
            **self.process.to_dict(),
            "risk_level": self.risk_level.value,
            "reasons": self.reasons,
            "action_recommended": self.action_recommended,
            "is_protected": self.is_protected,
            "is_allowlisted": self.is_allowlisted,
        }
