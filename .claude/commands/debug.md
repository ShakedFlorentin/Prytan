---
name: debug
description: Structured debug session — reproduce, isolate, diagnose, fix
argument-hint: "<description of the bug or error>"
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Write
  - Edit
---

# /debug

**Bug:** `$ARGUMENTS`

## Protocol

**Step 1 — Reproduce**
Describe the exact steps to trigger the bug. If there's an error message, paste it in full.
Run `python3 codegrapher.py query "<error keyword or symptom>"` to find relevant code fast.

**Step 2 — Isolate**
Narrow to the smallest code path that shows the problem. Read only the files the graph returns.
State your hypothesis: "I think the bug is in X because Y."

**Step 3 — Diagnose**
Prove or disprove the hypothesis by reading the code. Add a targeted test or log if needed.
State the root cause: one sentence, specific.

**Step 4 — Fix**
Apply the minimal change that fixes the root cause without side effects.
If the fix is risky or touches more than 2 files: write it as a proposal, don't auto-apply.

**Step 5 — Verify**
Run the relevant tests. Confirm the reproduction steps no longer trigger the bug.
Write a one-liner to `.agent-logs/<your-name>/journal.md`: what the bug was and how it was fixed.
