#!/usr/bin/env python3
"""
open_tasks.py — Durable open-task ledger for the chief-of-staff bot.

THE PROBLEM THIS SOLVES
-----------------------
The agent's only cross-turn memory is the SDK session (1-HOUR TTL) plus any
standing priorities. When three things are in flight and one finishes, the others
lived only in the session transcript — so the moment the session rolls (idle reset,
/reset, the 1h TTL expiring, or the transcript getting summarized) the agent loses
track of still-open work.

THE FIX
-------
A tiny durable ledger of in-flight tasks that lives OUTSIDE the session at
`.agent-logs/open-tasks.json` and is re-injected into the agent's cached system
prompt on EVERY turn. Because it rides the always-present prefix, open tasks survive
any session reset.

The agent maintains it with two markers:
    @@TASK: <short title>          → open a task in flight
    @@DONE: <id or words of title> → close it when finished

Pure stdlib (json, re, uuid, datetime, pathlib). No SDK import.
"""
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
LEDGER = PROJ / ".agent-logs" / "open-tasks.json"
DONE_RETENTION_DAYS = 7

TASK_RE = re.compile(r"^@@TASK:\s*(.+)$", re.MULTILINE)
DONE_RE = re.compile(r"^@@DONE:\s*(.+)$", re.MULTILINE)

MAX_OPEN = 12


def _load() -> list:
    if not LEDGER.exists():
        return []
    try:
        data = json.loads(LEDGER.read_text(errors="ignore"))
        return data.get("tasks", []) if isinstance(data, dict) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(tasks: list) -> None:
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps({"tasks": tasks}, ensure_ascii=False, indent=2))
    except OSError:
        pass


def open_tasks() -> list:
    """Currently-open tasks (each: {id, title, opened}). Excludes done ones."""
    return [t for t in _load() if t.get("status") != "done"]


def done_tasks(now: datetime | None = None, days: int = DONE_RETENTION_DAYS) -> list:
    """Tasks closed within the last `days` (newest first)."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = now - timedelta(days=days)
    out = []
    for t in _load():
        if t.get("status") != "done":
            continue
        try:
            closed = datetime.fromisoformat(t.get("closed", "")).astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
        if closed >= cutoff:
            out.append(t)
    return sorted(out, key=lambda t: t.get("closed", ""), reverse=True)


def purge_old_done(now: datetime | None = None, days: int = DONE_RETENTION_DAYS) -> int:
    """Drop done tasks closed more than `days` ago. Returns count purged."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = now - timedelta(days=days)
    tasks = _load()
    kept, purged = [], 0
    for t in tasks:
        if t.get("status") == "done":
            try:
                closed = datetime.fromisoformat(t.get("closed", "")).astimezone(timezone.utc)
            except (ValueError, TypeError):
                closed = None
            if closed is not None and closed < cutoff:
                purged += 1
                continue
        kept.append(t)
    if purged:
        _save(kept)
    return purged


def add_task(title: str) -> dict | None:
    """Open a task. De-dupes on title (idempotent). Returns the task, or None."""
    title = (title or "").strip()
    if not title:
        return None
    tasks = _load()
    for t in tasks:
        if t.get("title", "").strip().lower() == title.lower():
            return None
    if len(tasks) >= MAX_OPEN:
        return None
    task = {
        "id": uuid.uuid4().hex[:6],
        "title": title,
        "opened": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    tasks.append(task)
    _save(tasks)
    return task


def close_task(ref: str) -> dict | None:
    """Close a task by id-prefix or title substring. Returns the closed task, or None."""
    ref = (ref or "").strip().lower()
    if not ref:
        return None
    tasks = _load()
    openables = [(i, t) for i, t in enumerate(tasks) if t.get("status") != "done"]
    idx = next((i for i, t in openables if t.get("id", "").startswith(ref)), None)
    if idx is None:
        idx = next((i for i, t in openables if ref in t.get("title", "").lower()), None)
    if idx is None:
        return None
    tasks[idx]["status"] = "done"
    tasks[idx]["closed"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _save(tasks)
    return tasks[idx]


def render_block() -> str:
    """The block injected into the agent's cached system prompt every turn.
    Empty string when nothing is open (costs zero tokens when idle)."""
    tasks = open_tasks()
    if not tasks:
        return ""
    lines = [
        "## Open work in flight — your task ledger (persists across sessions)",
        f"You have {len(tasks)} task(s) still open. This list outlives the chat "
        "session, so trust it over your memory. When you FINISH one, look at what's "
        "still open and either keep going on the next or tell the human what's left.",
    ]
    for t in tasks:
        when = (t.get("opened", "") or "")[5:10]  # MM-DD
        lines.append(f"  [{t.get('id', '??????')}] opened {when} — {t.get('title', '')}")
    lines.append(
        "Maintain it yourself: open a task when you take on real multi-step work with "
        "`@@TASK: <short title>`; close it the moment it's done with `@@DONE: <id or a "
        "few words of the title>`. One marker per line, at the END of your reply. "
        "The human never sees these lines — the wrapper strips them.")
    return "\n".join(lines)


_STATUS_EN = re.compile(r"what'?s?\s+(?:still\s+)?(?:left|open|remaining|pending|on the list)")


def is_status_query(text: str) -> bool:
    """True if the message is a short 'what's still open?' question."""
    s = (text or "").strip().lower().rstrip("?!. ")
    if not s or len(s) > 40:
        return False
    return bool(_STATUS_EN.search(s))


def status_summary(now: datetime | None = None) -> str:
    """Plain-text summary of open + closed-this-week tasks. Purges stale closed tasks."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    purge_old_done(now)
    open_ts, done_ts = open_tasks(), done_tasks(now)
    out = []
    if open_ts:
        out.append(f"🔵 Open ({len(open_ts)}):")
        out += [f"• {t.get('title','')} [{t.get('id','??????')}]" for t in open_ts]
    else:
        out.append("🔵 No open tasks right now.")
    if done_ts:
        out.append("")
        out.append(f"✅ Closed this week ({len(done_ts)}):")
        out += [f"• {t.get('title','')}" for t in done_ts]
    return "\n".join(out)


def apply_markers(reply: str) -> tuple[str, list]:
    """Parse @@TASK / @@DONE markers out of the agent's reply, apply them to the ledger,
    and return (reply_without_markers, [human-readable event strings])."""
    events: list[str] = []
    for m in TASK_RE.finditer(reply or ""):
        t = add_task(m.group(1))
        if t:
            events.append(f"opened [{t['id']}] {t['title']}")
    for m in DONE_RE.finditer(reply or ""):
        c = close_task(m.group(1))
        if c:
            events.append(f"closed [{c['id']}] {c['title']}")
    if events:
        purge_old_done()
    clean = DONE_RE.sub("", TASK_RE.sub("", reply or "")).strip()
    return clean, events
