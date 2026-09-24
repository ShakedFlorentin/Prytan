#!/usr/bin/env python3
"""Generate and optionally install crontab entries for the Prytan scheduler.

Reads schedule times from config.yaml, then generates cron lines that call
`python -m core.scheduler` with stdout/stderr piped into .logs/cron.log.

Usage:
    python scripts/cron-install.py            # print cron lines, don't install
    python scripts/cron-install.py --install  # merge into the current crontab
    python scripts/cron-install.py --remove   # remove Prytan lines from crontab
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

# Sentinel comments that bracket Prytan's crontab block
_BEGIN = "# BEGIN prytan"
_END = "# END prytan"


def _hhmm_to_cron(hhmm: str) -> tuple[str, str]:
    """'HH:MM' → ('MM', 'HH')."""
    h, m = hhmm.split(":")
    return m.lstrip("0") or "0", h.lstrip("0") or "0"


def generate_lines(config, project_dir: str) -> list[str]:
    """Return cron lines (no surrounding comments) for this project."""
    sch = config.schedule
    log = f"{project_dir}/.logs/cron.log"
    py = sys.executable
    sched_cmd = f"cd {project_dir} && {py} -m core.scheduler"
    work_days = "1-5"   # Mon-Fri; adjust if config.work_week differs

    lines = []

    def add(cron_min, cron_hr, cron_dom, cron_mon, cron_dow, sub_cmd):
        lines.append(
            f"{cron_min} {cron_hr} {cron_dom} {cron_mon} {cron_dow}"
            f"  {sched_cmd} {sub_cmd} >> {log} 2>&1"
        )

    # nightly chain — runs after midnight on work days
    if t := sch.get("summarize"):
        mm, hh = _hhmm_to_cron(t)
        add(mm, hh, "*", "*", work_days, "nightly")

    # cadence meetings
    meeting_map = {
        "pod_daily":         ("pod-daily",         "*", "*", work_days),
        "weekly_sprint":     ("weekly-sprint",      "*", "*", "1"),       # Monday
        "monthly_milestone": ("monthly-milestone",  "1", "*", "*"),       # 1st of month
    }
    for key, (kind, dom, mon, dow) in meeting_map.items():
        if t := sch.get(key):
            mm, hh = _hhmm_to_cron(t)
            add(mm, hh, dom, mon, dow, f"meeting {kind}")

    return lines


def _current_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout


def _write_crontab(text: str) -> None:
    subprocess.run(["crontab", "-"], input=text, text=True, check=True)


def _strip_block(crontab: str) -> str:
    """Remove the existing Prytan block from a crontab string."""
    lines, inside = [], False
    for line in crontab.splitlines():
        if line.strip() == _BEGIN:
            inside = True
        elif line.strip() == _END:
            inside = False
        elif not inside:
            lines.append(line)
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--install", action="store_true",
                        help="merge generated lines into the current crontab")
    parser.add_argument("--remove", action="store_true",
                        help="remove Prytan lines from the current crontab")
    args = parser.parse_args(argv)

    project_dir = str(Path.cwd().resolve())
    sys.path.insert(0, project_dir)
    from core.config import Config
    config = Config.load(Path(project_dir) / "config.yaml")

    if args.remove:
        current = _current_crontab()
        cleaned = _strip_block(current)
        _write_crontab(cleaned)
        print("Prytan crontab block removed.")
        return 0

    new_lines = generate_lines(config, project_dir)
    block = "\n".join([_BEGIN] + new_lines + [_END])

    if not args.install:
        print("# Prytan crontab entries (preview — run --install to apply):\n")
        print(block)
        return 0

    current = _current_crontab()
    cleaned = _strip_block(current)
    merged = cleaned.rstrip() + "\n\n" + block + "\n"
    _write_crontab(merged)
    print(f"Installed {len(new_lines)} cron line(s) for project: {project_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
