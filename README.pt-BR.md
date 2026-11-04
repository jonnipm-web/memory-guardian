# Memory Guardian

**Monitoramento seguro e somente leitura de memória para Windows.**

[![CI](https://github.com/YOUR_USERNAME/memory-guardian/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/memory-guardian/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org)
[![Licença: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> English documentation: [README.md](README.md)

---

## Qual problema a ferramenta resolve?

Com o tempo, máquinas Windows acumulam processos de longa duração que ocupam memória sem executar trabalho útil: scripts abandonados, workers obsoletos, processos zumbi e aplicações com vazamentos lentos de memória. Os gerenciadores de tarefas padrão mostram *o que* está usando memória, mas não explicam *por quê* nem *se é seguro agir*.

O Memory Guardian oferece:

- **Observação segura primeiro** — somente leitura por padrão, nunca toca em um processo sem aprovação explícita na allowlist.
- **Detecção de anomalias** — detecta crescimento sustentado de memória (possíveis vazamentos), processos zumbi e processos ociosos que ocupam grandes quantidades de RAM.
- **Histórico** — armazena snapshots num banco SQLite local para visualizar tendências ao longo do tempo.
- **Integração com Claude Code** — skill reutilizável para que o Claude interprete os resultados e oriente as decisões.
- **Baixo consumo** — projetado para monitorar sem se tornar o próprio problema.

---

## Arquitetura

```
memory-guardian/
├── src/memory_guardian/
│   ├── models/        # Estruturas de dados (ProcessInfo, SystemSnapshot)
│   ├── core/
│   │   ├── collector.py   # Coleta de dados via psutil
│   │   ├── analyzer.py    # Detecção de anomalias (vazamentos, zumbis, ociosos)
│   │   ├── policy.py      # Motor de políticas de segurança + allowlist
│   │   └── reporter.py    # Geração de relatórios em texto e JSON
│   ├── config/        # Carregamento de config YAML com deep-merge
│   ├── history/       # Histórico SQLite de snapshots
│   └── cli/           # CLI baseada em Click
├── tests/             # Suite de testes Pytest
├── .claude/skills/    # Skill do Claude Code (SKILL.md)
└── docs/              # Documentação estendida
```

---

## Instalação

**Requisitos:** Python 3.9+, Windows 10/11 (suporte a macOS/Linux planejado).

```bash
pip install memory-guardian
```

Ou a partir do código-fonte:

```bash
git clone https://github.com/YOUR_USERNAME/memory-guardian.git
cd memory-guardian
pip install -e ".[dev]"
```

---

## Início rápido

```bash
# Snapshot único de memória (seguro, somente leitura)
memory-guardian snapshot

# Análise completa com detecção de anomalias
memory-guardian analyze

# Monitoramento contínuo a cada 60 s
memory-guardian monitor --interval 60

# Visualizar tendência de memória das últimas 24 h
memory-guardian history

# Gerar arquivo de configuração padrão
memory-guardian config-init
```

---

## Modelo de segurança

| Situação | Comportamento |
|----------|---------------|
| `readonly_mode: true` (padrão) | Nenhum processo é tocado |
| Processo fora da allowlist | Não pode ser encerrado, mesmo com risco alto |
| Processo protegido (sistema/segurança/IDE/MT5…) | Sempre bloqueado, independente da config |
| `dry_run: true` | Mostra o que aconteceria, sem executar ação |
| Kill forçado (SIGKILL) | Nunca utilizado — apenas encerramento gracioso |

Categorias protegidas (sempre seguras, definidas em código):
- Serviços de sistema do Windows (`lsass.exe`, `svchost.exe`, `csrss.exe`, …)
- Softwares de segurança / antivírus
- IDEs (VS Code, PyCharm, Visual Studio, …)
- Runtimes Python e Node.js
- MetaTrader MT4/MT5
- Docker e WSL
- Bancos de dados (PostgreSQL, MySQL, MongoDB, Redis)
- Claude Code e agentes de IA

---

## Configuração

Após executar `memory-guardian config-init`, edite `~/.memory-guardian/config.yaml`:

```yaml
policy:
  readonly_mode: true      # Defina false APENAS após validação completa
  dry_run: true            # Sempre comece com dry-run
  allowlist:               # Apenas esses processos podem ser encerrados
    - meu_script.exe
  protected_names:         # Nomes adicionais que nunca devem ser tocados
    - servico_importante.exe

monitoring:
  interval_seconds: 60
  history_retention_days: 30

alerts:
  memory_warning_percent: 85
  memory_critical_percent: 95
```

---

## Integração com Claude Code

```bash
# Instalar a skill (uma vez)
cp -r .claude/skills/memory-guardian ~/.claude/skills/

# Depois pergunte ao Claude:
# "Tire um snapshot de memória"
# "Analise a memória — há algum vazamento?"
# "Mostre a tendência de memória das últimas 6 horas"
```

Consulte [`.claude/skills/memory-guardian/SKILL.md`](.claude/skills/memory-guardian/SKILL.md) para a documentação completa da skill.

---

## Executando os testes

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Limitações conhecidas

- Requer privilégios elevados no Windows para inspecionar alguns processos de sistema (a ferramenta trata `AccessDenied` de forma segura e ignora esses processos).
- Os percentuais de CPU no primeiro snapshot após a inicialização são sempre `0.0` — o psutil precisa de duas leituras para calcular um valor significativo.
- A detecção de vazamentos exige pelo menos 3 snapshots consecutivos com crescimento sustentado antes de sinalizar um processo.
- O suporte a daemon em segundo plano está planejado, mas ainda não implementado.
- Suporte a macOS e Linux está no roadmap.

---

## Roadmap

- [ ] v0.2 — Daemon em segundo plano com notificações de alerta configuráveis
- [ ] v0.3 — Suporte a macOS e Linux
- [ ] v0.4 — Dashboard web local (somente leitura)
- [ ] v0.5 — Integração com o Log de Eventos do Windows
- [ ] v1.0 — API estável e interface de plugins

---

## Contribuição

Consulte [CONTRIBUTING.md](CONTRIBUTING.md). Todas as contribuições são bem-vindas.

## Segurança

Consulte [SECURITY.md](SECURITY.md) para a política de divulgação responsável.

## Licença

[MIT](LICENSE) — livre para usar, modificar e distribuir.
