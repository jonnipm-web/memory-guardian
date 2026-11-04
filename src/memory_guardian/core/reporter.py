"""Report generation — text and JSON output."""
from __future__ import annotations

import datetime
import json
import os
import time
from pathlib import Path
from typing import List, Optional

from ..core.analyzer import AnalysisResult
from ..models.process import ProcessRisk, RiskLevel
from ..models.snapshot import SystemSnapshot


def _fmt_mb(mb: float) -> str:
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.0f} MB"


def _fmt_ts(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _risk_badge(level: RiskLevel) -> str:
    badges = {
        RiskLevel.NONE: "    ",
        RiskLevel.LOW: "[LOW]",
        RiskLevel.MEDIUM: "[MED]",
        RiskLevel.HIGH: "[HIGH]",
        RiskLevel.CRITICAL: "[CRIT]",
    }
    return badges.get(level, "    ")


class Reporter:
    """Generates human-readable and machine-readable reports."""

    def snapshot_summary(self, snapshot: SystemSnapshot) -> str:
        lines = [
            "=" * 64,
            f"  Memory Guardian — Snapshot  {_fmt_ts(snapshot.timestamp)}",
            "=" * 64,
            "",
            f"  RAM   : {_fmt_mb(snapshot.memory.used_mb)} / {_fmt_mb(snapshot.memory.total_mb)}"
            f"  ({snapshot.memory.percent:.1f}%)",
            f"  Avail : {_fmt_mb(snapshot.memory.available_mb)}",
            f"  Swap  : {_fmt_mb(snapshot.swap.used_mb)} / {_fmt_mb(snapshot.swap.total_mb)}"
            f"  ({snapshot.swap.percent:.1f}%)",
            f"  CPU   : {snapshot.cpu_percent:.1f}%",
            f"  Procs : {len(snapshot.processes)}",
            "",
            "  Top 10 processes by memory:",
            f"  {'PID':>7}  {'NAME':<30}  {'MEM':>8}  {'CPU':>6}  STATUS",
            "  " + "-" * 60,
        ]
        for proc in snapshot.top_memory_processes[:10]:
            lines.append(
                f"  {proc.pid:>7}  {proc.name:<30}  "
                f"{_fmt_mb(proc.memory_mb):>8}  {proc.cpu_percent:>5.1f}%  {proc.status.value}"
            )
        lines.append("")
        return "\n".join(lines)

    def analysis_report(
        self,
        analysis: AnalysisResult,
        process_risks: Optional[List[ProcessRisk]] = None,
    ) -> str:
        lines = [
            "=" * 64,
            f"  Memory Guardian — Analysis  {_fmt_ts(analysis.snapshot_time)}",
            "=" * 64,
            "",
        ]

        if analysis.alerts:
            lines.append("  ALERTS:")
            for alert in analysis.alerts:
                lines.append(f"    ⚠  {alert}")
            lines.append("")

        lines.append(
            f"  RAM: {analysis.total_memory_percent:.1f}%  |  "
            f"High-mem procs: {len(analysis.high_memory_processes)}  |  "
            f"Zombies: {len(analysis.zombie_processes)}  |  "
            f"Leaks: {len(analysis.potential_leaks)}"
        )
        lines.append("")

        if analysis.potential_leaks:
            lines.append("  POTENTIAL MEMORY LEAKS:")
            for proc, reason in analysis.potential_leaks:
                lines.append(f"    PID {proc.pid:>6}  {proc.name:<30}  {reason}")
            lines.append("")

        if analysis.zombie_processes:
            lines.append("  ZOMBIE PROCESSES:")
            for proc in analysis.zombie_processes:
                lines.append(
                    f"    PID {proc.pid:>6}  {proc.name:<30}  "
                    f"age {proc.age_hours:.1f}h"
                )
            lines.append("")

        if analysis.idle_high_memory:
            lines.append("  IDLE PROCESSES WITH HIGH MEMORY:")
            for proc in analysis.idle_high_memory:
                lines.append(
                    f"    PID {proc.pid:>6}  {proc.name:<30}  "
                    f"{_fmt_mb(proc.memory_mb):>8}  idle {proc.age_hours:.1f}h"
                )
            lines.append("")

        if process_risks:
            lines.append("  RISK ASSESSMENT:")
            lines.append(
                f"  {'RISK':<8}  {'PID':>7}  {'NAME':<30}  {'MEM':>8}  ACTION"
            )
            lines.append("  " + "-" * 72)
            for pr in sorted(process_risks, key=lambda x: x.risk_level, reverse=True):
                if pr.risk_level == RiskLevel.NONE:
                    continue
                lines.append(
                    f"  {_risk_badge(pr.risk_level):<8}  {pr.process.pid:>7}  "
                    f"{pr.process.name:<30}  {_fmt_mb(pr.process.memory_mb):>8}  "
                    f"{pr.action_recommended}"
                )
            lines.append("")

        lines.append("=" * 64)
        return "\n".join(lines)

    def to_json(
        self,
        snapshot: SystemSnapshot,
        analysis: AnalysisResult,
        process_risks: Optional[List[ProcessRisk]] = None,
    ) -> str:
        data = {
            "generated_at": _fmt_ts(time.time()),
            "snapshot": snapshot.to_dict(),
            "analysis": analysis.to_dict(),
        }
        if process_risks:
            data["process_risks"] = [pr.to_dict() for pr in process_risks]
        return json.dumps(data, indent=2, default=str)

    def save_report(
        self,
        content: str,
        output_dir: Path,
        prefix: str = "report",
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = output_dir / f"{prefix}_{ts}.txt"
        path.write_text(content, encoding="utf-8")
        return path

    def save_json_report(
        self,
        content: str,
        output_dir: Path,
        prefix: str = "report",
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = output_dir / f"{prefix}_{ts}.json"
        path.write_text(content, encoding="utf-8")
        return path
