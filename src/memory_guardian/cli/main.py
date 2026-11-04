"""Memory Guardian CLI — entry point."""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import click
import yaml

from ..config import build_policy_config, load_config
from ..core.analyzer import MemoryAnalyzer
from ..core.app_audit import APP_PROFILES, MultiAppAuditor, ProcKind, ProcStatus
from ..core.claude_audit import ClaudeAuditor, Status
from ..core.collector import SystemCollector
from ..core.policy import PolicyEngine
from ..core.reporter import Reporter
from ..history.store import HistoryStore
from ..notify import notify_idle_apps, write_alert_log

pass_ctx = click.make_pass_decorator(dict, ensure=True)


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _load(config_path: Optional[str]) -> dict:
    return load_config(Path(config_path) if config_path else None)


@click.group()
@click.option("--config", "-c", default=None, help="Path to config YAML file.")
@click.option("--log-level", default="INFO", help="Logging level.")
@click.pass_context
def cli(ctx: click.Context, config: Optional[str], log_level: str) -> None:
    """Memory Guardian — safe memory monitoring for Windows."""
    ctx.ensure_object(dict)
    cfg = _load(config)
    _setup_logging(log_level or cfg.get("alerts", {}).get("log_level", "INFO"))
    ctx.obj["cfg"] = cfg
    ctx.obj["collector"] = SystemCollector()
    ctx.obj["analyzer"] = MemoryAnalyzer()
    ctx.obj["policy"] = PolicyEngine(build_policy_config(cfg))
    ctx.obj["reporter"] = Reporter()
    output_cfg = cfg.get("output", {})
    ctx.obj["history"] = HistoryStore(
        Path(output_cfg.get("history_db", "~/.memory-guardian/history.db")).expanduser()
    )
    ctx.obj["reports_dir"] = Path(
        output_cfg.get("reports_dir", "~/.memory-guardian/reports")
    ).expanduser()


# ---------------------------------------------------------------------------
# snapshot
# ---------------------------------------------------------------------------
@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option("--save", is_flag=True, help="Save report to disk.")
@click.option("--label", default=None, help="Optional label for this snapshot.")
@pass_ctx
def snapshot(ctx: dict, as_json: bool, save: bool, label: Optional[str]) -> None:
    """Take a single memory snapshot and display it."""
    collector: SystemCollector = ctx["collector"]
    reporter: Reporter = ctx["reporter"]
    history: HistoryStore = ctx["history"]

    click.echo("Collecting snapshot…")
    snap = collector.collect_snapshot(label=label)
    history.save(snap)

    if as_json:
        output = snap.to_dict()
        click.echo(json.dumps(output, indent=2, default=str))
    else:
        click.echo(reporter.snapshot_summary(snap))

    if save:
        path = reporter.save_report(
            reporter.snapshot_summary(snap), ctx["reports_dir"], prefix="snapshot"
        )
        click.echo(f"Report saved: {path}")


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------
@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option("--save", is_flag=True, help="Save report to disk.")
@pass_ctx
def analyze(ctx: dict, as_json: bool, save: bool) -> None:
    """Analyze current system state and report findings."""
    collector: SystemCollector = ctx["collector"]
    analyzer: MemoryAnalyzer = ctx["analyzer"]
    policy: PolicyEngine = ctx["policy"]
    reporter: Reporter = ctx["reporter"]
    history: HistoryStore = ctx["history"]

    click.echo("Collecting snapshot…")
    snap = collector.collect_snapshot()
    history.save(snap)

    result = analyzer.analyze(snap)
    risks = [
        policy.evaluate(proc, *analyzer.classify_process_risk(proc))
        for proc in snap.processes
    ]

    if as_json:
        click.echo(reporter.to_json(snap, result, risks))
    else:
        click.echo(reporter.snapshot_summary(snap))
        click.echo(reporter.analysis_report(result, risks))

    if save:
        content = reporter.snapshot_summary(snap) + reporter.analysis_report(result, risks)
        path = reporter.save_report(content, ctx["reports_dir"], prefix="analysis")
        click.echo(f"Report saved: {path}")


