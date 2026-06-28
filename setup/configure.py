#!/usr/bin/env python3
"""
Prytan setup configurator — terminal fallback for install.sh.

For the full interactive experience, open Claude Code and run /init.
This script is the non-Claude path: answers go in, config files come out.

Run: python3 setup/configure.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent.resolve()

# ── Helpers ───────────────────────────────────────────────────────────────────

def ask(prompt: str, default: str = "") -> str:
    display = f"  {prompt}" + (f" [{default}]" if default else "") + ": "
    try:
        answer = input(display).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return answer if answer else default

def ask_choice(prompt: str, options: list, default: int = 1) -> int:
    print(f"\n  {prompt}")
    for i, opt in enumerate(options, 1):
        marker = " ← default" if i == default else ""
        print(f"    {i}. {opt}{marker}")
    raw = ask("Choose", str(default))
    try:
        choice = int(raw)
        return choice if 1 <= choice <= len(options) else default
    except ValueError:
        return default

def ask_bool(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = ask(f"{prompt} ({hint})")
    if not raw:
        return default
    return raw.lower() in ("y", "yes")

def section(title: str):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")

def write_file(path: Path, content: str):
    if path.exists():
        raw = ask(f"  {path.relative_to(ROOT)} exists. Overwrite? (y/N)", "n")
        if raw.lower() not in ("y", "yes"):
            print(f"  → Skipped")
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"  ✓ {path.relative_to(ROOT)}")

# ── Presets ───────────────────────────────────────────────────────────────────

SOLO_AGENTS = [
    "chief-of-staff", "coordinator", "product-manager",
    "marketing-writer", "growth-strategist", "learning-loop", "org-doctor"
]
SMALL_AGENTS = SOLO_AGENTS + [
    "backend-engineer", "frontend-engineer", "qa-engineer",
    "devops-engineer", "ux-designer", "security-advisor", "legal-advisor"
]
ALL_AGENTS = SMALL_AGENTS + ["tech-lead", "org-governor"]

BUDGET_MAP = {1: (10, 20_000_000), 2: (25, 50_000_000), 3: (50, 100_000_000)}

# ── Intro ─────────────────────────────────────────────────────────────────────

print()
print("  ╔══════════════════════════════════════════╗")
print("  ║            Prytan Setup                  ║")
print("  ║    YOUR AI COUNCIL FOR ANY BUSINESS      ║")
print("  ╚══════════════════════════════════════════╝")
print()
print("  Tip: for a friendlier experience, open Claude Code and run /init")
print("  This terminal path is the quick fallback.")

# ── Q1: Name ─────────────────────────────────────────────────────────────────

section("1 / 7 — Project name")
project_name = ask("What's your project or business called?", "MyProject")

# ── Q2: Description ───────────────────────────────────────────────────────────

section("2 / 7 — What it does")
description = ask("Describe what you do in one sentence")
if not description:
    description = f"{project_name} — AI-assisted operations"

# ── Q3: Scale / agent preset ──────────────────────────────────────────────────

section("3 / 7 — Team size")
scale_choice = ask_choice(
    "How many people are on your team?",
    ["Just me", "Small team (2–15)", "Larger org (15+)"],
    default=1
)
if scale_choice == 1:
    scale = "solo"
    active_agents = SOLO_AGENTS
elif scale_choice == 2:
    scale = "small"
    active_agents = SMALL_AGENTS
else:
    scale = "large"
    active_agents = ALL_AGENTS

print(f"\n  Activating {len(active_agents)} agents: {', '.join(active_agents)}")

# ── Q4: Telegram ──────────────────────────────────────────────────────────────

section("4 / 7 — Telegram bot")
want_telegram = ask_bool("Enable Telegram so you can chat with Iris from your phone?", True)

# ── Q5: Budget ────────────────────────────────────────────────────────────────

section("5 / 7 — Monthly AI budget")
budget_choice = ask_choice(
    "What's your monthly limit for AI spend? (agents halt automatically at 100%)",
    ["~$10/month  (light use)", "~$25/month  (regular use)", "~$50/month  (heavy use)", "Custom"],
    default=2
)
if budget_choice == 4:
    custom_usd = ask("Monthly budget in USD", "25")
    try:
        budget_usd = int(custom_usd)
    except ValueError:
        budget_usd = 25
    token_cap = budget_usd * 2_000_000
else:
    budget_usd, token_cap = BUDGET_MAP.get(budget_choice, BUDGET_MAP[2])

# ── Q6: Standup time ──────────────────────────────────────────────────────────

section("6 / 7 — Daily standup time")
standup_time = ask("What time should the daily standup run? (HH:MM, 24-hour)", "08:00")
try:
    standup_h, standup_m = standup_time.split(":")
    int(standup_h); int(standup_m)
except Exception:
    standup_h, standup_m = "8", "0"

# ── Q7: Timezone ──────────────────────────────────────────────────────────────

section("7 / 7 — Timezone")
timezone = ask("Your timezone (e.g. Asia/Jerusalem, America/New_York, UTC)", "UTC")

# ── Confirm ───────────────────────────────────────────────────────────────────

print()
print("  ─────────────────────────────────────────")
print(f"  Project:   {project_name}")
print(f"  About:     {description}")
print(f"  Scale:     {scale} ({len(active_agents)} agents)")
print(f"  Telegram:  {'yes' if want_telegram else 'no'}")
print(f"  Budget:    ${budget_usd}/month")
print(f"  Standup:   {standup_time} {timezone}")
print("  ─────────────────────────────────────────")
print()
proceed = ask_bool("Generate files?", True)
if not proceed:
    print("  Aborted.")
    sys.exit(0)

print()

# ── Write files ───────────────────────────────────────────────────────────────

# project.yaml
write_file(ROOT / ".agent-config" / "project.yaml", f"""# Prytan project configuration
# Generated by setup/configure.py on {datetime.now().strftime('%Y-%m-%d')}

