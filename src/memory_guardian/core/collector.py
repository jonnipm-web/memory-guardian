"""System data collector using psutil."""
from __future__ import annotations

import logging
import time
from typing import List, Optional

import psutil

from ..models.process import ProcessInfo, ProcessStatus
from ..models.snapshot import MemoryStats, SwapStats, SystemSnapshot

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    "running": ProcessStatus.RUNNING,
    "sleeping": ProcessStatus.SLEEPING,
    "idle": ProcessStatus.IDLE,
    "waiting": ProcessStatus.WAITING,
    "zombie": ProcessStatus.ZOMBIE,
    "stopped": ProcessStatus.STOPPED,
    "disk-sleep": ProcessStatus.WAITING,
}


def _map_status(raw: str) -> ProcessStatus:
    return _STATUS_MAP.get(raw.lower(), ProcessStatus.UNKNOWN)


def _collect_process(proc: psutil.Process) -> Optional[ProcessInfo]:
    try:
        with proc.oneshot():
            name = proc.name()
            status = _map_status(proc.status())
            cpu = proc.cpu_percent(interval=None)
            mem_info = proc.memory_info()
            mem_mb = mem_info.rss / 1024 / 1024
            mem_pct = proc.memory_percent()
            create_time = proc.create_time()
            num_threads = proc.num_threads()
            try:
                cmdline = proc.cmdline()
            except (psutil.AccessDenied, psutil.ZombieProcess):
                cmdline = []
            try:
                username = proc.username()
            except (psutil.AccessDenied, psutil.ZombieProcess):
                username = None
            open_files = 0   # skipped — open_files() is very slow on Windows
            connections = 0  # skipped — net_connections() requires elevated rights

        return ProcessInfo(
            pid=proc.pid,
            name=name,
            status=status,
            cpu_percent=cpu,
            memory_mb=mem_mb,
            memory_percent=mem_pct,
            create_time=create_time,
            cmdline=cmdline,
            username=username,
            num_threads=num_threads,
            open_files_count=open_files,
            connections_count=connections,
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None
    except Exception as exc:
        logger.debug("Could not collect process %d: %s", proc.pid, exc)
        return None


class SystemCollector:
    """Collects system memory and process information using psutil."""

    def __init__(self, cpu_interval: float = 0.1) -> None:
        self._cpu_interval = cpu_interval
        self._initialized = False

    def _prime_cpu_counters(self) -> None:
        """Call cpu_percent once to initialize the per-process counters."""
        if self._initialized:
            return
        for proc in psutil.process_iter():
            try:
                proc.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        self._initialized = True

    def collect_snapshot(self, label: Optional[str] = None) -> SystemSnapshot:
        """Take a full system snapshot (memory + all processes)."""
        self._prime_cpu_counters()
        time.sleep(self._cpu_interval)

        vm = psutil.virtual_memory()
        mem = MemoryStats(
            total_mb=vm.total / 1024 / 1024,
            available_mb=vm.available / 1024 / 1024,
            used_mb=vm.used / 1024 / 1024,
            percent=vm.percent,
        )

        sw = psutil.swap_memory()
        swap = SwapStats(
            total_mb=sw.total / 1024 / 1024,
            used_mb=sw.used / 1024 / 1024,
            free_mb=sw.free / 1024 / 1024,
            percent=sw.percent,
        )

        cpu_pct = psutil.cpu_percent(interval=None)

        processes: List[ProcessInfo] = []
        for proc in psutil.process_iter():
            info = _collect_process(proc)
            if info is not None:
                processes.append(info)

        return SystemSnapshot(
            timestamp=time.time(),
            memory=mem,
            swap=swap,
            cpu_percent=cpu_pct,
            processes=processes,
            label=label,
        )

    def collect_memory_only(self) -> MemoryStats:
        """Lightweight memory-only collection for high-frequency polling."""
        vm = psutil.virtual_memory()
        return MemoryStats(
            total_mb=vm.total / 1024 / 1024,
            available_mb=vm.available / 1024 / 1024,
            used_mb=vm.used / 1024 / 1024,
            percent=vm.percent,
        )
