# Changelog

All notable changes to Memory Guardian are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.1.0] — 2026-11-04

### Added
- Core data models: `ProcessInfo`, `SystemSnapshot`, `MemoryStats`, `SwapStats`
- `SystemCollector` — psutil-based process and memory collection
- `MemoryAnalyzer` — detects memory leaks (sustained growth), zombie processes, idle heavy processes
- `PolicyEngine` — hard-coded protection for Windows system/security processes, IDEs, Python, Node, MT4/MT5, Docker, databases, Claude Code agents; allowlist-based termination gate
- `Reporter` — text and JSON report generation with save-to-disk support
- YAML configuration with deep-merge over defaults
- SQLite history store (`HistoryStore`) with trend queries and automatic purge
- CLI commands: `snapshot`, `analyze`, `monitor`, `history`, `config-init`, `version`
- Claude Code skill (`SKILL.md`) for integration with the agent
- Bilingual documentation: English (`README.md`) and Brazilian Portuguese (`README.pt-BR.md`)
- GitHub Actions CI workflow (lint + tests on Python 3.9, 3.10, 3.11, 3.12)
- MIT license
