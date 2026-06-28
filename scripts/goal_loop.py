#!/usr/bin/env python3
"""
goal_loop.py — persistent goal + bounded autonomous loop for the chief-of-staff.

`/goal` sets a durable target the agent works toward; `/loop` drives toward it WITHOUT asking
the human at every step (the dependency fix). This module holds the STATE and the pure
decision helpers — testable without the SDK/bot. The driver itself lives in
telegram-bot.run_goal_loop, which owns invoke_agent / run_agent / cost_governor.

Safety invariant (enforced by the driver, encoded here): the loop auto-runs only
REVERSIBLE work; it pauses and surfaces for a one-way/strategic decision (@@DECIDE), a
product-source write (@@WPROPOSE → needs מאושר), the step/budget backstop, or goal-done
(@@GOAL_DONE). "Balanced" dial: ≤10 steps, stop after 2 idle steps, monthly-budget
throttle as the spend backstop.

Pure stdlib (json, re, datetime, pathlib). No SDK import.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOAL_PATH = ROOT / ".agent-inbox" / "goal.json"
LOOP_PATH = ROOT / ".agent-inbox" / "loop-state.json"

# "Balanced" dial.
MAX_STEPS = 10
NO_PROGRESS_LIMIT = 2          # consecutive idle (no-action) steps → stop
_PROGRESS_KEEP = 12            # cap stored progress notes

# Loop-control markers the agent emits in a loop turn.
DONE_RE = re.compile(r"^@@GOAL_DONE:\s*(.+)$", re.MULTILINE)
DECIDE_RE = re.compile(r"^@@DECIDE:\s*(two_way|one_way|strategic_fork)\s*::\s*(.+)$",
                       re.MULTILINE | re.IGNORECASE)
_MARKER_SUB = re.compile(r"^@@(?:GOAL_DONE|DECIDE):.*$", re.MULTILINE)

# Markers the agent emits in a NORMAL chat turn to self-start work (so the human never has to
# type /goal or /loop). @@GOAL: sets the target; @@SCOPE: proposes a product-source write
# scope (authorized once by the human → in-scope writes skip per-file approval); @@LOOP drives.
SET_GOAL_RE = re.compile(r"^@@GOAL:\s*(.+)$", re.MULTILINE)   # NOTE: not @@GOAL_DONE (no ':')
SCOPE_RE = re.compile(r"^@@SCOPE:\s*(.+)$", re.MULTILINE)
LOOP_RE = re.compile(r"^@@LOOP\b.*$", re.MULTILINE)
TEST_RE = re.compile(r"^@@TEST:\s*(.+)$", re.MULTILINE)        # bot-run pytest (no agent shell)
_CHATMARKER_SUB = re.compile(r"^@@(?:GOAL:|SCOPE:|LOOP\b).*$", re.MULTILINE)


def safe_test_args(spec: str):
    """Sanitize a @@TEST spec into SAFE list-form pytest args, or None if unsafe. Allows
    ONLY: a path/node under tests/ (e.g. tests/test_x.py or tests/test_x.py::test_y), or
    -k "<expr>" with word/space/.()-/ chars. Rejects shell metachars, flags like -p/--pdb,
    and anything outside tests/. The bot runs these list-form (no shell) so there is no
    injection surface even before this check — this is defense in depth."""
    spec = (spec or "").strip()
    if not spec:
        return None
    if any(c in spec for c in ';|&$`><\n\\'):
        return None
    if spec.startswith("-k "):
        expr = spec[3:].strip().strip('"').strip("'")
        if expr and re.fullmatch(r"[\w\s().\-/]+", expr):
            return ["-k", expr]
        return None
    # else: a test node/path — must be under tests/ and contain no flag chars
    node = spec.split("::", 1)[0]
    if not node.startswith("tests/") or node.startswith("-") or ".." in spec:
        return None
    if not re.fullmatch(r"[\w./\-]+(::[\w\-]+)?", spec):
        return None
    return [spec]


# ── goal store ───────────────────────────────────────────────────────────────
def _now_iso(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat()


def set_goal(text: str, now: datetime, path: Path = GOAL_PATH) -> dict:
    """Set (replace) the active goal. Resets progress."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"text": text.strip(), "set_at": _now_iso(now), "status": "active", "progress": []}
    path.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    return rec


def load_goal(path: Path = GOAL_PATH):
    """The active goal dict, or None if unset/cleared/malformed."""
    try:
        rec = json.loads(Path(path).read_text())
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return rec if rec.get("status") == "active" and rec.get("text") else None


def clear_goal(path: Path = GOAL_PATH) -> None:
    try:
        Path(path).unlink()
    except OSError:
        pass


def append_progress(note: str, now: datetime, path: Path = GOAL_PATH) -> None:
    """Append a progress note to the active goal (keeps the last _PROGRESS_KEEP)."""
    rec = load_goal(path)
    if not rec:
        return
    rec.setdefault("progress", []).append({"at": _now_iso(now), "note": note.strip()[:300]})
    rec["progress"] = rec["progress"][-_PROGRESS_KEEP:]
    Path(path).write_text(json.dumps(rec, indent=2, ensure_ascii=False))


# ── loop state ───────────────────────────────────────────────────────────────
def start_loop(now: datetime, path: Path = LOOP_PATH) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    st = {"running": True, "started_at": _now_iso(now), "step": 0, "stop_requested": False}
    path.write_text(json.dumps(st, indent=2))
    return st


