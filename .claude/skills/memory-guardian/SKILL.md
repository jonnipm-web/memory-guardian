# memory-guardian

Monitors, diagnoses, and safely optimizes Windows memory usage. Integrates with Claude Code as a reusable skill.

## When to invoke this skill

Invoke when the user asks any of the following:
- "What is using my memory?"
- "Take a memory snapshot"
- "Analyze memory / check for leaks"
- "Monitor memory in the background"
- "Show memory history / trend"
- "Is there a process I can safely kill?"
- "Memory Guardian" (by name)

## Prerequisites

Install Memory Guardian before using:

```bash
pip install memory-guardian
# or, from source:
pip install -e "C:\Users\jpaul\Documents\memory-guardian"
```

Verify installation:
```bash
memory-guardian version
```

## Commands

### Quick snapshot
```bash
memory-guardian snapshot
```
Takes a single reading of RAM, swap, CPU and top processes.
Safe — read-only, no side effects.

### Full analysis
```bash
memory-guardian analyze
```
Collects a snapshot and runs anomaly detection:
- High-memory processes
- Potential memory leaks (sustained growth)
- Zombie processes
- Idle processes holding memory

```bash
memory-guardian analyze --json          # machine-readable output
memory-guardian analyze --save          # save report to ~/.memory-guardian/reports/
```

### Continuous monitoring
```bash
memory-guardian monitor --interval 60   # snapshot every 60 s
memory-guardian monitor --count 10      # stop after 10 snapshots
memory-guardian monitor --save          # auto-save each report
```
Press Ctrl+C to stop.

### History / trend
```bash
memory-guardian history                 # last 24 h
memory-guardian history --hours 48
memory-guardian history --json
```

### Initialize config
```bash
memory-guardian config-init             # writes ~/.memory-guardian/config.yaml
```
Edit the generated file to adjust policy, alert thresholds and allowlist.

## Safety rules (always enforced)

- **Read-only by default** — never terminates anything unless `readonly_mode: false` is explicitly set in config.
- **Protected processes cannot be killed** regardless of config. Includes: Windows system services, security software, IDEs (VS Code, PyCharm…), Python/Node runtimes, MetaTrader (MT4/MT5), Docker, databases, and Claude Code agents.
- **Allowlist required** — termination is only possible for processes explicitly named in `config.yaml` under `policy.allowlist`.
- **Dry-run mode** (`dry_run: true`) shows what would happen without taking action.
- **Never uses SIGKILL / force-kill** — graceful termination only.

## Example config additions (allowlist)

```yaml
policy:
  readonly_mode: false   # only after validation
  dry_run: true          # start with dry-run
  allowlist:
    - my_script.exe
    - old_tool.exe
  protected_names:
    - important_service.exe
```

## Output files

| File | Purpose |
|------|---------|
| `~/.memory-guardian/history.db` | SQLite snapshot history |
| `~/.memory-guardian/reports/` | Saved text/JSON reports |
| `~/.memory-guardian/memory-guardian.log` | Runtime log |
| `~/.memory-guardian/config.yaml` | User configuration |

## Auditoria de instâncias Claude Code (caso de uso principal)

Quando você perceber que há muitas instâncias do Claude Code abertas consumindo memória:

```bash
# 1. Auditar (somente leitura — seguro sempre)
memory-guardian claude-audit

# 2. Ver em JSON para análise detalhada
memory-guardian claude-audit --json

# 3. Simular encerramento sem executar (dry-run)
memory-guardian claude-audit --close-idle --dry-run

# 4. Encerrar com confirmação por PID (requer readonly_mode: false no config)
memory-guardian claude-audit --close-idle
```

**Legenda de status:**
- `★ ATUAL` — esta sessão ativa — nunca encerrar
- `▶ ATIVO` — executando tarefa agora — não encerrar
- `◉ OCIOSO` — CPU ≈ 0% por vários segundos — candidato a fechar
- `◌ RECENTE` — recém-iniciado — aguardar antes de decidir

**Para habilitar encerramento**, edite `~/.memory-guardian/config.yaml`:
```yaml
policy:
  readonly_mode: false
  dry_run: false   # somente após confirmar com dry-run
```

## Auditoria multi-app (Claude Code, Codex, Chrome, Edge)

Monitoramento centralizado de todos os apps pesados em uma única passagem:

```bash
# Ver todos os apps e instâncias ociosas
memory-guardian app-audit

# Apps específicos
memory-guardian app-audit --apps claude,codex,chrome

# Com notificação toast do Windows
memory-guardian app-audit --notify

# Encerrar por PID (após identificar no relatório)
memory-guardian app-audit --close-idle --pids 1234,5678

# Simulação sem executar
memory-guardian app-audit --close-idle --pids 1234 --dry-run
```

**Legenda de status:**
- `★ ATUAL` — esta sessão ativa — nunca encerrar
- `▶ ATIVO` — processo trabalhando agora — não encerrar
- `◉ OCIOSO` — CPU ≈ 0% — candidato a fechar
- `◌ RECENTE` — recém-iniciado — aguardar antes de decidir

**Apps suportados:** `claude`, `codex`, `chatgpt`, `chrome`, `edge`

## Monitoramento agendado (Task Scheduler)

Configura verificação automática a cada 2 horas com notificação:

```bash
# Registrar agendamento (requer terminal Administrador)
memory-guardian schedule-setup --interval-hours 2

# Remover agendamento
memory-guardian schedule-setup --remove
```

Ou registre manualmente em um terminal **Administrador**:
```
schtasks /Create /F /TN MemoryGuardian_AppAudit /TR "powershell -NonInteractive -WindowStyle Hidden -File \"C:\Users\jpaul\.memory-guardian\run_audit.ps1\"" /SC HOURLY /MO 2 /ST 00:00 /RL HIGHEST
```

O script gerado fica em: `~/.memory-guardian/run_audit.ps1`

## Typical workflow with Claude

1. Run `memory-guardian analyze --json` and paste the output here.
2. Ask Claude to interpret the findings.
3. If a process looks suspicious, ask Claude whether it is safe to add to the allowlist.
4. Only after review and with `dry_run: true`, enable `readonly_mode: false`.
5. Confirm no protected processes are affected.
6. Enable live termination only after explicit approval.
