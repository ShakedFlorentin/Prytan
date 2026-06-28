#!/usr/bin/env python3
"""
Prytan setup configurator.

Asks directed questions and generates customized config files:
  - CLAUDE.md (project instructions)
  - .claude/agents/<name>.md for each agent pod
  - .agent-config/budget.yaml
  - .agent-config/daily-steps.yaml
  - scripts/org.crontab
  - .env.example (if Telegram enabled)

Run: python3 setup/configure.py
"""

import os
import sys
import json
import textwrap
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent.resolve()


def ask(prompt: str, default: str = "") -> str:
    if default:
        display = f"{prompt} [{default}]: "
    else:
        display = f"{prompt}: "
    try:
        answer = input(display).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return answer if answer else default


def ask_bool(prompt: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    raw = ask(f"{prompt} ({default_str})")
    if not raw:
        return default
    return raw.lower() in ("y", "yes", "1", "true")


def ask_list(prompt: str) -> list:
    print(f"{prompt} (one per line, blank line to finish):")
    items = []
    while True:
        try:
            line = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            break
        items.append(line)
    return items


def section(title: str):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def write_file(path: Path, content: str, overwrite: bool = False):
    if path.exists() and not overwrite:
        confirm = ask(f"  {path.relative_to(ROOT)} already exists. Overwrite? (y/N)", "n")
        if confirm.lower() not in ("y", "yes"):
            print(f"  Skipped {path.name}")
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"  ✓ Wrote {path.relative_to(ROOT)}")


# ──────────────────────────────────────────────
# Gather answers
# ──────────────────────────────────────────────

print()
print("╔══════════════════════════════════════════╗")
print("║       Prytan Setup Configurator          ║")
print("╚══════════════════════════════════════════╝")

section("1 / 7 — Project Basics")
project_name = ask("Project name", "MyProject")
stack = ask("Primary language / stack", "Python / Flask")
src_dir = ask("Source directory", "src/")
test_cmd = ask("Test command", "pytest tests/ -x")
line_length = ask("Line length", "100")

section("2 / 7 — Agent Pods")
print()
print("Define your agent pods. Format per line:")
print("  <name> | <domain> | <model> | <writable|read-only>")
print("  e.g.:  backend | Flask API | sonnet | writable")
print("  e.g.:  security | threat modeling | opus | read-only")
print()
raw_pods = ask_list("Pods")

pods = []
for raw in raw_pods:
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) == 4:
        pods.append({
            "name": parts[0],
            "domain": parts[1],
            "model": parts[2],
            "writable": parts[3].lower() not in ("read-only", "readonly", "ro", "false", "no"),
        })
    else:
        print(f"  Warning: could not parse pod line: {raw!r} — skipping")

if not pods:
    print("  No pods defined — using defaults (coordinator + chief-of-staff only)")

coordinator = ask("Coordinator agent name (CEO-level router)", "coordinator")
chief = ask("Chief-of-staff agent name (Telegram-facing)", "chief-of-staff")

section("3 / 7 — Knowledge Graph")
scan_dirs_raw = ask("Codegrapher scan directories (comma-separated)", src_dir)
scan_dirs = [d.strip() for d in scan_dirs_raw.split(",")]
docs_dir = ask("Documentation directory to index (leave blank to skip)", "")

section("4 / 7 — Telegram Bot")
want_telegram = ask_bool("Enable Telegram bot?", False)
tg_token = ""
tg_chat = ""
if want_telegram:
    tg_token = ask("Telegram bot token (stored in .env, gitignored)", "YOUR_BOT_TOKEN")
    tg_chat = ask("Allowed Telegram chat ID", "YOUR_CHAT_ID")

section("5 / 7 — Token Budget")
budget_usd = ask("Monthly token budget (USD)", "50")
throttle_pct = ask("Soft throttle threshold (%)", "80")
halt_pct = ask("Hard halt threshold (%)", "95")
per_run_tokens = ask("Per-run token cap", "200000")

