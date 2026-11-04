"""Memory and process anomaly analyzer."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..models.process import ProcessInfo, ProcessStatus, RiskLevel
from ..models.snapshot import SystemSnapshot

logger = logging.getLogger(__name__)

_IDLE_CPU_THRESHOLD = 0.5        # % — below this = effectively idle
_IDLE_MIN_AGE_HOURS = 1.0        # process must be at least this old
_LEAK_MIN_SNAPSHOTS = 3          # need at least N samples to flag a leak
_LEAK_GROWTH_RATIO = 1.15        # 15 % growth across window
_LEAK_MIN_MB_GROWTH = 50.0       # ignore tiny absolute growth
_HIGH_MEM_MB = 500.0
_CRITICAL_MEM_MB = 1500.0
_ZOMBIE_STATUS = {ProcessStatus.ZOMBIE}
_WAITING_STATUS = {ProcessStatus.WAITING, ProcessStatus.SLEEPING}


@dataclass
class GrowthRecord:
    pid: int
    name: str
    readings: List[Tuple[float, float]] = field(default_factory=list)  # (ts, mb)

    def add(self, timestamp: float, memory_mb: float) -> None:
        self.readings.append((timestamp, memory_mb))
        if len(self.readings) > 60:
            self.readings = self.readings[-60:]

    @property
    def growth_mb(self) -> float:
        if len(self.readings) < 2:
            return 0.0
        return self.readings[-1][1] - self.readings[0][1]

    @property
    def growth_ratio(self) -> float:
        if len(self.readings) < 2 or self.readings[0][1] < 1.0:
            return 1.0
        return self.readings[-1][1] / self.readings[0][1]

    @property
    def is_sustained_growth(self) -> bool:
        if len(self.readings) < _LEAK_MIN_SNAPSHOTS:
            return False
        monotone = sum(
            1 for i in range(1, len(self.readings))
            if self.readings[i][1] >= self.readings[i - 1][1]
        )
        required = max(_LEAK_MIN_SNAPSHOTS - 1, int(len(self.readings) * 0.75))
        return monotone >= required


@dataclass
class AnalysisResult:
    snapshot_time: float
    total_memory_percent: float
    high_memory_processes: List[ProcessInfo] = field(default_factory=list)
    potential_leaks: List[Tuple[ProcessInfo, str]] = field(default_factory=list)
    zombie_processes: List[ProcessInfo] = field(default_factory=list)
    idle_high_memory: List[ProcessInfo] = field(default_factory=list)
    alerts: List[str] = field(default_factory=list)

    def has_critical_issues(self) -> bool:
        return bool(self.zombie_processes) or self.total_memory_percent > 90

    def to_dict(self) -> dict:
        return {
            "snapshot_time": self.snapshot_time,
            "total_memory_percent": round(self.total_memory_percent, 1),
            "high_memory_count": len(self.high_memory_processes),
            "potential_leak_count": len(self.potential_leaks),
            "zombie_count": len(self.zombie_processes),
            "idle_high_memory_count": len(self.idle_high_memory),
            "alerts": self.alerts,
            "high_memory_processes": [p.to_dict() for p in self.high_memory_processes],
            "potential_leaks": [
                {**p.to_dict(), "reason": r} for p, r in self.potential_leaks
            ],
            "zombie_processes": [p.to_dict() for p in self.zombie_processes],
            "idle_high_memory": [p.to_dict() for p in self.idle_high_memory],
        }


class MemoryAnalyzer:
    """Analyzes system snapshots to detect memory problems."""

    def __init__(self) -> None:
        self._growth_tracker: Dict[int, GrowthRecord] = {}
        self._last_cleanup = time.time()

    def _cleanup_stale(self, active_pids: set) -> None:
        if time.time() - self._last_cleanup < 300:
            return
        stale = [pid for pid in self._growth_tracker if pid not in active_pids]
        for pid in stale:
            del self._growth_tracker[pid]
        self._last_cleanup = time.time()

    def _update_growth(self, processes: List[ProcessInfo]) -> None:
        active = {p.pid for p in processes}
        self._cleanup_stale(active)
        for proc in processes:
            if proc.pid not in self._growth_tracker:
                self._growth_tracker[proc.pid] = GrowthRecord(pid=proc.pid, name=proc.name)
            self._growth_tracker[proc.pid].add(time.time(), proc.memory_mb)

    def _detect_leaks(
        self, processes: List[ProcessInfo]
    ) -> List[Tuple[ProcessInfo, str]]:
        leaks = []
        for proc in processes:
            rec = self._growth_tracker.get(proc.pid)
            if rec is None or not rec.is_sustained_growth:
                continue
            if rec.growth_mb < _LEAK_MIN_MB_GROWTH and rec.growth_ratio < _LEAK_GROWTH_RATIO:
                continue
            reason = (
                f"Sustained growth: +{rec.growth_mb:.0f} MB "
                f"(×{rec.growth_ratio:.2f}) across {len(rec.readings)} samples"
            )
            leaks.append((proc, reason))
        return leaks

    def _find_idle_heavy(self, processes: List[ProcessInfo]) -> List[ProcessInfo]:
        return [
            p for p in processes
            if p.cpu_percent < _IDLE_CPU_THRESHOLD
            and p.memory_mb > _HIGH_MEM_MB
            and p.age_hours >= _IDLE_MIN_AGE_HOURS
            and p.status in _WAITING_STATUS
        ]

    def analyze(self, snapshot: SystemSnapshot) -> AnalysisResult:
        """Full analysis of a snapshot. Call after each collection cycle."""
        self._update_growth(snapshot.processes)

        high_mem = sorted(
            [p for p in snapshot.processes if p.memory_mb >= _HIGH_MEM_MB],
            key=lambda p: p.memory_mb, reverse=True,
        )[:15]
        zombies = [p for p in snapshot.processes if p.status in _ZOMBIE_STATUS]
        idle_heavy = self._find_idle_heavy(snapshot.processes)
        leaks = self._detect_leaks(snapshot.processes)

        alerts: List[str] = []
        pct = snapshot.memory.percent
        if pct >= 95:
            alerts.append(f"CRITICAL: RAM at {pct:.0f}% — system may become unstable")
        elif pct >= 85:
            alerts.append(f"WARNING: RAM at {pct:.0f}%")
        if zombies:
            alerts.append(f"{len(zombies)} zombie process(es) detected")
        if leaks:
            alerts.append(f"{len(leaks)} potential memory leak(s) detected")
        if snapshot.swap.percent > 50:
            alerts.append(f"Swap elevated: {snapshot.swap.percent:.0f}%")

        return AnalysisResult(
            snapshot_time=snapshot.timestamp,
            total_memory_percent=pct,
            high_memory_processes=high_mem,
            potential_leaks=leaks,
            zombie_processes=zombies,
            idle_high_memory=idle_heavy[:10],
            alerts=alerts,
        )

    def classify_process_risk(
        self, proc: ProcessInfo
    ) -> Tuple[RiskLevel, List[str]]:
        """Return (risk_level, reasons) for a single process."""
        reasons: List[str] = []
        level = RiskLevel.NONE

        if proc.status in _ZOMBIE_STATUS:
            reasons.append("Zombie process")
            level = RiskLevel.HIGH

        if proc.memory_mb >= _CRITICAL_MEM_MB:
            reasons.append(f"Very high memory usage: {proc.memory_mb:.0f} MB")
            level = RiskLevel.CRITICAL
        elif proc.memory_mb >= _HIGH_MEM_MB:
            reasons.append(f"High memory usage: {proc.memory_mb:.0f} MB")
            if level == RiskLevel.NONE:
                level = RiskLevel.MEDIUM

        rec = self._growth_tracker.get(proc.pid)
        if rec and rec.is_sustained_growth and rec.growth_mb >= _LEAK_MIN_MB_GROWTH:
            reasons.append(f"Possible memory leak: +{rec.growth_mb:.0f} MB growth")
            if level in (RiskLevel.NONE, RiskLevel.LOW):
                level = RiskLevel.MEDIUM

        if (
            proc.cpu_percent < _IDLE_CPU_THRESHOLD
            and proc.memory_mb > _HIGH_MEM_MB
            and proc.age_hours >= _IDLE_MIN_AGE_HOURS
        ):
            reasons.append("Idle process holding significant memory")
            if level == RiskLevel.NONE:
                level = RiskLevel.LOW

        return level, reasons
