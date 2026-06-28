# Org Citizenship — Shared Behavioral Contract

Every agent in this org follows this contract. No exceptions.

---

## Your Desk

Your personal workspace is `.agent-logs/<your-name>/`. It contains:

- `journal.md` — running log of significant events, one entry per task (append-only)
- `YYYY-MM-DD-<task-slug>.md` — per-task run logs
- `conversations/` — archived conversation transcripts (optional)

Do not write to another agent's desk.

---

## Recall Cheaply: Query Before Reading

Before opening any file, query the knowledge graph:

```bash
python3 codegrapher.py query "<topic or symbol>"
python3 codegrapher.py explain "<symbol or page title>"
python3 codegrapher.py path "<a>" "<b>"
```

The graph returns the files you actually need. Read only those. Never read a whole
directory when a graph query would give you the right file in one step.

---

## The Four Things Agents Do

1. **File a handoff** — delegate or hand off work to another agent via
   `.agent-handoffs/<date>-<from>-<to>-<slug>.md`. Use `.agent-templates/handoff.md`.

2. **Propose an initiative** — file an unsolicited improvement idea to
   `.agent-proposals/<date>-<agent>-<slug>.md`. Use `.agent-templates/proposal.md`.
   Proposals are reviewed by the coordinator; never self-authorize them.

3. **Pick up a handoff** — check `.agent-handoffs/` for items addressed to you.
   Acknowledge by writing a brief note and starting the work.

4. **Log every run** — after every task, append one line to `journal.md` and write
   a run log using `.agent-templates/run-log.md`.

---

## Trust Levels

| Level | Name | What the agent can do |
|---|---|---|
| L0 | Propose-only | File proposals and handoffs. Cannot execute tasks autonomously. |
| L1 | Domain-autonomous | Execute tasks within their domain. Default for all working agents. |
| L2 | Executive | Execute across domains. Can modify cross-pod plans. |
| L3 | Chief-of-staff | Coordinate all pods. Interface with the human. Route everything. |

Trust level is set in each agent's frontmatter (`trust_level:`). The coordinator is
the only agent authorized to change trust levels.

---

## The One Rule That Matters

**Read-only advisors never write code.**

Agents with `read_only: true` in their frontmatter output reports only.
They do not create, edit, or delete source files. If you are a read-only advisor
and a task asks you to write code, redirect it to the appropriate writable agent
via a handoff.

---

## Escalation Ladder

When you are stuck or a decision is above your authority:

1. **Domain lead** — if your pod has a senior or lead, hand off to them first.
2. **Coordinator** — cross-pod conflicts, resource allocation, scope changes.
3. **Chief-of-staff** — anything needing human visibility or a one-way decision.
4. **Human** — one_way or strategic_fork decisions (see `.agent-templates/door-types.md`).

Do not skip levels. Do not escalate two-way decisions — own them.

---

## Door Types

Every decision you make or record has a door type. See `.agent-templates/door-types.md`
for the full spec. Short version:

- **two_way** — reversible, internal. You decide and record it.
- **one_way** — irreversible or outward-facing. Escalate to human before acting.
- **strategic_fork** — changes direction or roadmap. Human decides.

---

## After Every Task

1. Append one line to `.agent-logs/<your-name>/journal.md`:
   ```
   YYYY-MM-DD | <task-slug> | <quality: clean|partial|regression|blocked> | <one sentence>
   ```

2. Write a run log to `.agent-logs/<your-name>/YYYY-MM-DD-<task-slug>.md`
   using the template at `.agent-templates/run-log.md`.

No exceptions — even for trivial tasks. The journal is how the coordinator tracks
your work and how promotions are assessed.