section("6 / 7 — Cron Schedule")
daily_time = ask("Daily standup time (HH:MM, 24h)", "08:00")
weekly_day = ask("Weekly sprint-planning day (0=Sun…6=Sat)", "1")
weekly_time = ask("Weekly sprint-planning time (HH:MM)", "09:00")
monthly_day = ask("Monthly milestone day-of-month (1-28)", "1")
monthly_time = ask("Monthly milestone time (HH:MM)", "09:00")

section("7 / 7 — Review")
print()
print(f"  Project:      {project_name}")
print(f"  Stack:        {stack}")
print(f"  Source:       {src_dir}")
print(f"  Test cmd:     {test_cmd}")
print(f"  Pods:         {len(pods)} defined")
print(f"  Coordinator:  {coordinator}")
print(f"  Chief:        {chief}")
print(f"  Telegram:     {'yes' if want_telegram else 'no'}")
print(f"  Budget:       ${budget_usd}/month")
print()
proceed = ask_bool("Generate files?", True)
if not proceed:
    print("Aborted.")
    sys.exit(0)

# ──────────────────────────────────────────────
# Generate files
# ──────────────────────────────────────────────

print()
print("Generating files...")

# ── CLAUDE.md ──
routing_rows = "\n".join(
    f"| {p['domain']} | `{p['name']}` |" for p in pods
)
claude_md = f"""# {project_name} — Claude Code Configuration

## Agent Routing Cheatsheet

| Task type | Agent |
|---|---|
{routing_rows}

## Agent Pods

| Agent | Model | Domain | Access |
|---|---|---|---|
""" + "\n".join(
    f"| `{p['name']}` | {p['model']} | {p['domain']} | {'writable' if p['writable'] else 'read-only'} |"
    for p in pods
) + f"""

## Codegrapher Protocol

```bash
python3 codegrapher.py query "<topic or symbol>"
python3 codegrapher.py explain "<symbol>"
python3 codegrapher.py path "<a>" "<b>"
```

Re-run `python3 codegrapher.py scan {src_dir}` after editing code.

## Project Conventions

- Stack: {stack}
- Source: `{src_dir}`
- Test: `{test_cmd}`
- Line length: {line_length}

## GSD Execution Protocol

1. **Plan** — numbered plan with phases and acceptance criteria
2. **Execute** — work through phases, check off as you go
3. **Verify** — run `{test_cmd}`, confirm criteria met

## Phase-Closure Discipline

1. Cite the commit SHA. No SHA → claim is unverified.
2. Re-scan verdict is source of truth.
"""
write_file(ROOT / "CLAUDE.md", claude_md)

# ── budget.yaml ──
budget_yaml = f"""# Token budget configuration for {project_name}
# cost_governor.py reads this file before every cron run.

monthly_budget_usd: {budget_usd}

# Soft throttle: warn and reduce parallelism
throttle_threshold_pct: {throttle_pct}

# Hard halt: skip run entirely
halt_threshold_pct: {halt_pct}

# Per-run token ceiling (approximate, checked by governor)
per_run_token_cap: {per_run_tokens}

# Spend log location (auto-created)
spend_log: .agent-config/spend.jsonl
"""
write_file(ROOT / ".agent-config" / "budget.yaml", budget_yaml)

# ── daily-steps.yaml ──
scan_dirs_yaml = "\n".join(f"  - {d}" for d in scan_dirs)
if docs_dir:
    scan_dirs_yaml += f"\n  - {docs_dir}"

pods_yaml = "\n".join(
    f"""  - name: {p['name']}
    model: {p['model']}
    domain: {p['domain']}
    writable: {str(p['writable']).lower()}"""
    for p in pods
)

daily_steps = f"""# Prytan daily-steps configuration for {project_name}

project_name: {project_name}
coordinator: {coordinator}
chief_of_staff: {chief}

codegrapher:
  scan_dirs:
{scan_dirs_yaml}
  auto_scan_on_run: true

pods:
{pods_yaml if pods_yaml else "  []"}
"""
write_file(ROOT / ".agent-config" / "daily-steps.yaml", daily_steps)

