# Memory Guardian

**Safe Windows memory monitoring — CLI + automatic audit + Claude Code skill.**

[![CI](https://github.com/jonnipm-web/memory-guardian/actions/workflows/ci.yml/badge.svg)](https://github.com/jonnipm-web/memory-guardian/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-blue)](https://www.microsoft.com/windows)

> Leia em Português: [README.pt-BR.md](README.pt-BR.md)

---

## What problem does it solve?

Windows machines accumulate long-running processes that hold memory without doing useful work: abandoned sessions, zombie processes, slow memory leaks, and browser tabs open for days. Standard task managers show *what* is using memory but give no context about *why* or *whether it is safe to act*.

Memory Guardian provides:

- **Safe observation first** — read-only by default, never touches a process without explicit config.
- **Anomaly detection** — sustained memory growth (leaks), zombie processes, idle processes holding RAM.
- **Multi-app audit** — single-pass audit of Claude Code, Codex, ChatGPT Desktop, Chrome, and Edge.
- **Scheduled monitoring** — Windows Task Scheduler integration with toast notifications.
- **Historical tracking** — SQLite database, trend analysis over hours/days.
- **Claude Code skill** — Claude can interpret findings and guide decisions.

---

## Installation

**Requirements:** Python 3.9+, Windows 10/11.

```bash
pip install memory-guardian
```

Or from source:

```bash
git clone https://github.com/jonnipm-web/memory-guardian.git
cd memory-guardian
pip install -e ".[dev]"
```

> **Note:** After installing, the `memory-guardian` command may not be found if `%APPDATA%\Python\Python3xx\Scripts` is not in your PATH. Fix it once:
> ```powershell
> # Run in PowerShell (no admin needed)
> $p = "$env:APPDATA\Python\Python$(python -c 'import sys; v=sys.version_info; print(f\"{v.major}{v.minor}\")')\Scripts"
> [Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";$p", "User")
> ```
> Then restart your terminal.

---

## Quick start

```bash
# Single memory snapshot (always safe — read-only)
memory-guardian snapshot

# Full analysis with anomaly detection
memory-guardian analyze

# Continuous monitoring every 60 s
memory-guardian monitor --interval 60

# Memory trend from the last 24 h
memory-guardian history

# Generate a default config file
memory-guardian config-init
```

---

## Multi-app audit (Claude Code, Codex, ChatGPT, Chrome, Edge)

The `app-audit` command checks all major memory-heavy applications in a single pass:

```bash
# Show all apps and idle instances
memory-guardian app-audit

# Specific apps only
memory-guardian app-audit --apps claude,codex,chrome

# Send a Windows toast notification if reclaimable memory >= 500 MB
memory-guardian app-audit --notify

# Terminate specific idle instances by PID (requires readonly_mode: false in config)
memory-guardian app-audit --close-idle --pids 1234,5678

# Dry run — shows what would happen without acting
memory-guardian app-audit --close-idle --pids 1234 --dry-run
```

**Supported apps:** `claude`, `codex`, `chatgpt`, `chrome`, `edge`

**Status legend:**

| Symbol | Meaning |
|--------|---------|
| `★ CURRENT` | This active session — never close |
| `▶ ACTIVE` | Currently doing work — do not close |
| `◉ IDLE` | CPU ≈ 0% — candidate to close |
| `◌ RECENT` | Just started — wait before deciding |

---

## Claude Code instance audit

The `claude-audit` command focuses specifically on Claude Code and Codex:

```bash
# Audit all Claude instances (read-only)
memory-guardian claude-audit

# JSON output for detailed analysis
memory-guardian claude-audit --json

# Simulate closing idle instances (dry-run)
memory-guardian claude-audit --close-idle --dry-run

# Close specific idle instances by PID
memory-guardian claude-audit --close-idle --pids 3848,10204
```

---

## Scheduled automatic monitoring

Register a task in Windows Task Scheduler to run every 2 hours automatically:

```bash
# Register (requires running once as Administrator)
memory-guardian schedule-setup --interval-hours 2

# Remove the scheduled task
memory-guardian schedule-setup --remove
```

Or register manually in an **Administrator** PowerShell:

```powershell
schtasks /Create /F /TN MemoryGuardian_AppAudit `
  /TR "$env:APPDATA\Python\Python314\Scripts\memory-guardian.exe app-audit --notify" `
  /SC HOURLY /MO 2 /ST 00:00 /RL HIGHEST
```

The task runs `app-audit --notify` and sends a Windows toast notification when reclaimable memory exceeds the configured threshold.

---

## Claude Code skill

This project ships with a Claude Code skill that lets Claude interpret memory data and guide decisions interactively.

### Installation (one-time)

**Windows:**
```powershell
# Copy the skill to Claude Code's global skills directory
Copy-Item -Recurse .claude\skills\memory-guardian $env:USERPROFILE\.claude\skills\memory-guardian
```

**macOS / Linux:**
```bash
cp -r .claude/skills/memory-guardian ~/.claude/skills/
```

### Using the skill

After installing, start a Claude Code session and type any of these trigger phrases:

```
"What is using my memory?"
"Take a memory snapshot"
"Memory Guardian"
"Check for memory leaks"
"Analyze memory"
```

Claude will automatically use the `memory-guardian` CLI, interpret the results, and suggest safe actions.

### Typical workflow with Claude

1. Run `memory-guardian analyze --json` and paste the output in the chat.
2. Ask Claude to interpret the findings.
3. If a process looks suspicious, ask Claude whether it is safe to add to the allowlist.
4. With `dry_run: true`, enable `readonly_mode: false` in config.
5. Confirm no protected processes are affected.
6. Enable live termination only after explicit review.

See [`.claude/skills/memory-guardian/SKILL.md`](.claude/skills/memory-guardian/SKILL.md) for the full skill reference.

---

## Security model

| Situation | Behaviour |
|-----------|-----------|
| `readonly_mode: true` (default) | No process is ever touched |
| Process not in allowlist | Cannot be terminated, even if flagged as risky |
| Protected process | Always blocked regardless of config |
| `dry_run: true` | Shows what would happen, takes no action |
| Force-kill (SIGKILL) | Never used — graceful SIGTERM only |

**Always-protected categories:**
- Windows system services (`lsass.exe`, `svchost.exe`, `csrss.exe`, …)
- Security / antivirus software
- IDEs (VS Code, PyCharm, Visual Studio, …)
- Python and Node.js runtimes
- MetaTrader MT4/MT5
- Docker and WSL
- Databases (PostgreSQL, MySQL, MongoDB, Redis)
- Claude Code and AI agents (including this session)

---

## Configuration

Run `memory-guardian config-init` to generate `~/.memory-guardian/config.yaml`, then edit:

```yaml
policy:
  readonly_mode: true      # Set false ONLY after thorough validation
  dry_run: true            # Always start here
  allowlist:               # Only these processes may ever be terminated
    - my_script.exe
  protected_names:         # Extra names to never touch
    - important_daemon.exe

monitoring:
  interval_seconds: 60
  history_retention_days: 30

alerts:
  memory_warning_percent: 85
  memory_critical_percent: 95
```

---

## Architecture

```
memory-guardian/
├── src/memory_guardian/
│   ├── models/            # Data structures (ProcessInfo, SystemSnapshot)
│   ├── core/
│   │   ├── collector.py   # psutil-based data collection
│   │   ├── analyzer.py    # Anomaly detection (leaks, zombies, idle)
│   │   ├── policy.py      # Security policy engine + allowlist
│   │   ├── reporter.py    # Text and JSON report generation
│   │   ├── claude_audit.py # Claude Code instance auditor
│   │   └── app_audit.py   # Multi-app auditor (Chrome, Edge, Codex…)
│   ├── config/            # YAML config loading with deep-merge
│   ├── history/           # SQLite snapshot history
│   ├── notify.py          # Windows toast notifications (no extra deps)
│   └── cli/               # Click-based CLI
├── tests/                 # 33 pytest tests
├── .claude/skills/        # Claude Code skill (SKILL.md)
└── examples/              # Example config
```

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Known limitations

- Requires elevated privileges to inspect some system processes (handled gracefully — those are skipped).
- CPU percentages for the first snapshot are always `0.0` — psutil needs two readings.
- Leak detection requires at least 3 consecutive snapshots with sustained growth.
- Toast notifications require Windows 10/11.
- macOS and Linux support planned but not yet implemented.

---

## Roadmap

- [ ] v0.2 — Background daemon with configurable notifications
- [ ] v0.3 — macOS and Linux support
- [ ] v0.4 — Web dashboard (local, read-only)
- [ ] v0.5 — Integration with Windows Event Log
- [ ] v1.0 — Stable API and plugin interface

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All contributions welcome.

## Security

See [SECURITY.md](SECURITY.md) for the responsible disclosure policy.

## License

[MIT](LICENSE) — free to use, modify and distribute.
