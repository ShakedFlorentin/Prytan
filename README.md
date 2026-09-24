<p align="center">
  <img src="assets/logo.svg" alt="Prytan" width="780">
</p>

<p align="center">
  <a href="https://github.com/ShakedFlorentin/Prytan/releases"><img src="https://img.shields.io/badge/version-2.0.0-gold" alt="Version 2.0.0"></a>
  <a href="https://github.com/ShakedFlorentin/Prytan"><img src="https://img.shields.io/badge/Claude_Code-Plugin-blueviolet" alt="Claude Code Plugin"></a>
  <a href="agents/_base/"><img src="https://img.shields.io/badge/agents-16-4f8ef7" alt="16 agents"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/python-3.11+-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/telemetry-none-brightgreen" alt="Zero Telemetry">
</p>

<h2 align="center">An AI agent organization for any project.</h2>

<p align="center"><em>Install the plugin. Run <code>/org-init</code>. Talk to Atlas.</em></p>

Prytan gives a project a small AI organization on top of Claude Code: **Atlas**, a chief
of staff you talk to, who dispatches a team of specialists (backend, frontend, QA,
security, devops, product, …), keeps a local knowledge graph of your code, and remembers
what the org has learned — without sending anything anywhere but your own Claude Code
session.

> **v2 is a rewrite.** v1 (the `install.sh` + `/init` wizard edition) is preserved at the
> [`v1.0.0` tag](https://github.com/ShakedFlorentin/Prytan/tree/v1.0.0). See
> [CHANGELOG.md](CHANGELOG.md).

## Install

```text
/plugin marketplace add ShakedFlorentin/Prytan
/plugin install prytan@prytan
/org-init
```

`/org-init` analyzes the repository and configures the org non-destructively: source
dirs, the agent roster, any domain agents the project needs, the code graph and memory.

For the terminal and scheduler entry points, install the Python package too:

```bash
pip install -e .          # Python 3.11+, one dependency (pyyaml)
org                       # chat with Atlas from the terminal
org-schedule nightly      # the nightly reflection run (see scripts/cron-install.py)
```

## What's inside

| Part | What it does |
|---|---|
| `agents/_base/` | 16 role charters — Atlas (chief of staff), backend, frontend, qa, security, devops, build, product, ux, growth, content, legal, tech, governance, reliability, reflection |
| `core/runtime/` | Orchestrator, agent runner, CLI and Telegram adapters, per-dispatch write permissions, token metering |
| `core/scheduler/` | Nightly reflection and scheduled meetings; `scripts/cron-install.py` installs them |
| `core/knowledge/codegrapher/` | Offline code graph — `python3 -m core.knowledge.codegrapher scan .` / `query <term>` |
| `core/knowledge/memory/` | Shared `memory/` facts plus prompt-time recall (below) |
| `core/protocol/` | Comm dirs agents coordinate through: `.inbox/`, `.handoffs/`, `.proposals/`, `.logs/` |
| `skills/org-onboarding/` | The skill behind `/org-init` |

### Memory that only speaks when it's relevant

On every prompt, Prytan checks whether anything the org remembers is actually about what
you asked — and injects at most three memories, each with the line that states the fact.
Most prompts get nothing.

- **Words propose, meaning decides.** Candidates come from `memory/`, the comm dirs,
  per-agent logs and saved turns, matched per paragraph (not per file). If a local
  [Ollama](https://ollama.com) embedding model is available, it decides which candidates
  are really about the prompt; otherwise a strict word gate does.
- **Optional semantic check:** `ollama pull embeddinggemma`, then
  `python3 -m core.knowledge.memory warm`. Vectors are cached locally; recall falls back to
  words whenever Ollama is unavailable.
- **Measure, don't guess:** `python3 -m core.knowledge.memory eval labels.jsonl` scores
  recall against labeled prompts (`{"prompt": …, "expect": [path substrings]}`; an empty
  `expect` means "inject nothing").
- **Conversation store:** each finished turn is saved to `.logs/conversations.jsonl`
  (local, gitignored, 500-char cap, secrets redacted) so later sessions can recall it.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- Python 3.11+
- Optional: Ollama with an embedding model, for semantic recall
- Optional: a Telegram bot (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) to talk to Atlas
  from your phone — `python -m core.runtime.telegram_main`

## Development

```bash
pip install -e ".[dev]"
python -m pytest
```

## License

MIT — see [LICENSE](LICENSE). Privacy: [PRIVACY.md](PRIVACY.md). Security:
[SECURITY.md](SECURITY.md).
