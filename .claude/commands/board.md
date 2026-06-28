---
name: board
description: Trigger the leadership board circle table on a strategic topic
argument-hint: "<topic or question>"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - Agent
---

# /board

**Topic:** `$ARGUMENTS`

Runs the leadership board protocol from `.agent-templates/meetings/leadership-board.md`.

## Steps

1. **Frame** — read the latest standup digest + open `.agent-proposals/` + open decisions.
   State the topic clearly in one sentence.

2. **Assemble panel** — standing: coordinator + pod leads.
   Pull domain advisors only if the blocker is in their domain.

3. **Run @@BOARD** — spawn each panelist in order, each seeing prior rounds:
   ```
   You are <agent>. Topic: <topic>.
   Prior discussion:
   ---
   <transcript>
   ---
   State your position concretely. Max 3 paragraphs. No hedging.
   ```
   Run 2–3 rounds max.

4. **Close** — coordinator writes:
   ```
   DECISION [N]: <what was decided>
   Owner: <agent or human>
   Next action: <concrete step>
   ```
   Record in decision ledger: `python3 scripts/decision_ledger.py add --title "..." --door-type <type> ...`

5. **Report** — write a tight summary for the human (who proposed what, who objected, decision).
   Archive transcript to `.planning/boardroom-<date>-<topic-slug>.md`.
   Write handoffs for each owner to pick up their action.
