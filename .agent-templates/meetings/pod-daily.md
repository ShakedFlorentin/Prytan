# Pod Daily Standup Template

**Meeting type:** Daily standup
**Cadence:** Every weekday
**Duration target:** ~15 min (one cron run per pod)

---

## Instructions for the running agent

You are facilitating the daily standup for **{pod_name}** pod.

Read the following to build context:
1. `.agent-inbox/` — yesterday's digests and any open handoffs
2. `.agent-handoffs/` — pending handoff files addressed to this pod
3. `.agent-config/daily-steps.yaml` — pod responsibilities

Then answer these three questions on behalf of the pod:

### 1. What was completed yesterday?

*(List concrete deliverables: PRs merged, features shipped, bugs fixed, decisions made. Use bullet points. No vague statements.)*

### 2. What is planned for today?

*(List specific tasks with acceptance criteria. Each item should be verifiable — "add endpoint X", not "work on backend".)*

### 3. Any blockers?

*(List any blocker with: what it blocks, who can unblock it, and the urgency. If none: write "None.")*

---

## Output format

Write your digest to: `.agent-inbox/{pod_name}-standup-{YYYYMMDD}.md`

Use this structure:

```markdown
# {pod_name} standup — {YYYY-MM-DD}

## Done yesterday
- ...

## Planned today
- ...

## Blockers
- ...

## Handoffs out
- (list any handoffs this pod is sending to other pods)
```

If you have handoffs for another pod, write them to:
`.agent-handoffs/{pod_name}-to-{target}-{YYYYMMDD}.md`
