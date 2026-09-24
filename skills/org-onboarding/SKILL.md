---
name: org-onboarding
description: Use when the user runs /org-init — analyze a project and configure the agent org (source dirs, agent roster, new domain agents, codegrapher, memory), non-destructively.
---

# Org Onboarding

You are setting up the agent organization for the current project. You make the
DECISIONS; the framework provides mechanical primitives you call as shell commands
`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m core.onboarding_cli <cmd>`. Be decisive; only ask the user when genuinely
ambiguous.

## Procedure

1. **Analyze the project.** Glob/Read the build manifests (`package.json`,
   `pyproject.toml`, `go.mod`, `Cargo.toml`, `Makefile`, `pom.xml`, …) and the
   directory tree. Identify languages, the build system, and — crucially — which
   dir(s) hold the real SOURCE (could be `src`, `lib`, `app`, `internal`, `pkg`, or
   anything; do NOT assume a name). Ignore vendor/build/test dirs for indexing.

2. **Wire the knowledge layer (source).** Run
   `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m core.onboarding_cli scan <dir> [<dir>...]` with the source dir(s) you
   found, then `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m core.onboarding_cli wire-hook`. Record the choice:
   `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m core.onboarding_cli config-set codegrapher.source_dir <dir>`.
   If the project has a `books/` directory (reference pages with `title`/`chapter`/`explains` frontmatter), pass `--books books` to the scan command so book nodes are merged into the graph:
   `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m core.onboarding_cli scan <src> --books books`.
   Map any per-role shelves with `config-set books.<role> <book>`.

3. **Choose the roster.** From the 16 base agents, ENABLE the ones this project needs
   with `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m core.onboarding_cli install-agent <id>` (backend/frontend/qa/
   devops/security/etc.). Skip clearly-irrelevant roles. install-agent is
   NON-DESTRUCTIVE — it will not clobber an agent the project already defines.

4. **Author new domain agents — and ask WHO AUTHORS, not just who advises.** If the
   project needs expertise the 16 don't cover (an RTL agent for hardware, a
   data-engineer for a pipeline, an ML agent), AUTHOR one from
   `templates/agent-template.md`. For EACH such domain, first decide explicitly:
   does this domain have a real DELIVERABLE (RTL, a trained model, firmware, infra
   manifests, ...) that someone must actually WRITE — not just review? If so, that
   domain needs an **authoring** agent, chartered to produce the artifact, in
   addition to (never instead of) any advisory reviewer. An org with only advisors
   for a domain has nobody actually doing the work — don't leave that gap silently;
   name it and staff it.
   `echo "<persona body>" | PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m core.onboarding_cli author-agent <id> "<Name>" "<description>" --role-type authoring`.
   Use `--role-type advisory` only for roles that genuinely never produce the
   deliverable themselves (pure review/audit/compliance). `--role-type` defaults to
   `authoring` (Write/Edit) if omitted; `advisory` gets Read-only tools. Make each
   persona project-specific and concise. Add as many as the project genuinely needs.

5. **Finalize.** `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m core.onboarding_cli config-set project_name <name>`.
   Then report to the user: source dir(s) wired, agents enabled, new agents authored,
   and how to start (`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m core.runtime.cli_main`).

## Rules
- **Non-destructive:** never overwrite the project's existing agents or settings
  (install-agent and wire-hook already merge/skip).
- **Idempotent:** /org-init can be re-run to reconcile; don't duplicate.
- **Decisive:** infer source dirs and roster from evidence; don't interrogate the user.
