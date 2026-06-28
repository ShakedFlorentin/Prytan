# Monthly Milestone Review Template

**Meeting type:** Monthly milestone
**Cadence:** 1st of each month
**Duration target:** ~45 min (one cron run)

---

## Instructions for the running agent

You are the **coordinator** running the monthly milestone review.

### Pre-reads

1. Read all `.agent-inbox/sprint-plan-*.md` from the past 30 days
2. Read all `.agent-inbox/milestone-*.md` from prior months
3. Read `.agent-inbox/standup-*.md` for the past 30 days
4. Read `.agent-config/daily-steps.yaml` — pod roster and goals

---

## Review Structure

### 1. Milestone Scorecard

For each milestone set last month:
- Did we achieve it? (Yes / Partial / No)
- What evidence proves or disproves it?
- What was the root cause of any miss?

### 2. Metric Trends

For each pod, summarize trends over the past 30 days:
- Velocity (tasks completed vs. planned)
- Blockers frequency
- Cross-pod handoff latency (days from sent to resolved)

### 3. Key Decisions

List any significant architectural, product, or process decisions made this month.
Each decision needs: what was decided, who decided it, what alternatives were rejected.

### 4. Risk Register

List any open risks heading into next month:
- Risk description
- Likelihood (H/M/L)
- Impact (H/M/L)
- Mitigation plan

### 5. Next Month's Milestones

Set 2-4 milestones for next month. Each milestone:
- Outcome (not activity)
- Owner pod
- Measurable acceptance criterion
- Due date within the month

---

## Output

Write the review to: `.agent-inbox/milestone-{YYYYMM}.md`

```markdown
# Monthly Milestone Review — {YYYY-MM}

## Scorecard
| Milestone | Status | Evidence |
|-----------|--------|----------|

## Trends
...

## Key Decisions
...

## Risk Register
| Risk | L | I | Mitigation |
|------|---|---|-----------|

## Next Month Milestones
1. **Milestone** — owner: {pod} — AC: {criterion} — due: {date}
```