# ── org.crontab ──
daily_h, daily_m = daily_time.split(":")
weekly_h, weekly_m = weekly_time.split(":")
monthly_h, monthly_m = monthly_time.split(":")

project_path_placeholder = "[PROJECT_PATH]"
crontab = f"""# Prytan crontab for {project_name}
# Replace {project_path_placeholder} with absolute path to project root.
# Install: crontab scripts/org.crontab
# Note: % must be escaped as \% inside crontab

SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin

# Daily pod standup — {daily_time}
{daily_m} {daily_h} * * * cd {project_path_placeholder} && python3 scripts/cost_governor.py && echo "Run daily standup for {project_name}. Read .agent-config/daily-steps.yaml for pod list. For each pod: ask what was done yesterday, what is planned today, any blockers. Write digest to .agent-inbox/standup-$(date +\%Y\%m\%d).md" | claude --print --allowedTools "Read,Write,Bash" >> .agent-logs/cron.log 2>&1

# Weekly sprint planning — {["Sun","Mon","Tue","Wed","Thu","Fri","Sat"][int(weekly_day)]} {weekly_time}
{weekly_m} {weekly_h} * * {weekly_day} cd {project_path_placeholder} && python3 scripts/cost_governor.py && echo "Run weekly sprint planning for {project_name}. Read .agent-inbox/ for recent digests. Prioritize next week\'s work. Write plan to .agent-inbox/sprint-plan-$(date +\%Y\%m\%d).md" | claude --print --allowedTools "Read,Write,Bash" >> .agent-logs/cron.log 2>&1

# Monthly milestone review — day {monthly_day} at {monthly_time}
{monthly_m} {monthly_h} {monthly_day} * * cd {project_path_placeholder} && python3 scripts/cost_governor.py && echo "Run monthly milestone review for {project_name}. Summarize progress, flag risks, set next milestone. Write to .agent-inbox/milestone-$(date +\%Y\%m).md" | claude --print --allowedTools "Read,Write,Bash" >> .agent-logs/cron.log 2>&1
"""
write_file(ROOT / "scripts" / "org.crontab", crontab)

# ── Agent files ──
for pod in pods:
    access_note = "You are a **writable** agent. Follow GSD: plan → execute → verify." if pod["writable"] else "You are a **read-only** advisor. You MUST NOT modify source files. Write findings to `.agent-inbox/` only."
    agent_md = f"""---
name: {pod["name"]}
model: {pod["model"]}
---

# {pod["name"].title()} Agent

**Domain:** {pod["domain"]}
**Model:** {pod["model"]}

{access_note}

## Responsibilities

*(Fill in: what this agent owns, what decisions it makes, what it does NOT touch)*

## Allowed Tools

*(Customize per your project needs)*

- Read, Glob, Grep
{"- Write, Edit, Bash" if pod["writable"] else "# Write/Edit/Bash are NOT allowed for this read-only agent"}

## Context

- Project: {project_name}
- Stack: {stack}
- Source: `{src_dir}`

## Codegrapher Protocol

Always query the knowledge graph before searching files:

```bash
python3 codegrapher.py query "<topic>"
```

## Output

After completing work, write a digest to `.agent-inbox/<name>-<YYYYMMDD>.md`.
"""
    write_file(ROOT / ".claude" / "agents" / f"{pod['name']}.md", agent_md)

# ── .env.example ──
if want_telegram:
    env_example = f"""# Prytan environment variables for {project_name}
# Copy to .env and fill in real values. .env is gitignored.

TELEGRAM_BOT_TOKEN={tg_token}
TELEGRAM_ALLOWED_CHAT_ID={tg_chat}
PRYTAN_CHIEF_AGENT={chief}
PRYTAN_PROJECT_ROOT={ROOT}
"""
    write_file(ROOT / ".env.example", env_example)

print()
print("Done! Next steps:")
print(f"  1. python3 codegrapher.py scan {src_dir}")
print(f"  2. Review generated agent files in .claude/agents/")
print(f"  3. crontab scripts/org.crontab")
if want_telegram:
    print(f"  4. cp .env.example .env && python3 scripts/telegram-bot.py")
