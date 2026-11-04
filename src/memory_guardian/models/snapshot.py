"""Memory snapshot models."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from .process import ProcessInfo


@dataclass
class MemoryStats:
    total_mb: float
    available_mb: float
    used_mb: float
    percent: float

    def to_dict(self) -> dict:
        return {
            "total_mb": round(self.total_mb, 1),
            "available_mb": round(self.available_mb, 1),
            "used_mb": round(self.used_mb, 1),
            "percent": round(self.percent, 1),
        }


@dataclass
class SwapStats:
    total_mb: float
    used_mb: float
    free_mb: float
    percent: float

    def to_dict(self) -> dict:
        return {
            "total_mb": round(self.total_mb, 1),
            "used_mb": round(self.used_mb, 1),
            "free_mb": round(self.free_mb, 1),
            "percent": round(self.percent, 1),
        }


@dataclass
class SystemSnapshot:
    timestamp: float
    memory: MemoryStats
    swap: SwapStats
    cpu_percent: float
    processes: List[ProcessInfo] = field(default_factory=list)
    label: Optional[str] = None

    @property
    def top_memory_processes(self) -> List[ProcessInfo]:
        return sorted(self.processes, key=lambda p: p.memory_mb, reverse=True)[:20]

    @property
    def top_cpu_processes(self) -> List[ProcessInfo]:
        return sorted(self.processes, key=lambda p: p.cpu_percent, reverse=True)[:20]

    def total_process_memory_mb(self) -> float:
        return sum(p.memory_mb for p in self.processes)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "label": self.label,
            "memory": self.memory.to_dict(),
            "swap": self.swap.to_dict(),
            "cpu_percent": round(self.cpu_percent, 1),
            "process_count": len(self.processes),
            "total_process_memory_mb": round(self.total_process_memory_mb(), 1),
        }
