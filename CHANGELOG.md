# Changelog

## 2.0.0 — 2026-09-24

A rewrite. v1 is preserved at the `v1.0.0` tag.

**Changed**
- Ships as a Claude Code plugin (`.claude-plugin/`): `/plugin install prytan@prytan`, then
  `/org-init` (replaces v1's `install.sh` + `/init` wizard).
- New structure: `agents/_base/` role charters led by Atlas (chief of staff), a `core/`
  Python package (runtime, scheduler, knowledge, protocol) and `org` / `org-schedule`
  entry points.
- Comm dirs are `.inbox/`, `.handoffs/`, `.proposals/`, `.logs/`; shared facts live in
  `memory/`.

**Added**
- Prompt-time memory recall that injects only relevant memories: per-paragraph word
  matching proposes candidates, an optional local Ollama embedding model decides
  (`core/knowledge/relevance.py`, `core/knowledge/semantic.py`).
- `python3 -m core.knowledge.memory eval` (score recall on labeled prompts) and `warm`
  (pre-embed memories).
- Conversation store: finished turns saved to `.logs/conversations.jsonl`, capped and
  secret-redacted.
- Per-dispatch write allow-lists (`core/runtime/perms.py`) and token metering.

**Removed**
- v1's `scripts/*.py` suite (cost governor, escalation/claim guards, write proposals,
  goal loop, …) and `setup/configure.py`. Use the `v1.0.0` tag if you depend on them.

## 1.0.0

The original release: `install.sh` + `/init` wizard, 16 agents, codegrapher, Telegram bot,
cost governor and safety scripts.
