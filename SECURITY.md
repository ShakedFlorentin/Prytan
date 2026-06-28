# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Prytan, please **do not open a public GitHub issue**.

Report it privately via [GitHub's private vulnerability reporting](https://github.com/ShakedFlorentin/Prytan/security/advisories/new).

Include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact

You can expect an acknowledgement within 48 hours and a fix or mitigation plan within 7 days for confirmed vulnerabilities.

## Scope

Security reports are in scope for:
- The agent scaffolding files (`.claude/agents/`, `.claude/hooks/`, `scripts/`)
- The `codegrapher` knowledge graph engine
- The Telegram bot interface (`scripts/telegram-bot.py`)
- The safety layer (`escalation_guard.py`, `claim_guard.py`, `write_proposals.py`)

Out of scope: vulnerabilities in Claude Code or the Anthropic API itself — report those directly to [Anthropic](https://www.anthropic.com/security).

## Security Model

Prytan is designed to run **fully locally**. It does not send telemetry, does not contact external servers (except the Anthropic API via Claude Code), and does not store credentials.

- Agent decisions that are irreversible (`one_way`, `strategic_fork`) require explicit human approval before execution.
- File writes to source directories require a human-gated proposal (`write_proposals.py`).
- The budget governor (`cost_governor.py`) halts all agent runs if the monthly token cap is exceeded.

See [PRIVACY.md](PRIVACY.md) for the full data flow description.
