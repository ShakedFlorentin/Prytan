#!/usr/bin/env python3
"""
agent_doctor.py — Nightly driver for the doctor agent.

Two stages:
  1. INFRA health check (Python): py_compile the bot scripts + import safe modules.
     NEVER imports telegram-bot.py (it has a main loop). On failure it writes an
     ALERT to .agent-inbox/ and does NOT attempt to fix the Python — bot repair
     is human-gated.
  2. AGENT audit/repair: invoke the doctor agent with write scoped to
     .claude/agents + org dirs (via agent-doctor-perms.json) to audit/fix/propose
     agent definitions + hygiene and write a health report.

Cron-invoked nightly; also runnable by hand. `--dry-run` does stage 1 + prints
the stage-2 task without invoking the agent.

  python3 scripts/agent_doctor.py [--dry-run]

Configure DOCTOR_AGENT in .prytan.env (default: "coordinator").
"""
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
PERMS = PROJ / "scripts" / "agent-doctor-perms.json"
INBOX = PROJ / ".agent-inbox"
LEAN = ["--strict-mcp-config", "--exclude-dynamic-system-prompt-sections",
        "--no-session-persistence"]


def _claude() -> str:
    return shutil.which("claude") or "claude"


def _py() -> str:
    return shutil.which("python3") or shutil.which("python") or "python3"


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _load_env() -> dict:
    env_file = Path.home() / ".prytan.env"
    d = {}
    if env_file.exists():
        for ln in env_file.read_text().splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, _, v = ln.partition("=")
                d[k.strip()] = v.strip()
    return d


def _doctor_agent() -> str:
    return _load_env().get("DOCTOR_AGENT", "coordinator")


def infra_health():
    """(ok, detail). Compile the bot scripts + import safe helper modules."""
    problems = []
    for f in PROJ.glob("scripts/*.py"):
        if f.name.startswith("telegram-bot") or f.name.startswith("__"):
            continue   # skip files with main loops
        r = subprocess.run([_py(), "-m", "py_compile", str(f)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            problems.append(f"compile {f.name}: {r.stderr.strip()[-300:]}")
    return (not problems, "; ".join(problems))


def write_infra_alert(detail: str) -> Path:
    INBOX.mkdir(parents=True, exist_ok=True)
    p = INBOX / f"{_today()}-doctor-infra-alert.md"
    p.write_text(
        f"# 🔴 INFRA ALERT (agent_doctor, {_today()})\n\n"
        "Bot scripts failed their compile health check. This is a HUMAN-GATED "
        "repair — the doctor agent does not edit Python.\n\n"
        f"```\n{detail}\n```\n")
    return p


TASK_TEMPLATE = """You are {agent}, the agent-doctor, on your nightly run for {date}.
The driver already ran the infra health check — result: {infra}. Do not redo it.

Now audit every .claude/agents/*.md and the org comm-dirs per your protocol:
- AUTO-FIX only the mechanically-safe class (frontmatter, broken file references,
  format) and log each change with the file path.
- PROPOSE anything behavioral to .agent-proposals/{date}-doctor-<agent>.md.
- NEVER edit the chief-of-staff or coordinator agent files, product source, trust
  levels, or any agent's write scope.
Write your health report to .agent-logs/{date}-org-health.md (Audited / Auto-fixed /
Proposed / Infra alerts / Verdict GREEN|YELLOW|RED) and append one INBOX row so the
chief-of-staff surfaces it. Cite the file for every fix; re-check the live files —
do not trust the prior night's report."""


def main():
    dry = "--dry-run" in sys.argv
    logdir = PROJ / ".agent-logs"
    logdir.mkdir(parents=True, exist_ok=True)

    ok, detail = infra_health()
    infra = "GREEN (scripts compile clean)" if ok else f"RED — {detail}"
    if not ok:
        ap = write_infra_alert(detail)
        print(f"[doctor] infra RED → alert {ap}")
    else:
        print("[doctor] infra GREEN")

    # Decision-ledger mislabel lint
    try:
        sys.path.insert(0, str(PROJ / "scripts"))
        import decision_ledger as _dl
        _flags = _dl.lint_ledger() if hasattr(_dl, "lint_ledger") else []
        if _flags:
            _lines = [f"- {f['id']}: \"{f['title']}\" smells one-way "
                      f"(matched: {', '.join(f['smell'])}) but is labeled two_way — review."
                      for f in _flags]
            _rep = INBOX / f"doctor-decision-lint-{_today()}.md"
            _rep.write_text("# Decision-ledger door_type lint\n\n" + "\n".join(_lines) + "\n")
            print(f"[doctor] decision-lint: {len(_flags)} mislabeled two_way -> {_rep.name}")
        else:
            print("[doctor] decision-lint: clean")
    except Exception as e:
        print(f"[doctor] decision-lint skipped: {str(e)[:160]}")

    agent = _doctor_agent()
    task = TASK_TEMPLATE.format(date=_today(), infra=infra, agent=agent)
    if dry:
        print(f"[doctor] --dry-run; would invoke {agent} with task:\n" + task)
        return

    perms_args = ["--settings", str(PERMS)] if PERMS.exists() else []
    cmd = [_claude(), "-p", "--agent", agent] + perms_args + LEAN
    runlog = logdir / f"{_today()}-doctor-run.log"
    with runlog.open("w") as f:
        proc = subprocess.run(cmd, input=task, cwd=str(PROJ),
                              stdout=f, stderr=subprocess.STDOUT, text=True)
    print(f"[doctor] {agent} exit={proc.returncode}; log {runlog}")


if __name__ == "__main__":
    main()