def loop_state(path: Path = LOOP_PATH) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError, json.JSONDecodeError):
        return {"running": False, "step": 0, "stop_requested": False}


def is_running(path: Path = LOOP_PATH) -> bool:
    return bool(loop_state(path).get("running"))


def request_stop(path: Path = LOOP_PATH) -> bool:
    """Ask a running loop to stop at its next checkpoint. Returns True if one was running."""
    st = loop_state(path)
    if not st.get("running"):
        return False
    st["stop_requested"] = True
    Path(path).write_text(json.dumps(st, indent=2))
    return True


def stop_requested(path: Path = LOOP_PATH) -> bool:
    return bool(loop_state(path).get("stop_requested"))


def bump_step(path: Path = LOOP_PATH) -> int:
    st = loop_state(path)
    st["step"] = int(st.get("step", 0)) + 1
    Path(path).write_text(json.dumps(st, indent=2))
    return st["step"]


def stop_loop(path: Path = LOOP_PATH) -> None:
    st = loop_state(path)
    st["running"] = False
    st["stop_requested"] = False
    Path(path).write_text(json.dumps(st, indent=2))


# ── marker parsing ───────────────────────────────────────────────────────────
def parse_done(reply: str):
    """The agent's @@GOAL_DONE summary, or None."""
    m = DONE_RE.search(reply or "")
    return m.group(1).strip() if m else None


def parse_decide(reply: str):
    """The agent's @@DECIDE marker → (door_type, title), or None. two_way is NOT a real
    escalation (the driver logs it and keeps going); one_way/strategic_fork surface."""
    m = DECIDE_RE.search(reply or "")
    if not m:
        return None
    return m.group(1).strip().lower(), m.group(2).strip()


def strip_markers(reply: str) -> str:
    """Remove loop-control markers so the human sees clean prose."""
    return _MARKER_SUB.sub("", reply or "").strip()


def apply_chat_markers(reply: str):
    """For a NORMAL chat turn: pull the self-start markers the agent emitted so it can begin
    work without the human typing /goal or /loop. Returns
    (clean_reply, set_goal_text | None, scope_globs | None, start_loop: bool). Markers
    are stripped either way."""
    m = SET_GOAL_RE.search(reply or "")
    goal_text = m.group(1).strip() if m else None
    sm = SCOPE_RE.search(reply or "")
    scope = [g.strip() for g in sm.group(1).split(",") if g.strip()] if sm else None
    start_loop = bool(LOOP_RE.search(reply or ""))
    clean = _CHATMARKER_SUB.sub("", reply or "").strip()
    return clean, goal_text, scope, start_loop


# ── goal write-scope (pre-authorized product-source paths) ───────────────────
def set_scope(globs, now: datetime, path: Path = GOAL_PATH):
    """Attach a PROPOSED (unauthorized) write scope to the active goal. Requires a goal."""
    rec = load_goal(path)
    if not rec:
        return None
    rec["scope"] = {"globs": list(globs), "authorized": False, "set_at": _now_iso(now)}
    Path(path).write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    return rec["scope"]


def pending_scope(path: Path = GOAL_PATH):
    """Globs of a scope that's set but NOT yet authorized (so מאושר knows to grant it)."""
    sc = (load_goal(path) or {}).get("scope")
    if sc and not sc.get("authorized") and sc.get("globs"):
        return sc["globs"]
    return None


def authorize_scope(path: Path = GOAL_PATH) -> bool:
    """Mark the pending scope authorized (called on the human approval). True if one flipped."""
    rec = load_goal(path)
    sc = (rec or {}).get("scope")
    if not sc or sc.get("authorized") or not sc.get("globs"):
        return False
    sc["authorized"] = True
    Path(path).write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    return True


def authorized_scope(path: Path = GOAL_PATH) -> list:
    """Globs the agent may write WITHOUT per-file approval for the active goal ([] if none/unauth)."""
    sc = (load_goal(path) or {}).get("scope")
    return (sc.get("globs") or []) if sc and sc.get("authorized") else []


# ── stop decision (the budget/step backstop) ─────────────────────────────────
def should_stop(step: int, mtd_tokens: int, soft_threshold: int,
                idle: int, stop_req: bool):
    """(stop, reason) before running step N. Order: human stop → step cap → budget
    throttle → no-progress. soft_threshold ≤ 0 disables the budget check."""
    if stop_req:
        return True, "stopped by you"
    if step >= MAX_STEPS:
        return True, f"step cap ({MAX_STEPS})"
    if soft_threshold > 0 and mtd_tokens >= soft_threshold:
        return True, "budget cap"
    if idle >= NO_PROGRESS_LIMIT:
        return True, f"no progress in {NO_PROGRESS_LIMIT} steps"
    return False, ""


# ── render (injected into the agent's context each turn) ───────────────────────────
def render_goal_block(path: Path = GOAL_PATH) -> str:
    """A compact 'Active goal' block for the agent's system prompt, so it ALWAYS knows the
    standing objective and drives toward it instead of waiting to be told. '' if none."""
    rec = load_goal(path)
    if not rec:
        return ""
    lines = ["## Active goal (work toward this; don't wait to be told)", rec["text"]]
    prog = rec.get("progress") or []
    if prog:
        lines.append("recent progress:")
        lines += [f"- {p['note']}" for p in prog[-4:]]
    return "\n".join(lines)
