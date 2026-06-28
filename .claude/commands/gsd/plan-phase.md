---
name: gsd:plan-phase
description: Plan a work phase — research the codebase, write a PLAN.md with tasks, waves, and acceptance criteria
argument-hint: "<phase-name-or-number> [--skip-research]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
---

# /gsd:plan-phase

**Purpose:** Turn a goal into an executable phase plan (PLAN.md).

## Steps

1. **Identify the phase** — from `$ARGUMENTS` or ask the user.

2. **Research** (unless `--skip-research`) — query codegrapher:
   ```bash
   python3 codegrapher.py query "<phase topic>"
   ```
   Read only the files the graph returns. Check `.planning/ROADMAP.md` for adjacent phases.

3. **Draft PLAN.md** at `.planning/phases/<phase>/PLAN.md`:
   ```markdown
   # Phase <N>: <Title>

   ## Goal
   One sentence.

   ## Acceptance criteria
   - [ ] Criterion 1
   - [ ] Criterion 2

   ## Tasks (Wave 1 — parallel)
   - [ ] TASK-01: <description> — owner: <agent>
   - [ ] TASK-02: <description> — owner: <agent>

   ## Tasks (Wave 2 — after Wave 1)
   - [ ] TASK-03: <description> — owner: <agent>

   ## Out of scope
   - List what this phase deliberately does NOT do.
   ```

4. **Verify the plan** — check: are all tasks owned? Do acceptance criteria map to tasks? Any cross-domain tasks missing a handoff step?

5. **Present** the plan to the user. Ask: "Ready to execute, or any changes?"

## Wave rules
- Tasks in the same wave can run in parallel (no dependencies between them).
- Wave N+1 starts only after Wave N is complete.
- Keep waves ≤ 5 tasks each for manageable context.
