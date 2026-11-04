"""Notificações Windows nativas — sem dependências extras."""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_ICON_PATH = Path(__file__).parent / "assets" / "icon.ico"


def _ps_escape(text: str) -> str:
    return text.replace('"', '`"').replace("'", "`'").replace("\n", " ")


def toast(title: str, message: str, duration_ms: int = 8000) -> bool:
    """
    Mostra notificação balloon no system tray via PowerShell.
    Retorna True se enviou com sucesso.
    """
    if sys.platform != "win32":
        logger.debug("Toast notifications are Windows-only.")
        return False
    t = _ps_escape(title)
    m = _ps_escape(message)
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
$balloon = New-Object System.Windows.Forms.NotifyIcon
$balloon.Icon = [System.Drawing.SystemIcons]::Information
$balloon.Visible = $true
$balloon.ShowBalloonTip({duration_ms}, "{t}", "{m}", [System.Windows.Forms.ToolTipIcon]::Warning)
Start-Sleep -Milliseconds {duration_ms + 500}
$balloon.Dispose()
""".strip()
    try:
        subprocess.Popen(
            ["powershell", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return True
    except Exception as exc:
        logger.warning("Toast failed: %s", exc)
        return False


def write_alert_log(message: str, log_path: Optional[Path] = None) -> Path:
    """Grava alerta em arquivo de log de alertas."""
    import datetime
    if log_path is None:
        log_path = Path.home() / ".memory-guardian" / "alerts.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}]  {message}\n")
    return log_path


def notify_idle_apps(
    app_summaries: dict,
    total_memory_mb: float,
    threshold_mb: float = 500.0,
    alert_log: Optional[Path] = None,
) -> None:
    """Envia notificação consolidada se houver apps ociosos relevantes."""
    lines = []
    for key, summary in app_summaries.items():
        reclaimable = summary.reclaimable_mb
        if reclaimable >= threshold_mb:
            lines.append(
                f"• {summary.profile.display_name}: "
                f"{len(summary.idle_sessions)} ociosa(s), "
                f"{reclaimable / 1024:.1f} GB recuperável"
            )

    if not lines:
        return

    title = f"Memory Guardian — {total_memory_mb / 1024:.1f} GB em uso"
    message = "Apps com instâncias ociosas:\n" + "\n".join(lines)

    toast(title, message)
    write_alert_log(message.replace("\n", " | "), alert_log)
