---
name: daily-brief
description: Summarize what happened since the last standup and what's next
argument-hint: "[date, default: today]"
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
---

# /daily-brief

Pull the latest agent activity and give a tight summary.

## What to read (in order, cheapest first)

1. **Latest standup digest** — `.agent-inbox/standup-<latest>.md`
2. **Recent handoffs** — `.agent-handoffs/` files from the last 24h
3. **Open decisions** — `python3 scripts/decision_ledger.py list --status awaiting_human`
4. **Sprint tasks** — `.planning/sprint-tasks.md` (what's in progress vs done vs blocked)
5. **Recent run logs** — `.agent-logs/*/$(date +%Y-%m-%d)-*.md` for any logs from today

## Output format

```
## Daily Brief — <date>

### What got done
- <agent>: <what they completed>

### What's in flight
- <agent>: <what they're working on> — ETA: <if known>

### Blockers
- <blocker> — assigned to: <who's handling it>

### Decisions waiting for you
- D-<id>: <title> — door_type: one_way|strategic_fork
  Recommendation: <what the agent suggests>

### What's next
- <top 2-3 items from sprint-tasks.md that aren't started yet>
```

Keep it under 30 lines. No preamble.
