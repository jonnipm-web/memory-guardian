# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Send a private report to the maintainer via GitHub's
[Security Advisories](https://github.com/YOUR_USERNAME/memory-guardian/security/advisories/new)
feature, or by email (see the repository profile).

Include:
- A clear description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

You will receive an acknowledgement within 72 hours and a resolution timeline
within 7 days.

## Security design principles

- Read-only by default — no process is ever modified without explicit allowlist configuration.
- Hard-coded protection list for system-critical processes cannot be overridden by config files.
- No network access, no telemetry, no data sent off-device.
- No credentials or tokens are collected or stored.
- Termination is always graceful (SIGTERM equivalent) — force-kill is never used.
- PID reuse is a known OS-level risk; the tool validates process name before any action.
