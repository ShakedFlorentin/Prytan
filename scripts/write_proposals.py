#!/usr/bin/env python3
"""
write_proposals.py — Bounded confirm-to-write for product-source edits over Telegram.

Background. `@@RUNW` lets the agent dispatch a write-agent prompt-free, but ONLY scoped to
the org dirs (`.planning/`, `.agent-*`). Product source (`src/…`) is deliberately
outside that scope, so when a real fix needs to touch `src/`, the agent hits a wall and (in
the past) confabulated a "click Allow" button that does not exist over Telegram.

The human-gated model:: a HUMAN-GATED, per-action, file-scoped grant.
  1. the agent emits  @@WPROPOSE: <agent> :: <file1>,<file2> :: <task>   (no UI, no button).
  2. The bot validates the files, stores ONE pending proposal (with a TTL), and asks
     the human to confirm.
  3. The human replies a confirm token ("מאושר" / "approved" / …). The bot builds a
     one-shot --settings file scoped to EXACTLY those files (broad Read minus secrets,
     Write/Edit on the named paths only), dispatches the agent headless, then discards
     the grant.

This is NOT a standing permission widening: it never edits `.claude/settings.json`,
the grant is ephemeral, scoped to named files, and only fires on the human's explicit
reply. Fails closed everywhere (bad path → rejected; no/expired proposal → no action).

Pure stdlib (re, json, fnmatch, pathlib, datetime). No SDK import, so it is unit-
testable on python3.11 without the Telegram/Claude runtime.
"""
from __future__ import annotations

import fnmatch
import json
import re
from datetime import datetime, timezone
from pathlib import Path

# Repo root (same anchor the bot uses as PROJ). Overridable per-call for tests.
ROOT = Path(__file__).resolve().parent.parent
PENDING_PATH = ROOT / ".agent-inbox" / "pending-write.json"
TTL_MINUTES = 60   # was 15 — a 15-min window silently expired before the human replied "מאושר"

# The agent's marker. Three "::"-separated fields: agent, comma-list of files, task.
WPROPOSE_RE = re.compile(r"^@@WPROPOSE:\s*([a-z][a-z0-9_-]*)\s*::\s*(.+?)\s*::\s*(.+)$",
                         re.MULTILINE)

# A reply that authorizes the pending proposal. Whole-message match (after strip/lower)
# so a confirm word buried in a sentence does NOT silently trigger a write.
_CONFIRM_TOKENS = {
    "מאושר", "מאשר", "אשר", "אישור", "לאשר", "אשר את זה", "כן תאשר",
    "approved", "approve", "allow", "allowed", "confirm", "confirmed",
    "go", "go ahead", "do it", "yes do it", "ok do it",
}

# Paths that must NEVER be writable or readable through this grant, even if the agent names
# them. fnmatch patterns, checked against the path RELATIVE to root and its basename.
_DENY_GLOBS = (
    ".env", ".env.*", "*.env",
    "*.key", "*.pem", "*.crt", "*.p12",
    "*secret*", "*credential*",
    ".claude/*", ".claude/**",
    "CLAUDE.local.md",
    "*.db", "*.sqlite", "*.sqlite3",
    ".git/*", ".git/**",
    "*.prytan.env",
)

# Characters that mean "this is a glob, not a single concrete file" → reject.
_GLOB_CHARS = set("*?[]")


def is_confirm(text: str) -> bool:
    """True iff the WHOLE message is a confirm token (after strip/lower). Conservative
    on purpose: 'נראה לי שאפשר לאשר את זה מחר' must NOT confirm — only a bare 'מאושר'."""
    if not text:
        return False
    return text.strip().lower() in _CONFIRM_TOKENS


