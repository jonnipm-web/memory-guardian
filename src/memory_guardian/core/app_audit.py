"""Auditoria de múltiplos aplicativos — Claude Code, Codex, Chrome, Edge, ChatGPT."""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import psutil

# ---------------------------------------------------------------------------
# Perfis de aplicativos
# ---------------------------------------------------------------------------

@dataclass
class AppProfile:
    key: str
    display_name: str
    process_names: List[str]           # nomes exatos (lowercase)
    idle_cpu_threshold: float          # % CPU abaixo = ocioso
    min_age_hours: float               # ignorar processos recém-abertos
    # Substrings em cmdline que indicam processo auxiliar (não a sessão principal)
    helper_flags: List[str] = field(default_factory=list)
    # Se True, conta renderers separadamente (Chrome/Edge)
    count_tabs: bool = False


APP_PROFILES: Dict[str, AppProfile] = {
    "claude": AppProfile(
        key="claude",
        display_name="Claude Code",
        process_names=["claude.exe", "claude"],
        idle_cpu_threshold=2.0,
        min_age_hours=1.0,
        helper_flags=[
            "--type=renderer", "--type=gpu-process", "--type=utility",
            "--type=crashpad", "--type=broker",
        ],
    ),
    "codex": AppProfile(
        key="codex",
        display_name="Codex / OpenAI",
        process_names=[
            "codex.exe", "codex",
            "codex-computer-use-swift.exe",
            "codex-code-mode-host.exe",
            "codex-windows-sandbox-service.exe",
        ],
        idle_cpu_threshold=1.0,
        min_age_hours=2.0,
        helper_flags=["app-server", "--parent-pid"],
    ),
    "chatgpt": AppProfile(
        key="chatgpt",
        display_name="ChatGPT Desktop",
        process_names=["chatgpt.exe"],
        idle_cpu_threshold=1.0,
        min_age_hours=2.0,
        helper_flags=[
            "--type=renderer", "--type=gpu-process", "--type=utility",
            "--type=crashpad",
        ],
    ),
    "chrome": AppProfile(
        key="chrome",
        display_name="Google Chrome",
        process_names=["chrome.exe"],
        idle_cpu_threshold=0.5,
        min_age_hours=4.0,
        helper_flags=["--type=gpu-process", "--type=utility", "--type=crashpad"],
        count_tabs=True,
    ),
    "edge": AppProfile(
        key="edge",
        display_name="Microsoft Edge",
        process_names=["msedge.exe", "msedgewebview2.exe"],
        idle_cpu_threshold=0.5,
        min_age_hours=4.0,
        helper_flags=["--type=gpu-process", "--type=utility", "--type=crashpad"],
        count_tabs=True,
    ),
}

# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

class ProcKind:
    MAIN = "main"          # processo principal do app
    RENDERER = "renderer"  # aba/tab (Chrome/Edge)
    HELPER = "helper"      # utilitário interno (gpu, audio, node…)
    SESSION = "session"    # sessão CLI separada (Claude Code --output-format)


class ProcStatus:
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    YOUNG = "YOUNG"
    CURRENT = "CURRENT"


@dataclass
class AppProcess:
    pid: int
    name: str
    app_key: str
    kind: ProcKind
    status: str
    memory_mb: float
    cpu_percent: float
    age_seconds: float
    cmdline: List[str] = field(default_factory=list)
    is_current: bool = False

    @property
    def age_hours(self) -> float:
        return self.age_seconds / 3600

    @property
    def age_display(self) -> str:
        s = self.age_seconds
        if s < 120:
            return f"{s:.0f}s"
        if s < 3600:
            return f"{s/60:.0f}m"
        return f"{s/3600:.1f}h"

    @property
    def safe_to_close(self) -> bool:
        return self.status == ProcStatus.IDLE and not self.is_current

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "name": self.name,
            "app": self.app_key,
            "kind": self.kind,
            "status": self.status,
            "memory_mb": round(self.memory_mb, 1),
            "cpu_percent": round(self.cpu_percent, 2),
            "age_display": self.age_display,
            "safe_to_close": self.safe_to_close,
        }


@dataclass
class AppSummary:
    profile: AppProfile
    processes: List[AppProcess] = field(default_factory=list)

    @property
    def total_memory_mb(self) -> float:
        return sum(p.memory_mb for p in self.processes)

    @property
    def idle_sessions(self) -> List[AppProcess]:
        return [p for p in self.processes if p.safe_to_close
                and p.kind in (ProcKind.MAIN, ProcKind.SESSION)]

    @property
    def idle_tabs(self) -> List[AppProcess]:
        return [p for p in self.processes if p.safe_to_close
                and p.kind == ProcKind.RENDERER]

    @property
    def reclaimable_mb(self) -> float:
        return sum(p.memory_mb for p in self.idle_sessions)

    @property
    def tab_count(self) -> int:
        return sum(1 for p in self.processes if p.kind == ProcKind.RENDERER)

    def to_dict(self) -> dict:
        return {
            "app": self.profile.display_name,
            "total_memory_mb": round(self.total_memory_mb, 1),
            "process_count": len(self.processes),
            "tab_count": self.tab_count,
            "idle_session_count": len(self.idle_sessions),
            "reclaimable_mb": round(self.reclaimable_mb, 1),
            "processes": [p.to_dict() for p in self.processes],
        }