# ---------------------------------------------------------------------------
# monitor
# ---------------------------------------------------------------------------
@cli.command()
@click.option("--interval", "-i", default=60, show_default=True, help="Seconds between snapshots.")
@click.option("--count", "-n", default=0, help="Number of snapshots (0 = unlimited).")
@click.option("--save", is_flag=True, help="Save each report to disk.")
@pass_ctx
def monitor(ctx: dict, interval: int, count: int, save: bool) -> None:
    """Continuously monitor memory at regular intervals. Ctrl+C to stop."""
    collector: SystemCollector = ctx["collector"]
    analyzer: MemoryAnalyzer = ctx["analyzer"]
    reporter: Reporter = ctx["reporter"]
    history: HistoryStore = ctx["history"]

    click.echo(
        f"Monitoring every {interval}s"
        + (f" × {count}" if count else " (unlimited)")
        + " — Ctrl+C to stop\n"
    )

    iterations = 0
    try:
        while True:
            snap = collector.collect_snapshot()
            history.save(snap)
            result = analyzer.analyze(snap)
            summary = reporter.snapshot_summary(snap)
            report = reporter.analysis_report(result)

            click.echo(summary)
            if result.alerts:
                click.echo(report)

            if save:
                content = summary + (report if result.alerts else "")
                reporter.save_report(content, ctx["reports_dir"])

            iterations += 1
            if count and iterations >= count:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        click.echo("\nMonitoring stopped.")


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------
@cli.command("history")
@click.option("--hours", default=24, show_default=True, help="Hours to look back.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@pass_ctx
def show_history(ctx: dict, hours: int, as_json: bool) -> None:
    """Show memory trend from stored history."""
    history: HistoryStore = ctx["history"]
    rows = history.memory_trend(hours=hours)
    if not rows:
        click.echo("No history found.")
        return
    if as_json:
        click.echo(json.dumps(rows, indent=2))
        return

    click.echo(f"\nMemory trend — last {hours}h ({len(rows)} records)\n")
    click.echo(f"  {'TIME':<20}  {'RAM %':>6}  {'AVAIL':>8}  {'SWAP %':>6}  {'CPU %':>6}")
    click.echo("  " + "-" * 55)
    for row in rows:
        avail_mb = row["available_mb"]
        avail_str = f"{avail_mb / 1024:.1f} GB" if avail_mb >= 1024 else f"{avail_mb:.0f} MB"
        click.echo(
            f"  {row['recorded_at'][:19]:<20}  "
            f"{row['memory_pct']:>5.1f}%  {avail_str:>8}  "
            f"{row['swap_pct']:>5.1f}%  {row['cpu_pct']:>5.1f}%"
        )
    click.echo()


# ---------------------------------------------------------------------------
# config init
# ---------------------------------------------------------------------------
@cli.command("config-init")
@click.option("--output", "-o", default=None, help="Output path for config file.")
def config_init(output: Optional[str]) -> None:
    """Write a default configuration file."""
    from ..config.defaults import DEFAULT_CONFIG

    target = Path(output) if output else Path.home() / ".memory-guardian" / "config.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        click.echo(f"Config already exists: {target}")
        if not click.confirm("Overwrite?"):
            return

    with target.open("w", encoding="utf-8") as fh:
        yaml.dump(DEFAULT_CONFIG, fh, default_flow_style=False, sort_keys=False)
    click.echo(f"Config written to: {target}")


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------
@cli.command()
def version() -> None:
    """Show version."""
    from .. import __version__
    click.echo(f"memory-guardian {__version__}")


# ---------------------------------------------------------------------------
# claude-audit
# ---------------------------------------------------------------------------
_STATUS_SYMBOL = {
    Status.ACTIVE:  "▶ ATIVO   ",
    Status.IDLE:    "◉ OCIOSO  ",
    Status.CURRENT: "★ ATUAL   ",
    Status.YOUNG:   "◌ RECENTE ",
    Status.UNKNOWN: "? DESC.   ",
}

_STATUS_COLOR = {
    Status.ACTIVE:  "green",
    Status.IDLE:    "yellow",
    Status.CURRENT: "cyan",
    Status.YOUNG:   "blue",
    Status.UNKNOWN: "white",
}


@cli.command("claude-audit")
@click.option("--json", "as_json", is_flag=True, help="Saída em JSON.")
@click.option(
    "--close-idle", is_flag=True,
    help="Encerrar instâncias ociosas (exige confirmação por PID).",
)
@click.option(
    "--dry-run", "force_dry", is_flag=True, default=False,
    help="Mostrar o que seria encerrado sem executar.",
)
@click.option(
    "--pids", default=None,
    help="PIDs separados por vírgula para encerrar diretamente (sem prompt interativo).",
)
@pass_ctx
def claude_audit(ctx: dict, as_json: bool, close_idle: bool, force_dry: bool, pids: str) -> None:
    """Audita instâncias Claude Code e identifica as que podem ser fechadas."""
    cfg = ctx["cfg"]
    readonly = cfg.get("policy", {}).get("readonly_mode", True)
    dry_run = cfg.get("policy", {}).get("dry_run", True) or force_dry

    auditor = ClaudeAuditor()
    click.echo("Medindo CPU das instâncias Claude (~3 s)…")
    result = auditor.audit()

    if as_json:
        click.echo(json.dumps(result.to_dict(), indent=2, default=str))
        return

    if not result.instances:
        click.echo("Nenhuma instância Claude encontrada.")
        return

    # Cabeçalho
    click.echo("")
    click.echo("=" * 72)
    click.echo(f"  Memory Guardian — Auditoria Claude  ({len(result.instances)} instâncias)")
    click.echo("=" * 72)
    click.echo(
        f"  Memória total Claude : {result.total_memory_mb / 1024:.2f} GB\n"
        f"  Instâncias ativas    : {result.active_count}\n"
        f"  Instâncias ociosas   : {result.idle_count}  "
        f"({result.reclaimable_mb / 1024:.2f} GB recuperável)\n"
    )
    click.echo(
        f"  {'STATUS':<12}  {'PID':>7}  {'NOME':<24}  {'MEM':>8}  {'CPU':>6}  {'TEMPO':<8}"
    )
    click.echo("  " + "-" * 68)

    for inst in result.instances:
        label = _STATUS_SYMBOL.get(inst.status, "?         ")
        color = _STATUS_COLOR.get(inst.status, "white")
        mem_str = f"{inst.memory_mb / 1024:.2f} GB" if inst.memory_mb >= 1024 else f"{inst.memory_mb:.0f} MB"
        line = (
            f"  {label:<12}  {inst.pid:>7}  {inst.name:<24}  "
            f"{mem_str:>8}  {inst.cpu_percent:>5.1f}%  {inst.age_display:<8}"
        )
        click.secho(line, fg=color)
        if inst.cmdline and len(inst.cmdline) > 1:
            hint = " ".join(inst.cmdline[1:3])[:60]
            click.echo(f"             {'':>7}  {hint}")

    click.echo("")
    click.echo("  Legenda:")
    click.secho("    ★ ATUAL    — esta sessão (nunca fechar)", fg="cyan")
    click.secho("    ▶ ATIVO    — executando tarefa agora", fg="green")
    click.secho("    ◉ OCIOSO   — CPU ≈ 0 — candidato a fechar", fg="yellow")
    click.secho("    ◌ RECENTE  — recém-iniciado — aguardar", fg="blue")
    click.echo("")

    idle_instances = [i for i in result.instances if i.safe_to_close]
    if not idle_instances:
        click.echo("  Nenhuma instância ociosa detectada. Nada a fazer.")
        return

    # Encerramento direto via --pids (sem prompt)
    if pids:
        confirmed_pids = [int(p.strip()) for p in pids.split(",") if p.strip().isdigit()]
        cfg_ro = ctx["cfg"].get("policy", {}).get("readonly_mode", True)
        if cfg_ro:
            click.secho("  MODO SOMENTE LEITURA — use readonly_mode: false no config.", fg="red")
            return
        actions = auditor.terminate_idle(result, dry_run=force_dry, confirmed_pids=confirmed_pids)
        for pid, name, success, msg in actions:
            color = "green" if success else ("blue" if success is None else "red")
            click.secho(f"    PID {pid}  {name}  → {msg}", fg=color)
        return

    if not close_idle:
        click.echo(
            f"  {len(idle_instances)} instância(s) ociosa(s) identificada(s).\n"
            f"  Use --close-idle para encerrar (com confirmação por PID)."
        )
        return

    # Modo de encerramento
    if readonly:
        click.secho(
            "  MODO SOMENTE LEITURA ativo — encerramento bloqueado.\n"
            "  Defina readonly_mode: false no config para habilitar.",
            fg="red",
        )
        return

    click.echo("  Instâncias candidatas a encerramento:")
    for inst in idle_instances:
        mem_str = f"{inst.memory_mb / 1024:.2f} GB" if inst.memory_mb >= 1024 else f"{inst.memory_mb:.0f} MB"
        click.secho(
            f"    PID {inst.pid}  {inst.name}  {mem_str}  ({inst.age_display})",
            fg="yellow",
        )
    click.echo("")

    if dry_run:
        actions = auditor.terminate_idle(result, dry_run=True)
        click.secho("  DRY-RUN — nenhuma ação executada:", fg="blue")
        for pid, name, _, msg in actions:
            click.echo(f"    PID {pid}  {name}  → {msg}")
        return

    # Confirmação por PID
    click.echo("  Digite os PIDs a encerrar separados por vírgula (ou ENTER para cancelar):")
    raw = click.prompt("  PIDs", default="", show_default=False)
    if not raw.strip():
        click.echo("  Cancelado.")
        return

    confirmed_pids = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit():
            confirmed_pids.append(int(token))

    if not confirmed_pids:
        click.echo("  Nenhum PID válido informado. Cancelado.")
        return

    actions = auditor.terminate_idle(result, dry_run=False, confirmed_pids=confirmed_pids)
    click.echo("")
    for pid, name, success, msg in actions:
        color = "green" if success else "red"
        click.secho(f"    PID {pid}  {name}  → {msg}", fg=color)
    click.echo("")


def main() -> None:
    cli()


# ---------------------------------------------------------------------------
# app-audit
# ---------------------------------------------------------------------------

_APP_STATUS_SYMBOL = {
    ProcStatus.ACTIVE:  "▶ ATIVO   ",
    ProcStatus.IDLE:    "◉ OCIOSO  ",
    ProcStatus.CURRENT: "★ ATUAL   ",
    ProcStatus.YOUNG:   "◌ RECENTE ",
}
_APP_STATUS_COLOR = {
    ProcStatus.ACTIVE:  "green",
    ProcStatus.IDLE:    "yellow",
    ProcStatus.CURRENT: "cyan",
    ProcStatus.YOUNG:   "blue",
}
_KIND_LABEL = {
    ProcKind.MAIN:     "principal",
    ProcKind.SESSION:  "sessão  ",
    ProcKind.RENDERER: "aba     ",
    ProcKind.HELPER:   "helper  ",
}


@cli.command("app-audit")
@click.option("--apps", default=None,
              help="Apps a auditar (ex: claude,codex,chrome). Padrão: todos.")
@click.option("--json", "as_json", is_flag=True)
@click.option("--notify", "do_notify", is_flag=True,
              help="Enviar notificação Windows se houver ociosos.")
@click.option("--close-idle", is_flag=True,
              help="Encerrar sessões ociosas (exige confirmação).")
@click.option("--pids", default=None,
              help="PIDs separados por vírgula para encerrar diretamente.")
@click.option("--dry-run", "force_dry", is_flag=True)
@pass_ctx
def app_audit(
    ctx: dict,
    apps: Optional[str],
    as_json: bool,
    do_notify: bool,
    close_idle: bool,
    pids: Optional[str],
    force_dry: bool,
) -> None:
    """Audita Claude Code, Codex, ChatGPT, Chrome e Edge em uma única passagem."""
    cfg = ctx["cfg"]
    readonly = cfg.get("policy", {}).get("readonly_mode", True)
    dry_run = cfg.get("policy", {}).get("dry_run", True) or force_dry

    app_keys = [a.strip() for a in apps.split(",")] if apps else None
    auditor = MultiAppAuditor(app_keys)

    click.echo("Medindo CPU dos aplicativos (~3 s)…")
    result = auditor.audit()

    if as_json:
        import json as _json
        click.echo(_json.dumps(result.to_dict(), indent=2, default=str))
        return

    # Relatório por app
    click.echo("")
    click.echo("=" * 72)
    click.echo(
        f"  Memory Guardian — Auditoria de Apps"
        f"  |  Total: {result.total_memory_mb / 1024:.2f} GB"
        f"  |  Recuperável: {result.total_reclaimable_mb / 1024:.2f} GB"
    )
    click.echo("=" * 72)

    for key, summary in result.apps.items():
        profile = summary.profile
        if not summary.processes:
            continue

        mem_str = (
            f"{summary.total_memory_mb / 1024:.2f} GB"
            if summary.total_memory_mb >= 1024
            else f"{summary.total_memory_mb:.0f} MB"
        )
        tab_info = f"  {summary.tab_count} aba(s)" if profile.count_tabs and summary.tab_count else ""
        click.echo("")
        click.secho(
            f"  ── {profile.display_name}  ({mem_str}{tab_info})",
            bold=True,
        )
        click.echo(
            f"     {'STATUS':<12}  {'PID':>7}  {'TIPO':<10}  {'MEM':>8}  {'CPU':>6}  {'TEMPO':<8}"
        )
        click.echo("     " + "-" * 58)

        for proc in summary.processes:
            # Mostrar helpers apenas em resumo
            if proc.kind == ProcKind.HELPER:
                continue
            sym = _APP_STATUS_SYMBOL.get(proc.status, "?         ")
            color = _APP_STATUS_COLOR.get(proc.status, "white")
            kind_lbl = _KIND_LABEL.get(proc.kind, proc.kind)
            mem_p = (
                f"{proc.memory_mb / 1024:.2f} GB"
                if proc.memory_mb >= 1024
                else f"{proc.memory_mb:.0f} MB"
            )
            line = (
                f"     {sym:<12}  {proc.pid:>7}  {kind_lbl:<10}  "
                f"{mem_p:>8}  {proc.cpu_percent:>5.1f}%  {proc.age_display:<8}"
            )
            click.secho(line, fg=color)

        helpers = [p for p in summary.processes if p.kind == ProcKind.HELPER]
        if helpers:
            h_mem = sum(p.memory_mb for p in helpers)
            click.echo(
                f"     {'':12}  {'':>7}  + {len(helpers)} processo(s) auxiliar(es)"
                f"  ({h_mem:.0f} MB total)"
            )

        if summary.idle_sessions:
            click.secho(
                f"     → {len(summary.idle_sessions)} sessão(ões) ociosa(s)"
                f" — {summary.reclaimable_mb:.0f} MB recuperável",
                fg="yellow",
            )

    click.echo("")
    click.echo("=" * 72)
    click.echo("  Legenda:")
    click.secho("    ★ ATUAL   — esta sessão ativa", fg="cyan")
    click.secho("    ▶ ATIVO   — executando agora", fg="green")
    click.secho("    ◉ OCIOSO  — candidato a fechar", fg="yellow")
    click.secho("    ◌ RECENTE — recém-iniciado", fg="blue")
    click.echo("")

    # Notificação Windows
    if do_notify:
        notify_idle_apps(result.apps, result.total_memory_mb)

    # Encerramento via --pids
    if pids:
        pid_list = [int(p.strip()) for p in pids.split(",") if p.strip().isdigit()]
        if readonly:
            click.secho("  MODO SOMENTE LEITURA — encerramento bloqueado.", fg="red")
            return
        actions = auditor.terminate_pids(pid_list, result, dry_run=dry_run)
        for pid, _, success, msg in actions:
            color = "green" if success else ("blue" if success is None else "red")
            click.secho(f"    PID {pid}  → {msg}", fg=color)
        return

    # Encerramento interativo
    if close_idle:
        all_idle = [
            p for s in result.apps.values() for p in s.idle_sessions
        ]
        if not all_idle:
            click.echo("  Nenhuma sessão ociosa encontrada.")
            return
        if readonly:
            click.secho("  MODO SOMENTE LEITURA — defina readonly_mode: false no config.", fg="red")
            return
        click.echo("  Sessões ociosas encontradas:")
        for p in all_idle:
            mem_p = f"{p.memory_mb / 1024:.2f} GB" if p.memory_mb >= 1024 else f"{p.memory_mb:.0f} MB"
            click.secho(f"    PID {p.pid}  {p.name}  {mem_p}  {p.age_display}", fg="yellow")
        click.echo("")
        raw = click.prompt(
            "  Digite os PIDs a encerrar (vírgula) ou ENTER para cancelar",
            default="", show_default=False,
        )
        if not raw.strip():
            click.echo("  Cancelado.")
            return
        pid_list = [int(t.strip()) for t in raw.split(",") if t.strip().isdigit()]
        actions = auditor.terminate_pids(pid_list, result, dry_run=dry_run)
        for pid, _, success, msg in actions:
            color = "green" if success else ("blue" if success is None else "red")
            click.secho(f"    PID {pid}  → {msg}", fg=color)


# ---------------------------------------------------------------------------
# schedule-setup
# ---------------------------------------------------------------------------

@cli.command("schedule-setup")
@click.option("--interval-hours", default=2, show_default=True,
              help="Horas entre execuções do monitoramento automático.")
@click.option("--notify-threshold-mb", default=500, show_default=True,
              help="MB ociosos para disparar notificação.")
@click.option("--remove", is_flag=True, help="Remover agendamento existente.")
@pass_ctx
def schedule_setup(ctx: dict, interval_hours: int, notify_threshold_mb: int, remove: bool) -> None:
    """Registra (ou remove) tarefa no Agendador de Tarefas do Windows."""
    import sys
    import subprocess as sp
    from pathlib import Path

    task_name = "MemoryGuardian_AppAudit"
    script_dir = Path.home() / ".memory-guardian"
    runner_path = script_dir / "run_audit.ps1"

    if remove:
        result = sp.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            click.secho(f"  Tarefa '{task_name}' removida.", fg="green")
        else:
            click.secho(f"  Não foi possível remover: {result.stderr.strip()}", fg="red")
        return

    # Criar script PowerShell runner
    python_exe = sys.executable.replace("\\", "\\\\")
    script_dir.mkdir(parents=True, exist_ok=True)
    runner_content = f"""# Memory Guardian — Monitoramento automático
# Gerado por: memory-guardian schedule-setup
$python = "{python_exe}"
$args = @("-m", "memory_guardian.cli.main", "app-audit", "--notify")
$process = Start-Process -FilePath $python -ArgumentList $args `
    -WorkingDirectory "{str(Path.home() / '.memory-guardian').replace(chr(92), chr(92)*2)}" `
    -WindowStyle Hidden -PassThru
$process.WaitForExit(120000)
"""
    runner_path.write_text(runner_content, encoding="utf-8")
    click.echo(f"  Script de execução criado: {runner_path}")

    # Registrar no Task Scheduler
    # Disparar a cada N horas
    trigger_interval = f"PT{interval_hours}H"
    schtasks_cmd = [
        "schtasks", "/Create", "/F",
        "/TN", task_name,
        "/TR", f'powershell -NonInteractive -WindowStyle Hidden -File "{runner_path}"',
        "/SC", "HOURLY",
        "/MO", str(interval_hours),
        "/ST", "00:00",
        "/RL", "HIGHEST",
    ]
    result = sp.run(schtasks_cmd, capture_output=True, text=True)
    if result.returncode == 0:
        click.secho(
            f"\n  ✓ Tarefa '{task_name}' registrada com sucesso!\n"
            f"  Execução automática a cada {interval_hours}h\n"
            f"  Notificação quando houver ≥ {notify_threshold_mb} MB ociosos\n",
            fg="green",
        )
        click.echo(f"  Para remover: memory-guardian schedule-setup --remove")
        click.echo(f"  Para ver: schtasks /Query /TN {task_name}")
    else:
        click.secho(
            f"\n  Falha ao registrar tarefa:\n  {result.stderr.strip()}\n"
            f"\n  Execute como Administrador ou registre manualmente:",
            fg="red",
        )
        click.echo(f"  {' '.join(schtasks_cmd)}")


if __name__ == "__main__":
    main()
