#!/usr/bin/env python3
"""Serial daily orchestrator for the Prytan agent org.

Runs the daily chain in ONE process, each step waiting for the previous to finish,
so staggered-cron overlap is structurally impossible. Each step is run through the
cost_governor `gate` CLI (skip-empty / throttle / circuit-breaker / single-flight).
Steps are defined in .agent-config/daily-steps.yaml and filtered by date.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEPS_PATH = ROOT / ".agent-config" / "daily-steps.yaml"
GOVERNOR = ROOT / "scripts" / "cost_governor.py"
_SCRIPTS = ROOT / "scripts"
DEFAULT_MAX_TASKS = 3   # always-on per-pod task cap; THROTTLE can lower it further

def _py() -> str:
    return shutil.which("python3") or shutil.which("python") or "python3"

def _claude() -> str:
    return shutil.which("claude") or "claude"


def _runs_today(when: str, now: datetime) -> bool:
    wd = now.weekday()  # Mon=0 .. Sun=6
    if when == "always":
        return True
    if when == "weekday":
        return wd in (0, 1, 2, 3, 4)
    if when == "monday":
        return wd == 0
    if when == "month_start":
        return now.day == 1
    return False


def load_steps(now: datetime, path: Path = STEPS_PATH) -> list[dict]:
    """Ordered steps whose schedule matches `now`. Never raises."""
    try:
        data = yaml.safe_load(Path(path).read_text()) or {}
    except (OSError, yaml.YAMLError):
        return []
    out = []
    for s in data.get("steps", []):
        days = s.get("days")
        if days is not None:
            if now.weekday() in days:
                out.append(s)
        elif _runs_today(s.get("when", "weekday"), now):
            out.append(s)
    return out


def _log(root: Path, msg: str) -> None:
    try:
        (root / ".agent-inbox").mkdir(parents=True, exist_ok=True)
        with open(root / ".agent-inbox" / "cron.log", "a") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def _default_runner(pod: str, allowed: str, prompt: str) -> int:
    """Run one gated step through cost_governor gate -> claude. Returns exit code."""
    env = dict(os.environ)
    env.setdefault("ORG_MAX_TASKS_PER_POD", str(DEFAULT_MAX_TASKS))
    cmd = [_py(), str(GOVERNOR), "gate", pod, "--",
           _claude(), "--print", "--output-format", "json", "--allowedTools", allowed]
    proc = subprocess.run(cmd, input=prompt, text=True, env=env)
    return proc.returncode


def _default_pusher(now: datetime, root: Path) -> bool:
    """Compose + push the morning brief. ~0 LLM tokens."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("morning_brief", _SCRIPTS / "morning_brief.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.push_brief(now, root)


def run_day(now: datetime, root: Path = ROOT, runner=None,
            pusher=None) -> list[tuple]:
    """Run today's chain IN ORDER. Continue on per-step failure. Returns [(pod, rc)]."""
    if runner is None:
        runner = _default_runner
    if pusher is None:
        pusher = _default_pusher
    d = now.strftime("%Y-%m-%d")
    y = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    steps = load_steps(now, root / ".agent-config" / "daily-steps.yaml")
    _log(root, f"[orchestrator] {now.isoformat()} start — {len(steps)} steps")
    results = []
    for s in steps:
        pod = s.get("pod", "default")
        allowed = s.get("allowed_tools", "Read,Write,Edit,Bash,Glob,Grep,Task")
        prompt = (s.get("prompt", "") or "").replace("<D>", d).replace("<Y>", y)
        try:
            rc = runner(pod, allowed, prompt)
        except Exception as e:
            rc = 1
            _log(root, f"[orchestrator] step {pod} EXCEPTION: {str(e)[:200]}")
        _log(root, f"[orchestrator] step {pod} rc={rc}")
        results.append((pod, rc))
    try:
        ok = pusher(now, root)
        _log(root, f"[orchestrator] brief push ok={ok}")
    except Exception as e:
        _log(root, f"[orchestrator] brief push EXCEPTION: {str(e)[:200]}")
    _log(root, f"[orchestrator] {now.isoformat()} done — {results}")
    return results


if __name__ == "__main__":
    run_day(datetime.now(timezone.utc))