project_name: {project_name}
description: "{description}"
scale: {scale}
active_agents:
{chr(10).join(f'  - {a}' for a in active_agents)}
telegram_bot: {'true' if want_telegram else 'false'}
monthly_budget_usd: {budget_usd}
standup_time: "{standup_time}"
timezone: "{timezone}"
""")

# budget.yaml
write_file(ROOT / ".agent-config" / "budget.yaml", f"""# Token budget for {project_name}
# cost_governor.py reads this before every cron run.

monthly_budget_usd: {budget_usd}
monthly_token_cap: {token_cap}

# Soft throttle at 80% — agents reduce parallelism
throttle_threshold_pct: 80

# Hard halt at 100% — all cron runs skipped
halt_threshold_pct: 100

# Per-run runaway cap (abort any single run over this)
per_run_token_cap: 4000000

spend_log: .agent-config/spend.jsonl
""")

# org.crontab
project_path = str(ROOT)
write_file(ROOT / "scripts" / "org.crontab", f"""# Prytan crontab for {project_name}
# Install: crontab scripts/org.crontab
# Note: % must be escaped as \\% inside crontab

SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
TZ={timezone}

# Daily standup — {standup_time} {timezone}
{standup_m} {standup_h} * * * cd {project_path} && python3 scripts/cost_governor.py && echo "Run daily standup for {project_name}. Read .agent-config/project.yaml for active agents. For each active agent: ask what was done yesterday, what is planned today, any blockers. Write digest to .agent-inbox/standup-$(date +\\%Y\\%m\\%d).md" | claude --print --allowedTools "Read,Write,Bash" >> .agent-logs/cron.log 2>&1

# Weekly planning — Monday {standup_time} {timezone}
{standup_m} {standup_h} * * 1 cd {project_path} && python3 scripts/cost_governor.py && echo "Run weekly planning for {project_name}. Read recent standups in .agent-inbox/. Prioritize next week. Write plan to .agent-inbox/sprint-plan-$(date +\\%Y\\%m\\%d).md" | claude --print --allowedTools "Read,Write,Bash" >> .agent-logs/cron.log 2>&1

# Monthly review — 1st of month {standup_time} {timezone}
{standup_m} {standup_h} 1 * * cd {project_path} && python3 scripts/cost_governor.py && echo "Run monthly milestone review for {project_name}. Summarize progress, flag risks, set next milestone. Write to .agent-inbox/milestone-$(date +\\%Y\\%m).md" | claude --print --allowedTools "Read,Write,Bash" >> .agent-logs/cron.log 2>&1
""")

# .env.example
write_file(ROOT / ".env.example", f"""# Prytan environment variables
# Copy to .env and fill in real values — .env is gitignored

# Telegram bot (required only if telegram_bot: true in project.yaml)
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_ALLOWED_CHAT_ID=your_chat_id_from_userinfobot

# Project root (used by some scripts)
PRYTAN_PROJECT_ROOT={project_path}
""")

# Done
print()
print("  ✓ All files written.")
print()
print("  Next steps:")
print()
print("  1. Open Claude Code:        claude")
print("  2. Activate cron schedule:  crontab scripts/org.crontab")
if want_telegram:
    print("  3. Set up Telegram:")
    print("       - Create bot via @BotFather, get token")
    print("       - Get your chat ID from @userinfobot")
    print("       - cp .env.example .env  # then fill in the values")
    print("       - python3 scripts/telegram-bot.py")
print()
print("  Your AI council is ready. Run /init inside Claude Code for a guided tour.")
print()
