#!/usr/bin/env python3
"""
dispatch_day.py — Autonomous day-runner for the HITL workflow.

Triggered (detached) by the Telegram bot when the chief-of-staff emits
[ACTION: DISPATCH_DAY] AFTER the human approves the proposed agenda. This script:
  1. Reads the APPROVED agenda (.agent-inbox/proposed_agenda.md).
  2. Runs one headless `claude` orchestrator with the Task tool + full debug perms
     (Bash/Edit/Read/Write/Glob/Grep) so it can spawn the right sub-agents, each
     entering its OWN ReAct loop — debugging, editing, re-running tests, self-healing
     — WITHOUT pinging for minor errors.
  3. Enforces a HARD time limit so an autonomous run can never go unbounded.
  4. Pushes a completion digest back to Telegram (runs detached from the bot).

Stdlib only. Launched via: python3 scripts/dispatch_day.py
HITL safety: the human gate is the AGENDA APPROVAL. After that, execution is
autonomous by design. Permissions are SCOPED via --allowedTools.
"""
import json
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
ENV = Path.home() / ".prytan.env"
AGENDA = PROJ / ".agent-inbox" / "proposed_agenda.md"

HARD_LIMIT_SEC = 3600  # 60 minutes — autonomous run ceiling
RUN_TOOLS = "Task,Bash,Edit,Read,Write,Glob,Grep"


def _claude() -> str:
    return shutil.which("claude") or "claude"


def _py() -> str:
    return shutil.which("python3") or shutil.which("python") or "python3"


def load_env() -> dict:
    d = {}
    if ENV.exists():
        for ln in ENV.read_text().splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, _, v = ln.partition("=")
                d[k.strip()] = v.strip()
    return d


def _project_name() -> str:
    if ENV.exists():
        for ln in ENV.read_text().splitlines():
            if ln.startswith("PROJECT_NAME="):
                return ln.split("=", 1)[1].strip()
    return PROJ.name


def tg_send(token: str, chat: str, text: str) -> None:
    if not token or not chat:
        return
    for i in range(0, len(text) or 1, 3900):
        chunk = text[i:i + 3900] or "(empty)"
        data = urllib.parse.urlencode({"chat_id": chat, "text": chunk}).encode()
        try:
            urllib.request.urlopen(
                urllib.request.Request(
                    f"https://api.telegram.org/bot{token}/sendMessage", data=data),
                timeout=30)
        except Exception as e:
            print(f"[tg] send error: {e}", file=sys.stderr)


def main() -> int:
    env = load_env()
    token, chat = env.get("TELEGRAM_BOT_TOKEN", ""), env.get("ALLOWED_CHAT_ID", "")
    today = datetime.now().strftime("%Y-%m-%d")
    project = _project_name()
    digest_path = PROJ / ".agent-inbox" / f"dispatch-digest-{today}.md"

    if not AGENDA.exists():
        tg_send(token, chat, "⚠️ DISPATCH_DAY cancelled — no approved proposed_agenda.md found.")
        return 1
    agenda = AGENDA.read_text(errors="ignore")

    prompt = (
        f"You are the DAY-DISPATCHER for the {project} agent org. Today is {today}. "
        "The human has APPROVED the agenda below. Execute it AUTONOMOUSLY, end to end:\n"
        "- For EACH agenda item, use the Task tool to spawn the right agent. Give each "
        "the item as its task; let it run its OWN ReAct loop — debug, edit code, re-run "
        "tests, self-heal — until the item is done.\n"
        "- DO NOT stop or ask for approval on minor errors. Agents fix-and-continue. "
        "Abandon an item only if genuinely blocked after real attempts, and record WHY.\n"
        "- Honor standing org rules: read-only advisor agents must not edit source; "
        "no git push; local working-tree only.\n"
        f"- When finished, WRITE a completion digest to {digest_path} with, per agenda "
        "item: status (✅ done / 🟡 partial / ⛔ blocked) + one line of evidence "
        "(file, test result, change made), and anything that still needs the human.\n\n"
        "----- APPROVED AGENDA -----\n" + agenda)

    tg_send(token, chat,
            f"🚀 Autonomous run started ({today}). Agents are working on the agenda — I'll report when done.")
    status, ret = "completed", 0
    try:
        r = subprocess.run([_claude(), "--print", "--allowedTools", RUN_TOOLS],
                           cwd=str(PROJ), input=prompt, capture_output=True, text=True,
                           timeout=HARD_LIMIT_SEC)
        ret = r.returncode
        status = "done" if ret == 0 else f"done with error (exit {ret})"
        tail = (r.stdout or r.stderr or "")[-3000:]
    except subprocess.TimeoutExpired:
        status = f"stopped at time limit ({HARD_LIMIT_SEC // 60} min) — some items may be incomplete"
        tail = "(hard time limit hit)"

    digest = digest_path.read_text(errors="ignore")[:3500] if digest_path.exists() else tail
    tg_send(token, chat, f"✅ Autonomous run {status}.\n\n{digest}")
    print(f"[dispatch_day] {status}")

    # Fire the skill compiler detached so its reflection never delays this report.
    try:
        subprocess.Popen([_py(), str(PROJ / "scripts" / "skill_compiler.py")],
                         cwd=str(PROJ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except Exception as e:
        print(f"[dispatch_day] skill_compiler launch skipped: {e}", file=sys.stderr)
    return ret


if __name__ == "__main__":
    sys.exit(main())