@dataclass
class MultiAppAuditResult:
    apps: Dict[str, AppSummary] = field(default_factory=dict)
    total_memory_mb: float = 0.0
    total_reclaimable_mb: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_memory_mb": round(self.total_memory_mb, 1),
            "total_reclaimable_mb": round(self.total_reclaimable_mb, 1),
            "apps": {k: v.to_dict() for k, v in self.apps.items()},
        }

    def alert_lines(self, threshold_mb: float = 500.0) -> List[str]:
        lines = []
        for key, summary in self.apps.items():
            if summary.reclaimable_mb >= threshold_mb:
                lines.append(
                    f"{summary.profile.display_name}: "
                    f"{len(summary.idle_sessions)} sessão(ões) ociosa(s) — "
                    f"{summary.reclaimable_mb / 1024:.2f} GB recuperável"
                )
        return lines


# ---------------------------------------------------------------------------
# Classificação de processo
# ---------------------------------------------------------------------------

def _has_helper_flag(cmdline: List[str], flags: List[str]) -> bool:
    cmd = " ".join(cmdline).lower()
    return any(f.lower() in cmd for f in flags)


def _is_renderer(cmdline: List[str]) -> bool:
    cmd = " ".join(cmdline).lower()
    return "--type=renderer" in cmd


def _classify_kind(profile: AppProfile, cmdline: List[str]) -> str:
    if _is_renderer(cmdline) and profile.count_tabs:
        return ProcKind.RENDERER
    if _has_helper_flag(cmdline, profile.helper_flags):
        return ProcKind.HELPER
    if "--output-format" in " ".join(cmdline):
        return ProcKind.SESSION
    return ProcKind.MAIN


def _classify_status(
    profile: AppProfile,
    cpu: float,
    age_seconds: float,
    is_current: bool,
) -> str:
    if is_current:
        return ProcStatus.CURRENT
    if age_seconds < profile.min_age_hours * 3600:
        return ProcStatus.YOUNG
    if cpu <= profile.idle_cpu_threshold:
        return ProcStatus.IDLE
    return ProcStatus.ACTIVE


# ---------------------------------------------------------------------------
# Auditor principal
# ---------------------------------------------------------------------------

CPU_SAMPLE_SECONDS = 3.0


def _current_session_pids() -> Set[int]:
    pids: Set[int] = set()
    try:
        p = psutil.Process(os.getpid())
        for _ in range(4):
            pids.add(p.pid)
            p = p.parent()
            if p is None:
                break
    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
        pass
    return pids


class MultiAppAuditor:
    """Audita múltiplos aplicativos em uma única passagem."""

    def __init__(self, app_keys: Optional[List[str]] = None) -> None:
        self._profiles = (
            {k: APP_PROFILES[k] for k in app_keys if k in APP_PROFILES}
            if app_keys
            else APP_PROFILES
        )

    def _build_name_index(self) -> Dict[str, AppProfile]:
        index: Dict[str, AppProfile] = {}
        for profile in self._profiles.values():
            for name in profile.process_names:
                index[name.lower()] = profile
        return index

    def audit(self) -> MultiAppAuditResult:
        name_index = self._build_name_index()
        current_pids = _current_session_pids()

        # 1. Encontrar processos relevantes e inicializar CPU
        candidates: List[psutil.Process] = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if (proc.info["name"] or "").lower() in name_index:
                    proc.cpu_percent(interval=None)
                    candidates.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 2. Aguardar intervalo de medição
        time.sleep(CPU_SAMPLE_SECONDS)

        # 3. Coletar dados
        summaries: Dict[str, AppSummary] = {
            k: AppSummary(profile=p) for k, p in self._profiles.items()
        }

        for proc in candidates:
            try:
                with proc.oneshot():
                    name = proc.name()
                    profile = name_index.get(name.lower())
                    if profile is None:
                        continue
                    pid = proc.pid
                    mem_mb = proc.memory_info().rss / 1024 / 1024
                    cpu = proc.cpu_percent(interval=None)
                    age = time.time() - proc.create_time()
                    try:
                        cmdline = proc.cmdline()
                    except (psutil.AccessDenied, psutil.ZombieProcess):
                        cmdline = []

                is_current = pid in current_pids
                kind = _classify_kind(profile, cmdline)
                status = _classify_status(profile, cpu, age, is_current)

                summaries[profile.key].processes.append(AppProcess(
                    pid=pid,
                    name=name,
                    app_key=profile.key,
                    kind=kind,
                    status=status,
                    memory_mb=mem_mb,
                    cpu_percent=cpu,
                    age_seconds=age,
                    cmdline=cmdline,
                    is_current=is_current,
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Ordenar por memória dentro de cada app
        for summary in summaries.values():
            summary.processes.sort(key=lambda p: p.memory_mb, reverse=True)

        total_mem = sum(s.total_memory_mb for s in summaries.values())
        total_reclaimable = sum(s.reclaimable_mb for s in summaries.values())

        return MultiAppAuditResult(
            apps={k: s for k, s in summaries.items() if s.processes},
            total_memory_mb=total_mem,
            total_reclaimable_mb=total_reclaimable,
        )

    def terminate_pids(
        self,
        pids: List[int],
        result: MultiAppAuditResult,
        dry_run: bool = True,
    ) -> List[tuple]:
        """Encerra PIDs verificando que são processos safe_to_close."""
        safe = {
            p.pid
            for s in result.apps.values()
            for p in s.processes
            if p.safe_to_close
        }
        actions = []
        for pid in pids:
            if pid not in safe:
                actions.append((pid, "?", False, "não está na lista de seguros ou é sessão atual"))
                continue
            if dry_run:
                actions.append((pid, "", None, "dry-run"))
                continue
            try:
                psutil.Process(pid).terminate()
                actions.append((pid, "", True, "encerrado (SIGTERM)"))
            except psutil.NoSuchProcess:
                actions.append((pid, "", False, "processo não encontrado"))
            except psutil.AccessDenied:
                actions.append((pid, "", False, "acesso negado"))
            except Exception as exc:
                actions.append((pid, "", False, str(exc)))
        return actions
