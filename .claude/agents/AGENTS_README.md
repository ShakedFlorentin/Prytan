# Creating Agents in Prytan

This guide explains the agent file format and best practices for building
a productive multi-agent team inside Claude Code.

---

## File format

Each agent is a markdown file at `.claude/agents/<name>.md`.

The filename becomes the agent's `--agent` flag value and the routing key
used in handoffs. Use lowercase, hyphen-separated names (e.g. `backend`,
`chief-of-staff`, `security-advisor`).

### Required sections

```markdown
---
name: <agent-name>
model: sonnet | opus | haiku
---

# <Agent Name>

**Domain:** <one-line description of what this agent owns>
**Model:** <sonnet | opus | haiku>

<writable designation — see below>

## Responsibilities
...

## Allowed Tools
...
```

### Frontmatter fields

| Field | Required | Values |
|-------|----------|--------|
| `name` | Yes | lowercase, hyphens only |
| `model` | Yes | `sonnet`, `opus`, `haiku` |

---

## Writable vs. read-only

**Writable agent** — can modify source files, create files, run tests:

```markdown
You are a **writable** agent. Follow the GSD Execution Protocol:
1. Plan — write a numbered plan with phases and acceptance criteria
2. Execute — work through each phase, check off as you go
3. Verify — run tests, confirm criteria met
```

**Read-only advisor** — analyzes and reports, never modifies:

```markdown
You are a **read-only advisor**. You MUST NOT modify source files,
create production files, or run destructive commands.
Write all findings to `.agent-inbox/<name>-<YYYYMMDD>.md`.
```

---

## Allowed tools

Scope tools tightly — it reduces token waste and accidental writes.

**Writable agent:**
```markdown
## Allowed Tools
- Read, Glob, Grep
- Write, Edit
- Bash (for: git, tests, build commands only)
```

**Read-only advisor:**
```markdown
## Allowed Tools
- Read, Glob, Grep
# Write/Edit/Bash are NOT allowed for this read-only agent
```

---

## Codegrapher protocol

Include this block in every agent so they use the knowledge graph:

```markdown
## Codegrapher Protocol

Always query the knowledge graph before searching files:

```bash
python3 codegrapher.py query "<topic>"
python3 codegrapher.py explain "<symbol>"
```

Only fall back to Grep/Glob if the graph returns no relevant results.
```

---

## Handoff protocol

Include this so agents route work correctly:

```markdown
## Handoffs

To delegate work to another agent:
1. Copy `.agent-templates/handoff.md`
2. Fill in: From, To, Context, Request, Acceptance Criteria
3. Write to `.agent-handoffs/<your-name>-to-<target>-<YYYYMMDD>.md`
4. Write a note in your digest so the coordinator knows
```

---

## Digest protocol

Every agent should end work by writing a digest:

```markdown
## Output

After completing work, write a digest to:
  `.agent-inbox/<name>-<YYYYMMDD>.md`

Digest format:
  # <name> digest — <YYYY-MM-DD>
  ## Done
  ## Planned next
  ## Handoffs out
  ## Open questions
```

---

## Model selection guide

| Model | Use when |
|-------|----------|
| `haiku` | High-frequency, low-complexity tasks (summarize, format, route) |
| `sonnet` | Most engineering tasks (write, debug, review, test) |
| `opus` | Complex reasoning, security review, hardware semantics, rare decisions |

Default to `sonnet`. Upgrade to `opus` only for agents where quality
of judgment matters more than cost.

---

## Example: minimal writable agent

```markdown
---
name: backend
model: sonnet
---

# Backend Agent

**Domain:** REST API, database, authentication
**Model:** sonnet

You are a **writable** agent. Follow GSD: plan → execute → verify.

## Responsibilities
- Implement and maintain API endpoints
- Database schema migrations
- Authentication and authorization logic
- NOT responsible for: frontend, DevOps, security audit

## Allowed Tools
- Read, Glob, Grep, Write, Edit, Bash

## Codegrapher Protocol

```bash
python3 codegrapher.py query "<topic>"
```

## Output

Write digest to `.agent-inbox/backend-<YYYYMMDD>.md`
```

---

## Example: read-only advisor

```markdown
---
name: security-advisor
model: opus
---

# Security Advisor

**Domain:** Threat modeling, IDOR, authentication vulnerabilities
**Model:** opus

You are a **read-only advisor**. Do NOT modify source files.

## Responsibilities
- Review authentication flows for vulnerabilities
- Check for IDOR and privilege escalation paths
- Review input validation
- NOT responsible for: fixing bugs (hand off to writable agent)

## Allowed Tools
- Read, Glob, Grep

## Output

Write findings to `.agent-inbox/security-advisor-<YYYYMMDD>.md`
Use severity: CRITICAL / HIGH / MEDIUM / LOW / INFO
```
