---
name: gsd:execute-phase
description: Execute a planned phase — spawn agents per wave, collect results
argument-hint: "<phase-name-or-number> [--wave N] [--interactive]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Agent
---

# /gsd:execute-phase

**Purpose:** Execute tasks in a PLAN.md phase using wave-based parallel execution.

## Steps

1. **Load the plan** — read `.planning/phases/<phase>/PLAN.md`. If missing, run `/gsd:plan-phase` first.

2. **Check budget** — run `python3 scripts/cost_governor.py`. If HALT: stop and tell the user.

3. **Identify the wave** — from `--wave N` flag, or start from Wave 1 (the first wave with incomplete tasks).

4. **Spawn agents** for each task in the wave (in parallel via Agent tool). Each agent gets:
   - The task description and acceptance criteria
   - The relevant codegrapher context
   - The org-citizenship rules (reference `.agent-templates/org-citizenship.md`)

5. **Collect results** — wait for all agents in the wave to complete. Mark tasks `[x]` in PLAN.md.

6. **Advance** — if all tasks in the wave are done, move to Wave N+1 automatically (unless `--interactive`, which asks the user before advancing).

7. **Phase complete** when all waves are done. Write a summary to `.agent-handoffs/<date>-phase-<N>-complete.md`.

## Interactive mode (`--interactive`)
Execute tasks sequentially inline (no sub-agents). Pause between tasks for user feedback. Lower token cost, good for small phases or debugging.

## Flag: `--wave N`
Execute only Wave N. Use for pacing, quota management, or staged rollout.
