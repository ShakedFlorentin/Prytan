# Weekly Sprint Planning Template

**Meeting type:** Sprint planning
**Cadence:** Weekly (default: Monday morning)
**Duration target:** ~30 min (one cron run)

---

## Instructions for the running agent

You are the **coordinator** running this week's sprint planning session.

### Pre-reads (gather before planning)

1. Read all `.agent-inbox/standup-*.md` files from the past 7 days
2. Read `.agent-inbox/sprint-plan-*.md` — last week's plan
3. Read `.agent-handoffs/` — any open cross-pod handoffs
4. Read `.agent-config/daily-steps.yaml` — pod roster

### Sprint Planning Steps

**Step 1 — Retrospective (5 min)**

For each pod: did they deliver what they planned last week? List hits and misses.

**Step 2 — Backlog Review (10 min)**

List the top items from each pod's backlog or open handoffs. For each item:
- What is the outcome (not the task)?
- Which pod owns it?
- What is the acceptance criterion?
- What is the priority (P0 / P1 / P2)?

**Step 3 — Capacity Check (5 min)**

Note any pods with reduced capacity this week (out-of-office, dependencies blocked, etc.)

**Step 4 — Sprint Goals (10 min)**

Set 1-3 sprint goals — outcomes, not tasks. Each goal should be:
- Specific and measurable
- Achievable in one week
- Assigned to an owning pod

---

## Output

Write the sprint plan to: `.agent-inbox/sprint-plan-{YYYYMMDD}.md`

```markdown
# Sprint Plan — week of {YYYY-MM-DD}

## Retrospective
| Pod | Planned | Delivered | Miss reason |
|-----|---------|-----------|-------------|

## Sprint Goals
1. **Goal 1** — owner: {pod} — AC: {criterion}
2. **Goal 2** — owner: {pod} — AC: {criterion}

## Pod Tasks

### {pod_name}
- [ ] Task — AC — P{priority}

## Open Handoffs
- ...

## Risks & flags
- ...
```
