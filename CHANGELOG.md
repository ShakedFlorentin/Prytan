# Changelog

## Unreleased

**Changed**
- Semantic recall's meaning-only bar is back to 0.55 cosine (from 0.50). At 0.50 a
  real operational prompt ("fix the tests lint warnings too") pulled in unrelated
  memories at 0.50-0.52. Trade-off: a paraphrase with no shared words now needs a
  closer match to be recalled.

## 2.0.1 — 2026-09-24

**Changed**
- Semantic memory recall is now **opt-in**: set `memory: {semantic: true}` in
  `config.yaml`. By default recall uses the word gate only and contacts no local
  service, even if Ollama happens to be running. New projects get the setting written
  to `config.yaml` as `false` so it is easy to find.
- Session start only warms embeddings when semantic recall is on; `memory eval` follows
  the project setting (`--semantic` / `--lexical` override it).

**Fixed**
- Semantic recall no longer stalls prompts when Ollama has unloaded the model (a cold
  load takes 10-20 s): requests keep the model resident for 30 minutes, a failed call
  makes prompts skip Ollama for 60 s while a detached request loads it, and the
  per-prompt budget is 1 s.

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
