"""Auditor de instâncias Claude Code / Claude Desktop ociosas."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import List, Optional

import psutil

# Nomes de processo que pertencem ao ecossistema Claude/Anthropic
_CLAUDE_NAMES = {
    "claude.exe", "claude",
    "claude code", "claude-code",
    "codex.exe", "codex",
}

# CPU abaixo deste limiar por CPU_SAMPLE_SECONDS = candidato a ocioso
_IDLE_CPU_THRESHOLD = 2.0
_CPU_SAMPLE_SECONDS = 3.0
# Processo com menos de este tempo é considerado recém-iniciado → não tocar
_MIN_AGE_SECONDS = 30.0


class Status:
    ACTIVE = "ACTIVE"       # CPU elevado — claramente trabalhando
    IDLE = "IDLE"           # CPU quase zero por vários segundos
    YOUNG = "YOUNG"         # Recém-iniciado — aguardar
    CURRENT = "CURRENT"     # Esta sessão — nunca encerrar
    UNKNOWN = "UNKNOWN"     # Não foi possível medir


@dataclass
class ClaudeInstance:
    pid: int
    name: str
    memory_mb: float
    cpu_percent: float
    age_seconds: float
    cmdline: List[str]
    status: str
    username: Optional[str] = None
    is_current_session: bool = False
    parent_pid: Optional[int] = None
    parent_name: Optional[str] = None

    @property
    def age_minutes(self) -> float:
        return self.age_seconds / 60

    @property
    def age_display(self) -> str:
        if self.age_seconds < 120:
            return f"{self.age_seconds:.0f}s"
        if self.age_seconds < 3600:
            return f"{self.age_seconds / 60:.0f}m"
        return f"{self.age_seconds / 3600:.1f}h"

    @property
    def safe_to_close(self) -> bool:
        return self.status == Status.IDLE and not self.is_current_session

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "name": self.name,
            "memory_mb": round(self.memory_mb, 1),
            "cpu_percent": round(self.cpu_percent, 2),
            "age_display": self.age_display,
            "status": self.status,
            "is_current_session": self.is_current_session,
            "safe_to_close": self.safe_to_close,
            "cmdline_hint": " ".join(self.cmdline[:4]) if self.cmdline else "",
        }


@dataclass
class ClaudeAuditResult:
    instances: List[ClaudeInstance] = field(default_factory=list)
    total_memory_mb: float = 0.0
    reclaimable_mb: float = 0.0
    idle_count: int = 0
    active_count: int = 0

    def to_dict(self) -> dict:
        return {
            "total_instances": len(self.instances),
            "active": self.active_count,
            "idle": self.idle_count,
            "total_memory_mb": round(self.total_memory_mb, 1),
            "reclaimable_mb": round(self.reclaimable_mb, 1),
            "instances": [i.to_dict() for i in self.instances],
        }


def _current_session_pids() -> set:
    """PIDs que pertencem à cadeia de processo desta sessão."""
    pids = set()
    try:
        # Esta sessão Python
        me = psutil.Process(os.getpid())
        pids.add(me.pid)
        # Processo pai (PowerShell / terminal)
        parent = me.parent()
        if parent:
            pids.add(parent.pid)
            # Avô (Claude Code que abriu o terminal)
            grandparent = parent.parent()
            if grandparent:
                pids.add(grandparent.pid)
                ggp = grandparent.parent()
                if ggp:
                    pids.add(ggp.pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return pids


def _is_claude_process(name: str) -> bool:
    lower = name.lower()
    return any(cn in lower for cn in _CLAUDE_NAMES)


def _get_parent_info(proc: psutil.Process):
    try:
        p = proc.parent()
        if p:
            return p.pid, p.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return None, None


class ClaudeAuditor:
    """Detecta instâncias Claude ociosas e calcula memória recuperável."""

    def audit(self) -> ClaudeAuditResult:
        # 1. Encontrar todos os processos Claude
        candidates: List[psutil.Process] = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if _is_claude_process(proc.info["name"] or ""):
                    candidates.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if not candidates:
            return ClaudeAuditResult()

        # 2. Inicializar contadores de CPU
        for proc in candidates:
            try:
                proc.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 3. Aguardar o intervalo de medição
        time.sleep(_CPU_SAMPLE_SECONDS)

        # 4. Coletar dados reais
        current_pids = _current_session_pids()
        instances: List[ClaudeInstance] = []

        for proc in candidates:
            try:
                with proc.oneshot():
                    pid = proc.pid
                    name = proc.name()
                    mem_mb = proc.memory_info().rss / 1024 / 1024
                    cpu = proc.cpu_percent(interval=None)
                    age = time.time() - proc.create_time()
                    try:
                        cmdline = proc.cmdline()
                    except (psutil.AccessDenied, psutil.ZombieProcess):
                        cmdline = []
                    try:
                        username = proc.username()
                    except (psutil.AccessDenied, psutil.ZombieProcess):
                        username = None

                parent_pid, parent_name = _get_parent_info(proc)
                is_current = pid in current_pids

                # Classificar status
                if is_current:
                    status = Status.CURRENT
                elif age < _MIN_AGE_SECONDS:
                    status = Status.YOUNG
                elif cpu <= _IDLE_CPU_THRESHOLD:
                    status = Status.IDLE
                elif cpu > _IDLE_CPU_THRESHOLD:
                    status = Status.ACTIVE
                else:
                    status = Status.UNKNOWN

                instances.append(ClaudeInstance(
                    pid=pid,
                    name=name,
                    memory_mb=mem_mb,
                    cpu_percent=cpu,
                    age_seconds=age,
                    cmdline=cmdline,
                    status=status,
                    username=username,
                    is_current_session=is_current,
                    parent_pid=parent_pid,
                    parent_name=parent_name,
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        instances.sort(key=lambda i: i.memory_mb, reverse=True)

        total_mb = sum(i.memory_mb for i in instances)
        idle = [i for i in instances if i.status == Status.IDLE]
        active = [i for i in instances if i.status == Status.ACTIVE]
        reclaimable = sum(i.memory_mb for i in idle)

        return ClaudeAuditResult(
            instances=instances,
            total_memory_mb=total_mb,
            reclaimable_mb=reclaimable,
            idle_count=len(idle),
            active_count=len(active),
        )

    def terminate_idle(
        self,
        result: ClaudeAuditResult,
        dry_run: bool = True,
        confirmed_pids: Optional[List[int]] = None,
    ) -> List[tuple]:
        """
        Encerra instâncias ociosas (somente as que safe_to_close=True).
        Retorna lista de (pid, name, success, message).
        confirmed_pids: se fornecido, só encerra estes PIDs.
        """
        actions = []
        for inst in result.instances:
            if not inst.safe_to_close:
                continue
            if confirmed_pids is not None and inst.pid not in confirmed_pids:
                continue
            if dry_run:
                actions.append((inst.pid, inst.name, None, "dry-run — não encerrado"))
                continue
            try:
                proc = psutil.Process(inst.pid)
                proc.terminate()
                actions.append((inst.pid, inst.name, True, "encerrado (SIGTERM)"))
            except psutil.NoSuchProcess:
                actions.append((inst.pid, inst.name, False, "processo não encontrado"))
            except psutil.AccessDenied:
                actions.append((inst.pid, inst.name, False, "acesso negado"))
            except Exception as exc:
                actions.append((inst.pid, inst.name, False, str(exc)))
        return actions
