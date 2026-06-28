#!/usr/bin/env python3
"""
codegrapher_hook.py — Claude Code PreToolUse hook.

Intercepts Glob, Grep, and Read tool calls and prints a reminder to query
the knowledge graph first. Does NOT block the tool call — it only advises.

Installation (auto via .claude/settings.json):
    {
      "hooks": {
        "PreToolUse": [{"matcher": ".*", "hooks": [{"type": "command", "command": "python3 codegrapher_hook.py"}]}]
      }
    }

Hook protocol (Claude Code):
  - stdin: JSON with keys: tool_name, tool_input, session_id, ...
  - stdout: JSON response (see RESPONSE below)
  - Non-zero exit: Claude Code treats it as a hard block (don't use for advice-only hooks)
"""

from __future__ import annotations

import json
import sys
import os
from pathlib import Path

# Tools that trigger the reminder
SEARCH_TOOLS = {"Glob", "Grep", "Read", "LS"}

# How many times to remind per session before going quiet
MAX_REMINDERS_PER_SESSION = 3

# State file to track reminder count (per session)
STATE_DIR = Path(".agent-logs/.hook-state")


def _session_state_path(session_id: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    safe = session_id.replace("/", "_").replace("\\", "_")[:64]
    return STATE_DIR / f"{safe}.json"


def _get_reminder_count(session_id: str) -> int:
    p = _session_state_path(session_id)
    if not p.exists():
        return 0
    try:
        return json.loads(p.read_text()).get("reminders", 0)
    except Exception:
        return 0


def _increment_reminder_count(session_id: str) -> None:
    p = _session_state_path(session_id)
    count = _get_reminder_count(session_id)
    try:
        p.write_text(json.dumps({"reminders": count + 1}))
    except Exception:
        pass


def graph_exists() -> bool:
    return Path("codegrapher_out/graph.json").exists()


def build_reminder(tool_name: str, tool_input: dict) -> str:
    target = ""
    if tool_name == "Grep":
        target = tool_input.get("pattern", "")
    elif tool_name in ("Read", "Glob"):
        target = tool_input.get("path", tool_input.get("pattern", ""))

    hint = f" for `{target}`" if target else ""

    return (
        f"[Codegrapher] You're about to use **{tool_name}**{hint}. "
        f"Consider querying the knowledge graph first:\n\n"
        f"```bash\n"
        f"python3 codegrapher.py query \"{target or '<topic>'}\"\n"
        f"```\n\n"
        f"If the graph returns the file you need, read only that file. "
        f"Skip this reminder if you already queried."
    )


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        # Can't parse — let tool proceed silently
        print(json.dumps({"continue": True}))
        return

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    session_id = payload.get("session_id", "default")

    # Only act on search tools
    if tool_name not in SEARCH_TOOLS:
        print(json.dumps({"continue": True}))
        return

    # Only remind if graph exists
    if not graph_exists():
        print(json.dumps({"continue": True}))
        return

    # Check reminder budget for this session
    count = _get_reminder_count(session_id)
    if count >= MAX_REMINDERS_PER_SESSION:
        print(json.dumps({"continue": True}))
        return

    _increment_reminder_count(session_id)

    reminder = build_reminder(tool_name, tool_input)

    # Output Claude Code hook response: continue=True + message to display
    print(json.dumps({
        "continue": True,
        "stopReason": None,
        "suppressOutput": False,
        "decision": "approve_with_note",
        "note": reminder,
    }))


if __name__ == "__main__":
    main()
