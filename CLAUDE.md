# [PROJECT_NAME] — Claude Code Configuration

> **First time?** Run `/init` to set up this file for your project. It takes ~5 minutes.

---

## Quick orientation

Prytan gives your project a multi-agent org that runs autonomously on a schedule.
Agents communicate via `.agent-handoffs/`, store daily work in `.agent-inbox/`,
and query the codebase through a local knowledge graph (no API, no tokens spent on grep).

**The three things you control:**
1. Which agents exist and what they own (`.claude/agents/`)
2. What cron meetings run and when (`scripts/org.crontab`)
3. How much budget agents can spend (`.agent-config/budget.yaml`)

---

## Agent Routing

| Task | Agent | Persona |
|---|---|---|
| Backend / API / DB | `backend-engineer` | **Leon** |
| Frontend / UI | `frontend-engineer` | **Clio** |
| Product direction / roadmap | `product-manager` | **Thea** |
| Tests / coverage / bug repro | `qa-engineer` | **Argus** |
| Docker / CI / deploy | `devops-engineer` | **Atlas** |
| Security review (read-only) | `security-advisor` | **Themis** |
| Marketing / copy / content / SEO | `marketing-writer` | **Lyra** |
| Cross-pod decisions / strategy | Leadership Board via chief-of-staff | **Nestor** chairs |
| Quick chat / routing / Telegram | `chief-of-staff` | **Iris** |

*After `/init`, this table is filled in with your actual agent names.*

**Key rules:**
- `security-advisor` is read-only — it NEVER edits code.
- All agents write handoffs to `.agent-handoffs/` after completing work.
- Irreversible decisions (spend money, delete data, external changes) get routed to you.

---

## Codegrapher — Query Before You Read

A local knowledge graph (`codegrapher_out/graph.json`) indexes your code and docs.
Agents query it instead of grepping files — this saves thousands of tokens per task.

**Protocol: query the graph, then read ONE file. Never read a whole directory.**

```bash
python3 codegrapher.py query "<topic or symbol>"     # → ranked nodes + file paths
python3 codegrapher.py explain "<symbol or page>"    # → edges (explains/contains)
python3 codegrapher.py path "<node-a>" "<node-b>"   # → shortest path

# Re-scan after editing code or books:
python3 codegrapher.py scan src
```

This is enforced automatically — `codegrapher_hook.py` fires before every Read/Grep/Glob
and reminds agents to query the graph first.

---

## Books — Reference Docs in the Graph

Put any markdown documentation in `.claude/books/` with YAML frontmatter and
codegrapher indexes it alongside the code. Agents can then find design docs, ADRs,
API references, and runbooks with the same `query` command.

See `.claude/books/README.md` for the frontmatter format.

```bash
python3 codegrapher.py query "authentication design"
# → returns page:auth-design with file path — read ONLY that page
```

---

## Episodic Memory

`.claude/hooks/codegrapher-memo.py` auto-injects relevant memories into every session:
- **On each prompt** — top-5 most relevant past notes/decisions from `.agent-logs/`
- **After compaction** — re-injects top-7 so context survives a session compaction

Wired in `.claude/settings.json` — runs automatically, no setup needed.

---

## Scheduled Meetings (Crons)

```bash
crontab scripts/org.crontab   # install once
crontab -l                     # verify
```

| Meeting | Cadence | Runs |
|---|---|---|
| Pod standup | Weekdays 08:00 | All pods in sequence |
| Weekly sprint | Mondays 09:00 | Coordinator + pod leads |
| Monthly milestone | 1st of month 07:13 | Coordinator + all leads |
| Archive old digests | 1st of month 04:17 | Shell script, no LLM |

Leadership Board is **NOT a cron** — trigger it via your chief-of-staff.

Pattern every cron uses:
```bash
echo "prompt" | claude --print --allowedTools "Read,Write,Edit,Bash,Glob,Grep,Task"
```
(`Task` lets facilitators spawn pod agents. `%` escaped as `\%` in crontab.)

---

## Token Budget

`.agent-config/budget.yaml` sets the monthly ceiling. `scripts/cost_governor.py` reads
it before every cron run — returns PROCEED / THROTTLE / HALT and logs to
`.agent-inbox/usage-ledger.tsv`.

```yaml
monthly_token_cap: 50000000   # 50M tokens
soft_throttle_pct: 80         # start trimming at 80%
circuit_breaker_pct: 100      # hard stop at 100%
runaway_per_run_cap: 4000000  # single run > 4M tokens = abort
```

---

## Telegram Bot

Chat with your chief-of-staff from your phone:

```bash
python3 scripts/telegram-bot.py   # run in background
```

Setup: see `setup/SETUP.md §Telegram`. Read-only by default; set `WRITE_MODE=1` in
`~/.prytan.env` to allow the agent to write files from chat.

---

## Conventions

- Python 3.10+, `datetime.now(timezone.utc)` — never `datetime.utcnow()`
- All agents write digests to `.agent-inbox/` after completing work
- Handoff files: `.agent-handoffs/YYYY-MM-DD-<from>-<to>-<topic>.md`
- Planning files: `.planning/` — roadmap, sprint tasks, boardroom transcripts

---

## Phase-Closure Discipline

When marking a task complete:
1. Cite the commit SHA — no SHA = claim is unverified.
2. Re-scan the relevant domain before closing — the agent's verdict is the source of truth.

## Scan Hygiene

Before flagging something as "still open": run `git log --since=<date>` to check if it
was already fixed. Don't re-open closed issues.
