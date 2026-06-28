#!/usr/bin/env python3
"""
claim_guard.py — Flag agent claims that EXCEED what a bot-dispatched agent can do.

The trust problem: an agent's report is just text. It can claim it "ran the tests
(3 passed)" or "saved the file" — and the human can't easily tell a real result from
a confabulated one. But there's a HARD, checkable bound: agents dispatched via
@@RUN/@@RUNW get NO shell (read mode = Read/Glob/Grep; write mode = +Write/Edit on
org dirs — never Bash). So:
  - ANY claim of EXECUTION (pytest/tests, simulation, git commit) is impossible —
    the agent has no shell. It reasoned about it; it did NOT run it.
  - A READ-ONLY run additionally cannot have written/saved/created a file.

capability_warnings() turns those impossibilities into a ⚠️ the bot appends to the
relay, so the human SEES "this is unverified" instead of trusting it.

Pure stdlib (re).
"""
import re

# Completed EXECUTION of something that needs a shell — impossible (agents have no Bash).
_EXEC = re.compile(
    r"\b(?:ran|re-?ran|executed|i ran|הרצתי|רצתי|ביצעתי|בוצע)\b[^.\n]{0,50}?"
    r"\b(?:pytest|tests?|coverage|simulation|build|compile|lint)\b"
    r"|\b\d+\s*(?:tests?|checks?)\s*(?:passed|pass)\b"
    r"|\b(?:committed|pushed)\b|\bgit\s+commit\b",
    re.IGNORECASE)

# Completed WRITE of a file — impossible on a read-only run unless via @@WRITE marker.
_WROTE = re.compile(
    r"\b(?:wrote|saved|created|updated|edited|כתבתי|שמרתי|יצרתי|עדכנתי|נשמר|נכתב|נוצר)\b"
    r"[^.\n]{0,40}?(?:file|\.json|\.py|\.md|disk|report|קובץ|לדיסק)",
    re.IGNORECASE)
_HAS_WRITE_MARKER = re.compile(r"^@@WRITE:\s*\S", re.MULTILINE)


def violations(result: str, write: bool) -> list:
    """Structured findings: [{type, severity, message}].
    `write` = the run had Write/Edit on org dirs; it still NEVER has a shell."""
    text = result or ""
    out = []
    if _EXEC.search(text):
        out.append({
            "type": "exec_claim_no_shell",
            "severity": "hard",
            "message": ("Agent claims to have run/executed something — but agents have "
                        "no shell here, so it reasoned about it, not actually ran it. Verify yourself."),
        })
    if not write and _WROTE.search(text) and not _HAS_WRITE_MARKER.search(text):
        out.append({
            "type": "write_claim_read_only",
            "severity": "hard",
            "message": "Agent claims to have written/saved a file — but the run was read-only and no @@WRITE marker found. No file was written.",
        })
    return out


def capability_warnings(result: str, write: bool) -> list:
    """Human-facing warning messages (the bot's inline ⚠️ list)."""
    return [v["message"] for v in violations(result, write)]
