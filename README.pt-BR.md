# Memory Guardian

**Monitoramento de memória Windows com segurança — CLI + auditoria automática + skill para o Claude Code.**

[![CI](https://github.com/jonnipm-web/memory-guardian/actions/workflows/ci.yml/badge.svg)](https://github.com/jonnipm-web/memory-guardian/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-blue)](https://www.microsoft.com/windows)

> Read in English: [README.md](README.md)

---

## Qual problema resolve?

Com o tempo, o Windows acumula processos de longa duração que ocupam memória sem fazer trabalho útil: sessões abandonadas, processos zombie, vazamentos lentos de memória e abas do navegador abertas há dias. Os gerenciadores de tarefas padrão mostram *o que* está usando memória, mas não *por quê* nem *se é seguro agir*.

Memory Guardian oferece:

- **Observação segura primeiro** — somente leitura por padrão, nunca toca em processo sem configuração explícita.
- **Detecção de anomalias** — crescimento sustentado de memória (vazamentos), processos zombie, processos ociosos segurando RAM.
- **Auditoria multi-app** — passagem única auditando Claude Code, Codex, ChatGPT Desktop, Chrome e Edge.
- **Monitoramento agendado** — integração com o Agendador de Tarefas do Windows com notificações toast.
- **Histórico** — banco SQLite com análise de tendência por horas/dias.
- **Skill para o Claude Code** — o Claude interpreta os resultados e guia as decisões.

---

## Instalação

**Requisitos:** Python 3.9+, Windows 10/11.

```bash
pip install memory-guardian
```

Ou a partir do código-fonte:

```bash
git clone https://github.com/jonnipm-web/memory-guardian.git
cd memory-guardian
pip install -e ".[dev]"
```

> **Aviso:** Após instalar, o comando `memory-guardian` pode não ser encontrado se `%APPDATA%\Python\Python3xx\Scripts` não estiver no PATH. Corrija uma vez:
> ```powershell
> # Execute no PowerShell (sem precisar de Administrador)
> $p = "$env:APPDATA\Python\Python$(python -c 'import sys; v=sys.version_info; print(f\"{v.major}{v.minor}\")')\Scripts"
> [Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";$p", "User")
> ```
> Depois reinicie o terminal.

---

## Início rápido

```bash
# Snapshot único de memória (sempre seguro — somente leitura)
memory-guardian snapshot

# Análise completa com detecção de anomalias
memory-guardian analyze

# Monitoramento contínuo a cada 60 s
memory-guardian monitor --interval 60

# Tendência de memória das últimas 24 h
memory-guardian history

# Gerar arquivo de configuração padrão
memory-guardian config-init
```

---

## Auditoria multi-app (Claude Code, Codex, ChatGPT, Chrome, Edge)

O comando `app-audit` verifica todos os aplicativos pesados em uma única passagem:

```bash
# Ver todos os apps e instâncias ociosas
memory-guardian app-audit

# Apps específicos
memory-guardian app-audit --apps claude,codex,chrome

# Enviar notificação toast se memória recuperável >= 500 MB
memory-guardian app-audit --notify

# Encerrar instâncias ociosas por PID (requer readonly_mode: false no config)
memory-guardian app-audit --close-idle --pids 1234,5678

# Dry run — mostra o que aconteceria sem executar
memory-guardian app-audit --close-idle --pids 1234 --dry-run
```

**Apps suportados:** `claude`, `codex`, `chatgpt`, `chrome`, `edge`

**Legenda de status:**

| Símbolo | Significado |
|---------|-------------|
| `★ ATUAL` | Esta sessão ativa — nunca encerrar |
| `▶ ATIVO` | Executando trabalho agora — não encerrar |
| `◉ OCIOSO` | CPU ≈ 0% — candidato a fechar |
| `◌ RECENTE` | Recém-iniciado — aguardar antes de decidir |

---

## Auditoria de instâncias Claude Code

O comando `claude-audit` foca especificamente no Claude Code e Codex:

```bash
# Auditar todas as instâncias Claude (somente leitura)
memory-guardian claude-audit

# Saída JSON para análise detalhada
memory-guardian claude-audit --json

# Simular encerramento de instâncias ociosas (dry-run)
memory-guardian claude-audit --close-idle --dry-run

# Encerrar instâncias ociosas por PID
memory-guardian claude-audit --close-idle --pids 3848,10204
```

---

## Monitoramento automático agendado

Registra uma tarefa no Agendador de Tarefas do Windows para rodar a cada 2 horas automaticamente:

```bash
# Registrar (requer executar como Administrador uma vez)
memory-guardian schedule-setup --interval-hours 2

# Remover a tarefa agendada
memory-guardian schedule-setup --remove
```

Ou registrar manualmente em um PowerShell **Administrador**:

```powershell
schtasks /Create /F /TN MemoryGuardian_AppAudit `
  /TR "$env:APPDATA\Python\Python314\Scripts\memory-guardian.exe app-audit --notify" `
  /SC HOURLY /MO 2 /ST 00:00 /RL HIGHEST
```

A tarefa roda `app-audit --notify` e envia uma notificação toast quando a memória recuperável ultrapassa o limite configurado.

---

## Skill para o Claude Code

Este projeto inclui uma skill para o Claude Code que permite ao Claude interpretar dados de memória e guiar decisões de forma interativa.

### Instalação (uma vez)

**Windows:**
```powershell
# Copiar a skill para o diretório global de skills do Claude Code
Copy-Item -Recurse .claude\skills\memory-guardian $env:USERPROFILE\.claude\skills\memory-guardian
```

**macOS / Linux:**
```bash
cp -r .claude/skills/memory-guardian ~/.claude/skills/
```

### Como usar a skill

Após instalar, inicie uma sessão do Claude Code e diga qualquer uma destas frases:

```
"O que está usando minha memória?"
"Tire um snapshot de memória"
"Memory Guardian"
"Verifique vazamentos de memória"
"Analise a memória"
```

O Claude usará automaticamente o CLI `memory-guardian`, interpretará os resultados e sugerirá ações seguras.

### Fluxo típico com o Claude

1. Execute `memory-guardian analyze --json` e cole a saída no chat.
2. Peça ao Claude para interpretar os resultados.
3. Se um processo parecer suspeito, pergunte ao Claude se é seguro adicioná-lo ao allowlist.
4. Com `dry_run: true`, habilite `readonly_mode: false` no config.
5. Confirme que nenhum processo protegido será afetado.
6. Habilite o encerramento real somente após revisão explícita.

Veja [`.claude/skills/memory-guardian/SKILL.md`](.claude/skills/memory-guardian/SKILL.md) para a referência completa da skill.

---

## Modelo de segurança

| Situação | Comportamento |
|----------|---------------|
| `readonly_mode: true` (padrão) | Nenhum processo é tocado |
| Processo não está no allowlist | Não pode ser encerrado, mesmo se sinalizado como risco |
| Processo protegido | Sempre bloqueado independente do config |
| `dry_run: true` | Mostra o que aconteceria sem executar |
| Force-kill (SIGKILL) | Nunca usado — somente SIGTERM gracioso |

**Categorias sempre protegidas:**
- Serviços do sistema Windows (`lsass.exe`, `svchost.exe`, `csrss.exe`, …)
- Software de segurança / antivírus
- IDEs (VS Code, PyCharm, Visual Studio, …)
- Runtimes Python e Node.js
- MetaTrader MT4/MT5
- Docker e WSL
- Bancos de dados (PostgreSQL, MySQL, MongoDB, Redis)
- Claude Code e agentes de IA (incluindo a sessão atual)

---

## Configuração

Execute `memory-guardian config-init` para gerar `~/.memory-guardian/config.yaml`, depois edite:

```yaml
policy:
  readonly_mode: true      # Defina false SOMENTE após validação completa
  dry_run: true            # Sempre comece aqui
  allowlist:               # Somente estes processos podem ser encerrados
    - meu_script.exe
  protected_names:         # Nomes extras que nunca devem ser tocados
    - servico_importante.exe

monitoring:
  interval_seconds: 60
  history_retention_days: 30

alerts:
  memory_warning_percent: 85
  memory_critical_percent: 95
```

---

## Arquitetura

```
memory-guardian/
├── src/memory_guardian/
│   ├── models/            # Estruturas de dados (ProcessInfo, SystemSnapshot)
│   ├── core/
│   │   ├── collector.py   # Coleta de dados via psutil
│   │   ├── analyzer.py    # Detecção de anomalias (vazamentos, zombies, ociosos)
│   │   ├── policy.py      # Motor de política de segurança + allowlist
│   │   ├── reporter.py    # Geração de relatórios em texto e JSON
│   │   ├── claude_audit.py # Auditor de instâncias Claude Code
│   │   └── app_audit.py   # Auditor multi-app (Chrome, Edge, Codex…)
│   ├── config/            # Carregamento de config YAML com deep-merge
│   ├── history/           # Histórico SQLite de snapshots
│   ├── notify.py          # Notificações toast Windows (sem dependências extras)
│   └── cli/               # CLI baseado em Click
├── tests/                 # 33 testes pytest
├── .claude/skills/        # Skill para Claude Code (SKILL.md)
└── examples/              # Config de exemplo
```

---

## Rodando os testes

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Limitações conhecidas

- Requer privilégios elevados para inspecionar alguns processos do sistema (tratado graciosamente — esses são ignorados).
- Percentuais de CPU no primeiro snapshot são sempre `0.0` — o psutil precisa de duas leituras.
- Detecção de vazamento requer pelo menos 3 snapshots consecutivos com crescimento sustentado.
- Notificações toast requerem Windows 10/11.
- Suporte a macOS e Linux planejado, mas ainda não implementado.

---

## Roadmap

- [ ] v0.2 — Daemon em background com notificações configuráveis
- [ ] v0.3 — Suporte a macOS e Linux
- [ ] v0.4 — Dashboard web (local, somente leitura)
- [ ] v0.5 — Integração com o Log de Eventos do Windows
- [ ] v1.0 — API estável e interface de plugins

---

## Contribuindo

Veja [CONTRIBUTING.md](CONTRIBUTING.md). Todas as contribuições são bem-vindas.

## Segurança

Veja [SECURITY.md](SECURITY.md) para a política de divulgação responsável.

## Licença

[MIT](LICENSE) — livre para usar, modificar e distribuir.
