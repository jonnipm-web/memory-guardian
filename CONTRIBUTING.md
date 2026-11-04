# Contributing to Memory Guardian

Thank you for your interest in contributing!

## Getting started

```bash
git clone https://github.com/YOUR_USERNAME/memory-guardian.git
cd memory-guardian
pip install -e ".[dev]"
```

## Running tests

```bash
pytest tests/ -v
```

## Code style

```bash
ruff check src/ tests/
mypy src/
```

## Submitting changes

1. Fork the repository.
2. Create a branch: `git checkout -b feature/my-feature`.
3. Make your changes and add tests.
4. Ensure `pytest` and `ruff` pass.
5. Open a pull request with a clear description.

## Security policy

Please read [SECURITY.md](SECURITY.md) before reporting vulnerabilities.

## Scope of contributions

- Bug fixes and tests: always welcome.
- New detection heuristics: open an issue first to discuss.
- New platforms (macOS, Linux): aligned with the roadmap — coordinate via issue.
- Changes to the safety policy or protected-process lists: requires explicit discussion and justification.

## Code of Conduct

Be respectful. Contributions from all backgrounds and experience levels are welcome.
