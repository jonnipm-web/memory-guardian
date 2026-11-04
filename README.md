# Memory Guardian

**Safe, read-only memory monitoring and diagnostics for Windows.**

[![CI](https://github.com/YOUR_USERNAME/memory-guardian/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/memory-guardian/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> Read the Portuguese documentation: [README.pt-BR.md](README.pt-BR.md)

---

## What problem does it solve?

Over time, Windows machines accumulate long-running processes that hold onto memory without doing useful work: abandoned scripts, stale workers, zombie processes, and applications with slow memory leaks. Standard task managers show *what* is using memory but give no context about *why* or *whether it is safe to act*.

Memory Guardian provides:

- **Safe observation first** — read-only by default, never touches a process without explicit allowlist approval.
- **Anomaly detection** — detects sustained memory growth (possible leaks), zombie processes, and idle processes holding large amounts of RAM.
- **Historical tracking** — stores snapshots in a local SQLite database so you can see trends over time.
- **Claude Code integration** — a reusable skill so Claude can interpret findings and guide decisions.
- **Low footprint** — designed to monitor without itself becoming the problem.

---

## Architecture

```
memory-guardian/
├── src/memory_guardian/
│   ├── models/        # Data structures (ProcessInfo, SystemSnapshot)
│   ├── core/
│   │   ├── collector.py   # psutil-based data collection
│   │   ├── analyzer.py    # Anomaly detection (leaks, zombies, idle)
│   │   ├── policy.py      # Security policy engine + allowlist
│   │   └── reporter.py    # Text and JSON report generation
│   ├── config/        # YAML config loading with deep-merge
│   ├── history/       # SQLite snapshot history
│   └── cli/           # Click-based CLI
├── tests/             # Pytest test suite
├── .claude/skills/    # Claude Code skill (SKILL.md)
└── docs/              # Extended documentation
```

---

## Installation

**Requirements:** Python 3.9+, Windows 10/11 (macOS/Linux support planned).

```bash
pip install memory-guardian
```

Or install from source:

```bash
git clone https://github.com/YOUR_USERNAME/memory-guardian.git
cd memory-guardian
pip install -e ".[dev]"
```

---

## Quick start

```bash
# Single memory snapshot (safe, read-only)
memory-guardian snapshot

# Full analysis with anomaly detection
memory-guardian analyze

# Continuous monitoring every 60 s
memory-guardian monitor --interval 60

# View memory trend from last 24 h
memory-guardian history

# Generate a default config file
memory-guardian config-init
```

---

## Security model

| Situation | Behaviour |
|-----------|-----------|
| `readonly_mode: true` (default) | No process is ever touched |
| Process not in allowlist | Cannot be terminated, even if risky |
| Protected process (system/security/IDE/MT5…) | Always blocked, regardless of config |
| `dry_run: true` | Shows what would happen, takes no action |
| Force-kill (SIGKILL) | Never used — graceful termination only |

Protected categories (always safe, hard-coded):
- Windows system services (`lsass.exe`, `svchost.exe`, `csrss.exe`, …)
- Security / antivirus software
- IDEs (VS Code, PyCharm, Visual Studio, …)
- Python and Node.js runtimes
- MetaTrader MT4/MT5
- Docker and WSL
- Databases (PostgreSQL, MySQL, MongoDB, Redis)
- Claude Code and AI agents

---

## Configuration

After running `memory-guardian config-init`, edit `~/.memory-guardian/config.yaml`:

```yaml
policy:
  readonly_mode: true      # Set false ONLY after thorough validation
  dry_run: true            # Always start with dry-run
  allowlist:               # Only these may ever be terminated
    - my_script.exe
  protected_names:         # Extra names never to touch
    - important_daemon.exe

monitoring:
  interval_seconds: 60
  history_retention_days: 30

alerts:
  memory_warning_percent: 85
  memory_critical_percent: 95
```

---

## Claude Code integration

```bash
# Install the skill (once)
cp -r .claude/skills/memory-guardian ~/.claude/skills/

# Then ask Claude:
# "Take a memory snapshot"
# "Analyze memory — are there any leaks?"
# "Show memory trend for the last 6 hours"
```

See [`.claude/skills/memory-guardian/SKILL.md`](.claude/skills/memory-guardian/SKILL.md) for full skill documentation.

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Known limitations

- Requires elevated privileges on Windows to inspect some system processes (the tool handles `AccessDenied` gracefully and skips those processes).
- CPU percentages for the first snapshot after startup are always `0.0` — psutil needs two readings to calculate a meaningful value.
- Leak detection requires at least 3 consecutive snapshots with sustained memory growth before flagging a process.
- Background daemon support is planned but not yet implemented.
- macOS and Linux support is in the roadmap.

---

## Roadmap

- [ ] v0.2 — Background daemon with configurable alert notifications
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
