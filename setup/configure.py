#!/usr/bin/env python3
"""
Prytan terminal setup — 3 questions, then done.

Prefer /init inside Claude Code for a friendlier experience.
This script exists for headless / CI environments.

Run: python3 setup/configure.py
"""

import sys
from pathlib import Path
from datetime import datetime

try:
    import subprocess
    _tz = subprocess.check_output(
        ["python3", "-c", "import datetime; print(datetime.datetime.now().astimezone().tzname())"],
        stderr=subprocess.DEVNULL, text=True
    ).strip()
    DETECTED_TZ = _tz if _tz else "UTC"
except Exception:
    DETECTED_TZ = "UTC"

ROOT = Path(__file__).parent.parent.resolve()

SOLO_AGENTS   = ["chief-of-staff","coordinator","product-manager","marketing-writer","growth-strategist","learning-loop","org-doctor"]
SMALL_AGENTS  = SOLO_AGENTS + ["backend-engineer","frontend-engineer","qa-engineer","devops-engineer","ux-designer","security-advisor","legal-advisor"]
ALL_AGENTS    = SMALL_AGENTS + ["tech-lead","org-governor"]

def ask(prompt, default=""):
    d = f" [{default}]" if default else ""
    try:
        v = input(f"  {prompt}{d}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print(); sys.exit(0)
    return v if v else default

def ask_choice(prompt, options, default=1):
    print(f"\n  {prompt}")
    for i, o in enumerate(options, 1):
        print(f"    {i}. {o}" + (" ← default" if i == default else ""))
    raw = ask("Choose", str(default))
    try:
        c = int(raw)
        return c if 1 <= c <= len(options) else default
    except ValueError:
        return default

def write(path, content):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"  ✓  {path.relative_to(ROOT)}")

# ─────────────────────────────────────────────────────────────────────────────

print()
print("  ╔══════════════════════════════════════════╗")
print("  ║         Prytan — Quick Setup             ║")
print("  ╚══════════════════════════════════════════╝")
print()
print("  Tip: run /init inside Claude Code for a friendlier setup.")
print()

# Q1
name = ask("What's your project or business called?", "MyProject")

# Q2
desc = ask("Describe it in one sentence")
if not desc:
    desc = f"{name} — AI-assisted operations"

# Q3
scale_choice = ask_choice(
    "How many people on your team?",
    ["Just me", "Small team (2–15)", "Larger org (15+)"]
)
scale, agents = {1: ("solo", SOLO_AGENTS), 2: ("small", SMALL_AGENTS), 3: ("large", ALL_AGENTS)}[scale_choice]

# Summary
print()
print(f"  Project:  {name} — {desc}")
print(f"  Agents:   {len(agents)} active")
print(f"  Budget:   $25/month  |  Standup: 08:00 {DETECTED_TZ}  |  Telegram: off")
print()
go = ask("Write config files? (Y/n)", "y")
if go.lower() not in ("y", "yes", ""):
    print("  Aborted."); sys.exit(0)
print()

# ── Write files ───────────────────────────────────────────────────────────────

write(".agent-config/project.yaml", f"""\
# Prytan project config — generated {datetime.now().strftime('%Y-%m-%d')}
project_name: {name}
description: "{desc}"
scale: {scale}
active_agents:
{chr(10).join(f'  - {a}' for a in agents)}
telegram_bot: false
monthly_budget_usd: 25
standup_time: "08:00"
timezone: "{DETECTED_TZ}"
""")

write(".agent-config/budget.yaml", f"""\
monthly_budget_usd: 25
monthly_token_cap: 50000000
throttle_threshold_pct: 80
halt_threshold_pct: 100
per_run_token_cap: 4000000
spend_log: .agent-config/spend.jsonl
""")

write("scripts/org.crontab", f"""\
# Prytan crontab — install: crontab scripts/org.crontab
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
TZ={DETECTED_TZ}

# Daily standup — 08:00
0 8 * * * cd {ROOT} && python3 scripts/cost_governor.py && echo "Daily standup for {name}" | claude --print --allowedTools "Read,Write,Bash" >> .agent-logs/cron.log 2>&1

# Weekly planning — Monday 08:00
0 8 * * 1 cd {ROOT} && python3 scripts/cost_governor.py && echo "Weekly planning for {name}" | claude --print --allowedTools "Read,Write,Bash" >> .agent-logs/cron.log 2>&1

# Monthly review — 1st of month
0 8 1 * * cd {ROOT} && python3 scripts/cost_governor.py && echo "Monthly review for {name}" | claude --print --allowedTools "Read,Write,Bash" >> .agent-logs/cron.log 2>&1
""")

write(".env.example", """\
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_ALLOWED_CHAT_ID=your_chat_id_here
""")

print()
print("  Done! Next steps:")
print()
print(f"  1. Open Claude Code:   cd {ROOT} && claude")
print(f"  2. Activate cron:      crontab scripts/org.crontab")
print()