def parse_propose(reply: str):
    """Pull the first @@WPROPOSE marker from the agent's reply.
    Returns (clean_reply, proposal | None) where proposal is
    {'agent': str, 'files': [str, ...], 'task': str} with raw (unvalidated) file
    strings. All @@WPROPOSE lines are stripped from clean_reply either way."""
    m = WPROPOSE_RE.search(reply or "")
    clean = WPROPOSE_RE.sub("", reply or "").strip()
    if not m:
        return clean, None
    agent = m.group(1).strip().lower()
    files = [f.strip() for f in m.group(2).split(",") if f.strip()]
    task = m.group(3).strip()
    if not files or not task:
        return clean, None
    return clean, {"agent": agent, "files": files, "task": task}


def _is_denied(rel: str, name: str) -> bool:
    """Match the denylist case-INsensitively (macOS default FS is case-insensitive, so
    `.ENV` IS `.env`) and against trailing-space/dot variants (`'.env '` resolves to a
    basename the literal glob would miss). Both sides are casefolded so fnmatchcase is
    effectively case-insensitive."""
    cands = {rel, name, name.rstrip(" ."), rel.rstrip(" .")}
    cands = {c.casefold() for c in cands if c}
    globs = [g.casefold() for g in _DENY_GLOBS]
    return any(fnmatch.fnmatchcase(c, g) for c in cands for g in globs)


def validate_files(files, root: Path):
    """Map raw file strings to safe absolute paths under root.
    Returns (ok_abs: [str], rejected: [(raw, reason)]). A file is OK iff:
      - it contains no glob metacharacters,
      - it resolves to a path strictly under root (no traversal / absolute escape),
      - it is not on the secrets denylist,
      - it is not an existing directory,
      - its parent directory already exists (no writing into arbitrary new trees).
    Everything else is rejected with a reason. Fails closed."""
    root = Path(root).resolve()
    ok, rejected = [], []
    for raw in files:
        if not raw or set(raw) & _GLOB_CHARS:
            rejected.append((raw, "glob/empty not allowed — name one concrete file"))
            continue
        # Resolve against root. An absolute raw path that escapes root is caught below.
        cand = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        try:
            rel = cand.relative_to(root).as_posix()
        except ValueError:
            rejected.append((raw, "outside the repo root"))
            continue
        if _is_denied(rel, cand.name):
            rejected.append((raw, "secret/protected path — denied"))
            continue
        if cand.is_dir():
            rejected.append((raw, "is a directory — name a file"))
            continue
        if not cand.parent.exists():
            rejected.append((raw, "parent directory does not exist"))
            continue
        ok.append(str(cand))
    return ok, rejected


def validate_org_path(path: str, root: Path, org_dirs):
    """Validate a @@WRITE target: a single concrete file under one of the ORG dirs
    (.planning/, .agent-*). Returns (abs_path:str, None) if safe, else (None, reason).
    This is the containment for the agent's content-carrying write primitive — the bot lays
    the bytes down directly, so the path MUST be:
      - no glob metacharacters, no empty,
      - resolved strictly under root (no traversal / absolute escape),
      - under one of org_dirs (never src/, tests/, cli.py, pyproject, .claude/...),
      - not on the secrets denylist,
      - not an existing directory.
    Parent dirs inside an org dir may be created by the caller. Fails closed."""
    root = Path(root).resolve()
    raw = (path or "").strip()
    if not raw or set(raw) & _GLOB_CHARS:
        return None, "glob/empty not allowed — name one concrete file"
    cand = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    try:
        rel = cand.relative_to(root).as_posix()
    except ValueError:
        return None, "outside the repo root"
    parts = rel.split("/", 1)
    top = parts[0]
    if top not in set(org_dirs):
        return None, f"@@WRITE is org-dirs only ({', '.join(org_dirs)}); not '{top}'"
    if len(parts) == 1 or not parts[1]:
        return None, "name a file INSIDE the org dir, not the dir itself"
    if _is_denied(rel, cand.name):
        return None, "secret/protected path — denied"
    if cand.is_dir():
        return None, "is a directory — name a file"
    return str(cand), None


