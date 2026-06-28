# Prytan Setup Guide

## Overview

This guide walks you through configuring Prytan for your project. The fastest path is the `/init` wizard inside Claude Code. This document covers the manual path and explains every decision.

---

## Step 1 — Answer the Setup Questionnaire

Run the interactive configurator:

```bash
python3 setup/configure.py
```

Or answer the questions below and fill in the templates manually.

### Questionnaire

**Project basics**

1. What is your project name? *(used in CLAUDE.md header and agent names)*
2. What is the primary programming language / stack?
3. What is the source directory? *(e.g. `src/`, `app/`, `lib/`)*
4. What is the test command? *(e.g. `pytest tests/ -x`, `npm test`)*
5. What is the line-length / style convention?

**Agent pods**

6. List your agent pods (name, domain, model, writable: yes/no).
   - Example: `backend | Flask/SQLite API | sonnet | writable`
   - Example: `security | threat modeling | opus | read-only`
7. Which agent is the "coordinator" (CEO-level, routes all work)?
8. Which agent is "chief-of-staff" (Telegram-facing, human interface)?

**Memory & knowledge graph**

9. Which directories should codegrapher scan? *(default: `src/`)*
10. Do you have documentation or books to index? *(e.g. `.claude/books/`)*

**Telegram**

11. Do you want the Telegram bot? (yes/no)
12. If yes: bot token and allowed chat ID *(stored in `.env`, gitignored)*

**Token budget**

13. Monthly token budget in USD? *(default: 50)*
14. Soft throttle threshold (% of budget)? *(default: 80)*
15. Hard halt threshold (% of budget)? *(default: 95)*
16. Per-run cap in tokens? *(default: 200000)*

**Cron schedule**

17. Daily standup time (HH:MM, 24h, your timezone)?
18. Weekly sprint planning: day and time?
19. Monthly milestone: day-of-month and time?

---

## Step 2 — Configure Agents

After running the configurator, agent files are generated under `.claude/agents/`. Each file is a markdown prompt. Edit them to add:

- Domain-specific context (architecture docs, coding conventions)
- Allowed tools list
- Read-only vs. writable designation

See `.claude/agents/AGENTS_README.md` for the full format spec.

---

## Step 3 — Initialize the Knowledge Graph

```bash
python3 codegrapher.py scan src/
# Add more directories as needed:
python3 codegrapher.py scan docs/
```

Verify it works:

```bash
python3 codegrapher.py stats
python3 codegrapher.py query "your main module name"
```

---

## Step 4 — Install Hooks

The hooks in `.claude/settings.json` activate automatically inside Claude Code. No extra step needed — just open the project in Claude Code.

To verify hooks are active:

```
Claude Code → Settings → Hooks
```

You should see `codegrapher_hook.py` (PreToolUse) and `codegrapher-memo.py` (UserPromptSubmit).

---

## Step 5 — Set Up Cron (optional)

```bash
# Review the crontab first — update [PROJECT_PATH] placeholders
cat scripts/org.crontab

# Install
crontab scripts/org.crontab

# Verify
crontab -l
```

---

## Step 6 — Start Telegram Bot (optional)

```bash
cp .env.example .env
# Edit .env with your bot token and chat ID
source .env
python3 scripts/telegram-bot.py
```

---

## Customization Tips

- **Add a new agent:** create `.claude/agents/<name>.md` following the template in `AGENTS_README.md`
- **Add a new cron meeting:** create a template in `.agent-templates/meetings/` and add a crontab line
- **Adjust token budget:** edit `.agent-config/budget.yaml`
- **Add more graph scan paths:** edit `.agent-config/daily-steps.yaml`
