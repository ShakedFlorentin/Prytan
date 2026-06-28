---
name: gsd:verify-work
description: Verify completed phase work — test acceptance criteria, diagnose gaps, plan fixes
argument-hint: "<phase-name-or-number>"
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Write
  - Agent
---

# /gsd:verify-work

**Purpose:** Confirm that what was built actually satisfies the acceptance criteria. Surface gaps and plan fixes.

## Steps

1. **Load the plan** — read `.planning/phases/<phase>/PLAN.md`. Extract acceptance criteria.

2. **Test each criterion** — for each `- [ ]` criterion:
   - Run relevant tests if they exist (`python3 -m pytest tests/ -x -q` or equivalent).
   - Read the relevant code to check the criterion is actually implemented.
   - Mark: ✅ PASS, ❌ FAIL, or ⚠️ PARTIAL.

3. **Write UAT report** at `.planning/phases/<phase>/UAT.md`:
   ```markdown
   # UAT — Phase <N> — <date>

   ## Results
   | Criterion | Status | Notes |
   |---|---|---|
   | Criterion 1 | ✅ PASS | |
   | Criterion 2 | ❌ FAIL | Missing: <what> |

   ## Gaps found
   - GAP-01: <description> — severity: high|medium|low

   ## Fix plan
   - [ ] FIX-01: <what to fix> — owner: <agent>
   ```

4. **If gaps found** — spawn the relevant domain agent(s) to fix each gap. Then re-verify.

5. **Phase closure** — when all criteria PASS: update `.planning/ROADMAP.md` to mark the phase complete. Write a one-line entry in each involved agent's `journal.md`.
