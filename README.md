# Prytan

> A plug-and-play multi-agent operating system for software teams, built on Claude Code.

Clone this repo into any project, run `/init`, answer 10 questions, and you have a fully wired AI team: autonomous agents that talk to each other, remember your codebase, run on a schedule, and surface decisions to you over Telegram.

---

## What you get out of the box

| Feature | What it does |
|---|---|
| **Multi-agent org** | 7 role-specific agents + a chief-of-staff who routes everything |
| **Knowledge graph** | Offline graph that indexes your code and docs — agents find what they need without burning tokens on grep |
| **Episodic memory** | Relevant past decisions auto-injected into every session |
| **Telegram bot** | Chat with your chief-of-staff from your phone |
| **Cron meetings** | Daily standups, weekly sprint planning, monthly milestones — all autonomous |
| **Token governor** | Hard monthly cap with soft throttle — no surprise bills |
| **Decision ledger** | Irreversible actions surface to you; everything else agents handle themselves |
| **GSD workflow** | `/gsd:plan-phase` → `/gsd:execute-phase` → `/gsd:verify-work` |

---

## Quickstart (5 minutes)

**Prerequisites:** [Claude Code](https://claude.ai/code) (`npm install -g @anthropic/claude-code`) and Python 3.10+.

```bash
# 1. Clone
git clone https://github.com/ShakedFlorentin/Prytan.git
cd Prytan

# 2. Open Claude Code
claude

# 3. Run the setup wizard — answers 10 questions, writes all config files
/init

# 4. Build the knowledge graph (point 'src' at your source folder)
python3 codegrapher.py scan src

# 5. Install the crontab (daily standups, weekly planning, monthly reviews)
crontab scripts/org.crontab

# 6. Optional: start the Telegram bot
python3 scripts/telegram-bot.py
```

Don't want the wizard? See [setup/SETUP.md](setup/SETUP.md) for manual setup.

---

## How it works

### The big picture

```
You (Telegram) ──→ telegram-bot.py ──→ chief-of-staff agent
                                               │
                                    routes via .agent-handoffs/
                                               │
                    ┌──────────────────────────┼──────────────────────┐
                    ↓                          ↓                      ↓
            backend-engineer          frontend-engineer          qa-engineer
                    │                          │                      │
                    └──────────────────────────┴──────────────────────┘
                                         writes to
                                      .agent-inbox/

crontab ──→ cost_governor.py ──→ PROCEED ──→ orchestrator.py ──→ pod agents
```

### Agents

Every agent is a markdown file in `.claude/agents/`. Each has a role, a trust level, and an org-citizenship contract (shared behavioral rules).

| Agent | Domain | Trust |
|---|---|---|
| `chief-of-staff` | Human interface, Telegram, routing | L3 |
| `coordinator` | Org governance, promotions, decisions | L2 |
| `backend-engineer` | API, database, auth | L1 |
| `frontend-engineer` | UI, components | L1 |
| `qa-engineer` | Tests, coverage, bug repro | L1 |
| `devops-engineer` | Docker, CI/CD, deploy | L1 |
| `product-manager` | Roadmap, specs, priorities | L1 |
| `security-advisor` | Threat model, review (read-only) | L1 |

### Decision routing

Every decision agents make is classified:

- **`two_way`** — reversible, agent decides autonomously
- **`one_way`** — irreversible (ship, spend, delete, deploy) — surfaces to you
- **`strategic_fork`** — changes direction — surfaces to you

You only see what matters.

### Token economy

Four layers of cost control:

1. **Codegrapher** — agents query the local graph instead of grepping files
2. **Episodic memo hook** — only the top-N relevant memories injected per session
3. **Scoped tools** — each agent gets only the tools it needs (`--allowedTools`)
4. **Budget governor** — monthly cap, soft throttle at 80%, hard stop at 100%

---

## Directory layout

```
Prytan/
├── README.md
├── CLAUDE.md                         ← Claude Code reads this on every session
├── codegrapher.py                    ← CLI: query / explain / path / scan
├── codegrapher_hook.py               ← PreToolUse hook: query before grep
├── codegrapher/                      ← Knowledge graph engine (local, no API)
│
├── .claude/
│   ├── settings.json                 ← Hook wiring
│   ├── hooks/
│   │   └── codegrapher-memo.py       ← Auto-recall hook (fires on every prompt)
│   ├── agents/                       ← One .md file per agent
│   │   ├── chief-of-staff.md
│   │   ├── coordinator.md
│   │   └── ...
│   ├── books/                        ← Your docs, indexed by codegrapher
│   │   └── README.md                 ← How to write a book entry
│   └── commands/
│       ├── init.md                   ← /init wizard
│       ├── board.md                  ← /board — leadership circle table
│       ├── code-review.md
│       ├── debug.md
│       ├── daily-brief.md
│       └── gsd/
│           ├── plan-phase.md         ← /gsd:plan-phase
│           ├── execute-phase.md      ← /gsd:execute-phase
│           └── verify-work.md        ← /gsd:verify-work
│
├── .agent-config/
│   ├── budget.yaml                   ← Monthly token cap + throttle thresholds
│   └── daily-steps.yaml             ← What cron runs and when
│
├── .agent-templates/
│   ├── org-citizenship.md            ← Shared behavioral contract for all agents
│   ├── door-types.md                 ← Decision classification guide
│   └── meetings/
│       ├── pod-daily.md
│       ├── weekly-sprint-planning.md
│       ├── monthly-milestone.md
│       └── leadership-board.md
│
├── scripts/
│   ├── telegram-bot.py               ← Chief-of-staff Telegram interface
│   ├── cost_governor.py              ← PROCEED / THROTTLE / HALT gate
│   ├── orchestrator.py               ← Serial daily step runner (no cron overlap)
│   ├── dispatch_day.py               ← Autonomous day-runner (post-approval)
│   ├── morning_brief.py              ← Daily digest → Telegram
│   ├── decision_ledger.py            ← Append-only decision log
│   ├── skill_compiler.py             ← Nightly reflection → skills.json
│   ├── skills_store.py               ← Versioned skill lesson store
│   ├── open_tasks.py                 ← Durable task ledger (@@TASK/@@DONE)
│   ├── goal_loop.py                  ← /goal + /loop autonomous work driver
│   ├── write_proposals.py            ← Human-gated file-scoped write grants
│   ├── bot_abilities.py              ← @@GIT / @@SHOW / @@WEB / @@REMIND
│   ├── escalation_guard.py           ← Blocks permission-escalation confabulation
│   ├── claim_guard.py                ← Flags impossible agent claims
│   ├── agent_violations.py           ← Violation log (Python layer, not agent)
│   ├── agent_doctor.py               ← Nightly agent health checker
│   ├── handoff_reconcile.py          ← Auto-close stale handoffs
│   ├── org.crontab                   ← Install: crontab scripts/org.crontab
│   └── archive-pods.sh               ← Monthly log archiver
│
└── setup/
    ├── SETUP.md                      ← Full manual setup guide
    └── configure.py                  ← /init wizard implementation
```

---

## Slash commands (Claude Code)

| Command | What it does |
|---|---|
| `/init` | Setup wizard — configure Prytan for your project |
| `/board` | Convene the leadership circle table |
| `/code-review` | Structured code review |
| `/debug` | 5-step debugging session |
| `/daily-brief` | Pull today's org digest |
| `/gsd:plan-phase` | Plan a work phase (waves + acceptance criteria) |
| `/gsd:execute-phase` | Execute a planned phase |
| `/gsd:verify-work` | Verify completed work against criteria |

## Telegram commands

| Command | What it does |
|---|---|
| `/status` | Session + budget status |
| `/standup` | Today's org standup |
| `/brief` | Morning brief |
| `/reset` | Clear the current session |
| `/goal <text>` | Set a persistent goal |
| `/loop` | Start autonomous work toward the goal |

---

## Configuring your budget

Edit `.agent-config/budget.yaml`:

```yaml
monthly_token_cap: 50000000   # 50M tokens (~$15/month at Sonnet pricing)
soft_throttle_pct: 80         # trim non-essential work at 80%
circuit_breaker_pct: 100      # hard stop at 100%
runaway_per_run_cap: 4000000  # abort any single run over 4M tokens
```

---

## Adding a book (reference doc for agents)

Drop a markdown file in `.claude/books/` with this frontmatter:

```markdown
---
title: "Authentication Design"
tags: [auth, security, jwt]
explains: [login_view, AuthService, verify_token]
---

Your doc content here...
```

Re-scan: `python3 codegrapher.py scan src`

Agents now find it with: `python3 codegrapher.py query "authentication"`

---

## Adding a new agent

1. Copy `.claude/agents/backend-engineer.md` → `.claude/agents/my-agent.md`
2. Edit the frontmatter (`name`, `domain`, `model`, `trust_level`)
3. Write the role + responsibilities
4. Add it to the routing table in `CLAUDE.md`

---

## For Claude (reading this repo)

> This section is for the AI assistant. If you're a human, feel free to skip it.

**What Prytan is:** A generic scaffolding. After `/init` runs, `CLAUDE.md` and the agent files are updated with project-specific routing and instructions. Before `/init`, treat everything as a template.

**On first use (before `/init`):**
- Read `setup/SETUP.md` and `.claude/commands/init.md`
- Ask the user the 10 setup questions
- Write the config files and update `CLAUDE.md`
- Run `python3 codegrapher.py scan src` to build the initial graph

**On every session:**
- Query the graph before reading files: `python3 codegrapher.py query "<topic>"`
- Check `.agent-inbox/` for pending handoffs or decisions
- Read `.agent-templates/org-citizenship.md` — it's your behavioral contract
- Default trust level is L1 — escalate `one_way`/`strategic_fork` decisions to the coordinator

**Key paths:**
- Agent files: `.claude/agents/*.md`
- Behavioral contract: `.agent-templates/org-citizenship.md`
- Decision types: `.agent-templates/door-types.md`
- Budget: `.agent-config/budget.yaml`
- Cron steps: `.agent-config/daily-steps.yaml`

**Graph-first rule:** Never grep or glob without first running `python3 codegrapher.py query "<topic>"`. The hook will remind you, but the reason is real — the graph finds the right file in one call; blind grep can cost 10× the tokens.

**Markers the chief-of-staff emits (bot handles, human never sees):**
- `@@RUN: <agent> :: <task>` — dispatch read-only agent
- `@@RUNW: <agent> :: <task>` — dispatch write agent (org dirs only)
- `@@TASK: <title>` / `@@DONE: <ref>` — open/close durable task
- `@@GOAL: <text>` / `@@LOOP` — set goal, start autonomous work
- `@@WPROPOSE: <agent> :: <files> :: <task>` — propose human-gated source edit
- `@@RESOLVE: <id> :: <answer>` — resolve a pending decision
- `@@DECIDE: <door_type> :: <title>` — escalate a decision
- `@@GIT: <args>` / `@@SHOW: <path>` / `@@WEB: <url>` / `@@REMIND: <time> :: <note>`

---

## License

MIT
