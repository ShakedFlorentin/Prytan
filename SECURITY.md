# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Prytan, please **do not open a public GitHub
issue**. Report it privately via
[GitHub's private vulnerability reporting](https://github.com/ShakedFlorentin/Prytan/security/advisories/new).

Include a description, steps to reproduce, and the potential impact. You can expect an
acknowledgement within 48 hours and a fix or mitigation plan within 7 days for confirmed
vulnerabilities.

## Scope

In scope:
- Agent charters and the plugin manifest (`agents/`, `.claude-plugin/`, `hooks/`)
- The runtime (`core/runtime/`), including per-dispatch permissions (`perms.py`) and the
  Telegram adapter
- The knowledge layer (`core/knowledge/`): codegrapher, memory recall, the conversation
  store and its secret redaction

Out of scope: vulnerabilities in Claude Code, the Anthropic API, Ollama or Telegram
themselves — report those to their maintainers.

## Security Model

Prytan runs **fully locally** and sends no telemetry.

- Each agent dispatch gets a generated allow-list of the directories it may write to
  (its own log dir and `memory/`, plus deliverable dirs for write dispatches); the
  permission file itself lives outside every write-allowed dir.
- Saved conversation turns are capped and pass through secret redaction (private keys,
  URL credentials, JWTs, vendor tokens, random-looking blobs, `KEY=value`) before they
  are written, and the store is gitignored.
- Memory hooks never block a session: any error exits silently.

See [PRIVACY.md](PRIVACY.md) for the full data-flow description.