def build_scoped_perms(abs_files, root: Path) -> dict:
    """A --settings dict granting broad Read/Glob/Grep MINUS secrets, plus Write/Edit on
    EXACTLY the named files (the '//abs' form Claude Code honors, matching the bot's
    existing perms file). deny overrides allow, so secrets stay unreadable even though
    Read is broad. No directory or glob write is ever emitted."""
    root = Path(root).resolve()
    allow = ["Read", "Glob", "Grep"]
    for p in abs_files:
        allow.append(f"Write(/{p})")   # p is absolute (starts with '/') → '//abs/file'
        allow.append(f"Edit(/{p})")
    deny = []
    for g in _DENY_GLOBS:
        ap = f"/{root}/{g}"            # '//root/<glob>'
        deny += [f"Read({ap})", f"Write({ap})", f"Edit({ap})"]
    return {
        "_comment": "EPHEMERAL one-shot grant (write_proposals). Write/Edit scoped to "
                    "the human-confirmed files only; secrets denied. Discarded after use.",
        "permissions": {"allow": allow, "deny": deny},
    }


# NOTE: the agent's read scope (Read/Glob, secrets denied) is enforced by a --settings
# deny file built in bot._cs_read_settings_file, which reuses `_DENY_GLOBS`
# below. A per-call can_use_tool callback was tried first but the SDK does NOT consult it
# for the default-allowed Read tool — only a settings `deny` rule gates Read. So the
# denylist is shared; there is no read-gate function here.


def scope_allows(file_path: str, globs, root: Path) -> bool:
    """True if file_path falls inside an AUTHORIZED goal write-scope: a concrete file
    (no glob chars) under root, NOT a secret (the denylist wins even inside an authorized
    scope), and matching one of the scope globs. Used to skip per-file approval for in-scope
    writes. Fails closed (empty globs, escape, secret, or no match → False)."""
    if not globs:
        return False
    root = Path(root).resolve()
    raw = (file_path or "").strip()
    if not raw or set(raw) & _GLOB_CHARS:
        return False
    cand = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    try:
        rel = cand.relative_to(root).as_posix()
    except ValueError:
        return False
    if _is_denied(rel, cand.name):          # secrets are NEVER in scope
        return False
    for g in globs:
        g = (g or "").strip()
        if not g:
            continue
        if fnmatch.fnmatch(rel, g):
            return True
        gp = g.rstrip("/*")                  # directory-style scope: "src/foo" / "src/foo/"
        if gp and (rel == gp or rel.startswith(gp + "/")):
            return True
    return False


def save_pending(proposal: dict, now: datetime, chat_id: str,
                 path: Path = PENDING_PATH) -> None:
    """Persist ONE pending proposal (overwrites any prior one — single-slot by design)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = dict(proposal)
    rec["chat_id"] = str(chat_id)
    rec["created"] = now.astimezone(timezone.utc).isoformat()
    path.write_text(json.dumps(rec, indent=2, ensure_ascii=False))


def load_pending(now: datetime, path: Path = PENDING_PATH):
    """Return the pending proposal if present and not past its TTL, else None.
    A missing, malformed, or expired record returns None (fails closed)."""
    path = Path(path)
    try:
        rec = json.loads(path.read_text())
        created = datetime.fromisoformat(rec["created"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None
    age_min = (now.astimezone(timezone.utc) - created.astimezone(timezone.utc)).total_seconds() / 60.0
    if age_min > TTL_MINUTES:
        return None
    return rec


def expired_pending(now: datetime, path: Path = PENDING_PATH):
    """Return the pending record IF it exists but is PAST its TTL (else None). Lets the
    bot tell 'no proposal at all' apart from 'a proposal that silently expired', so a late
    'מאושר' gets a 'resend it' nudge instead of vanishing into a normal agent turn."""
    path = Path(path)
    try:
        rec = json.loads(path.read_text())
        created = datetime.fromisoformat(rec["created"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None
    age_min = (now.astimezone(timezone.utc) - created.astimezone(timezone.utc)).total_seconds() / 60.0
    return rec if age_min > TTL_MINUTES else None


def clear_pending(path: Path = PENDING_PATH) -> None:
    """Remove the pending proposal. Idempotent."""
    try:
        Path(path).unlink()
    except OSError:
        pass
