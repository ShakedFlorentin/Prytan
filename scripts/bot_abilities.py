#!/usr/bin/env python3
"""
bot_abilities.py — pure, testable primitives for the agent's bounded abilities.

Four capabilities, each invoked by a marker the agent emits and executed by the trusted bot
layer (never via an agent shell):
  @@GIT:    read-only git (status/diff/log/show/blame/...) — situational awareness, the
            "what changed / what's the SHA" gap. NEVER commit/push (respects no-git).
  @@SHOW:   send a repo file (or a diff) to Telegram — show, don't just tell.
  @@WEB:    fetch an ALLOWLISTED doc URL — verify external API/version facts vs guessing.
  @@REMIND: schedule a self-follow-up so the agent re-initiates instead of waiting on the human.

This module holds ONLY the sanitizers/parsers (no subprocess, no network, no SDK) so the
security-critical logic is unit-testable. The bot (telegram-bot) wires the markers
and does the actual IO with these guards in front.

Pure stdlib (re, ipaddress, datetime, pathlib, urllib.parse).
"""
from __future__ import annotations

import ipaddress
import re
import socket
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import write_proposals as wp  # reuse the secret denylist (_is_denied / _DENY_GLOBS)

# ── @@GIT — read-only git ────────────────────────────────────────────────────
# Allowlist of READ-only subcommands. None of these mutate the repo or index.
_GIT_READ_SUB = {"status", "diff", "log", "show", "blame", "shortlog", "describe",
                 "branch", "tag", "ls-files", "rev-parse"}
# Flags that could write a file, run a command, or escape the repo — rejected outright.
_GIT_BAD_FLAG = ("--output", "-o", "--exec", "--ext-diff", "-c", "--upload-pack",
                 "--git-dir", "--work-tree", "-c", "--open-files-in-pager", "-O")
# Mutating flags on otherwise-read subcommands (branch/tag can delete/rename/force).
_GIT_MUTATE = {"-d", "-D", "-m", "-M", "--delete", "--move", "--force", "-f",
               "--set-upstream-to", "-u", "--edit-description", "--create-reflog"}

GIT_RE = re.compile(r"^@@GIT:\s*(.+)$", re.MULTILINE)


def safe_git_args(spec: str):
    """Sanitize a @@GIT spec into SAFE read-only git args, or None. The bot runs these
    list-form (no shell) as `git --no-pager <args>` with a cat pager. Allows only the
    read subcommands above; rejects shell metachars, write/exec/output flags, mutating
    branch/tag flags, and `..` traversal pathspecs. Fails closed."""
    spec = (spec or "").strip()
    if not spec or any(c in spec for c in ";|&$`><\n\\"):
        return None
    toks = spec.split()
    if toks[0] not in _GIT_READ_SUB:
        return None
    for t in toks[1:]:
        low = t.lower()
        if any(low == f or low.startswith(f + "=") or low == f for f in _GIT_BAD_FLAG):
            return None
        if low in _GIT_MUTATE:
            return None
        if ".." in t:               # no traversal pathspecs / range tricks into parent
            return None
    return toks


# ── @@SHOW — send a file/diff to Telegram ────────────────────────────────────
SHOW_RE = re.compile(r"^@@SHOW:\s*(.+)$", re.MULTILINE)
MAX_SHOW_BYTES = 5 * 1024 * 1024   # don't try to upload huge files


def safe_show_path(arg: str, root: Path):
    """Resolve a @@SHOW target to (mode, abs_path|relspec). mode is 'file' (send the file)
    or 'diff' (the bot generates `git diff <rel>` and sends that). Returns (None, reason)
    if unsafe: outside repo, a secret, missing, a dir, or too big. Reuses the wp denylist."""
    root = Path(root).resolve()
    arg = (arg or "").strip()
    if not arg:
        return None, "nothing to show"
    mode = "file"
    if arg.lower().startswith("diff "):
        mode, arg = "diff", arg[5:].strip()
    if not arg or set(arg) & wp._GLOB_CHARS:
        return None, "name one concrete file (no globs)"
    cand = (root / arg).resolve() if not Path(arg).is_absolute() else Path(arg).resolve()
    try:
        rel = cand.relative_to(root).as_posix()
    except ValueError:
        return None, "outside the repo"
    if wp._is_denied(rel, cand.name):
        return None, "secret/protected — denied"
    if mode == "diff":
        return "diff", rel          # bot runs `git diff -- <rel>`; file need not exist
    if not cand.exists() or cand.is_dir():
        return None, "not a file"
    if cand.stat().st_size > MAX_SHOW_BYTES:
        return None, "file too large to send"
    return "file", str(cand)


# ── @@WEB — allowlisted doc fetch (verify external facts) ─────────────────────
WEB_RE = re.compile(r"^@@WEB:\s*(\S+)$", re.MULTILINE)
# Domains the agent may fetch. Doc/reference sites only — the point is verifying API/version
# facts, not browsing. Extend deliberately; never add a domain that echoes user input.
WEB_ALLOWLIST = (
    "docs.cocotb.org", "cocotb.org", "pypi.org", "readthedocs.io",
    "docs.python.org", "python.org", "github.com", "raw.githubusercontent.com",
    "docs.anthropic.com", "developer.arm.com", "semiwiki.com",
    "docs.amd.com", "verilator.org", "yosyshq.readthedocs.io", "yosyshq.net",
)


def allowed_web_url(url: str, allowlist=WEB_ALLOWLIST) -> bool:
    """SSRF guard: True only for an http(s) URL whose host is on the allowlist and is NOT
    a raw IP, localhost, or a .local/.internal name. (Residual DNS-rebinding risk is
    accepted for a single-user local bot — the allowlist is the primary control.)"""
    try:
        p = urlparse((url or "").strip())
    except ValueError:
        return False
    if p.scheme not in ("http", "https"):
        return False
    host = (p.hostname or "").lower()
    if not host:
        return False
    try:
        ipaddress.ip_address(host)   # a raw IP literal → never allowed
        return False
    except ValueError:
        pass
    if host in ("localhost",) or host.endswith(".local") or host.endswith(".internal"):
        return False
    return any(host == d or host.endswith("." + d) for d in allowlist)


def _ip_is_public(ip_str: str) -> bool:
    """True only for a routable public IP. Rejects private (RFC1918), loopback,
    link-local (169.254/16 — the cloud-metadata range), reserved, multicast, and
    unspecified addresses. Fails closed on anything unparseable."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def host_resolves_public(host: str) -> bool:
    """Resolve host and return True only if EVERY resolved address is a public IP.
    This closes the DNS-rebinding / redirect-to-internal hole that allowed_web_url
    (a name-only check) can't see: an allowlisted name pointing at 127.0.0.1 or
    169.254.169.254 is rejected here. Fails closed on resolution failure."""
    host = (host or "").strip().lower()
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except (OSError, UnicodeError):
        return False
    if not infos:
        return False
    return all(_ip_is_public(info[4][0]) for info in infos)


class _RevalidatingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that re-applies BOTH SSRF guards to every hop. urllib follows
    3xx redirects by default, so a 200 on an allowlisted URL could 302 to an internal
    address — the original-URL-only check would never see it. Each redirect target must
    re-pass allowed_web_url AND host_resolves_public, else the redirect is refused."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host = (urlparse(newurl).hostname or "")
        if not allowed_web_url(newurl) or not host_resolves_public(host):
            raise urllib.error.HTTPError(
                newurl, code, f"redirect blocked (off-allowlist / non-public): {newurl[:80]}",
                headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_safe_opener() -> "urllib.request.OpenerDirector":
    """An opener whose every redirect hop is re-validated by the SSRF guards above.
    Use this instead of urllib.request.urlopen for any agent-driven fetch."""
    return urllib.request.build_opener(_RevalidatingRedirectHandler())


# ── @@REMIND — self-scheduled follow-up ──────────────────────────────────────
REMIND_RE = re.compile(r"^@@REMIND:\s*(\S+)\s*::\s*(.+)$", re.MULTILINE)
_REL_RE = re.compile(r"^(\d+)\s*(m|min|mins|h|hr|hrs|hour|hours|d|day|days)$", re.IGNORECASE)
_HHMM_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
MAX_REMIND_DAYS = 14


def parse_when(spec: str, now: datetime):
    """Parse a reminder 'when' into a UTC datetime, or None. Accepts relative (`30m`,
    `2h`, `1d`) and absolute `HH:MM` (next occurrence, today or tomorrow). Caps at
    MAX_REMIND_DAYS so a typo can't park a reminder a year out."""
    s = (spec or "").strip().lower()
    now = now.astimezone(timezone.utc)
    m = _REL_RE.match(s)
    if m:
        n, u = int(m.group(1)), m.group(2)
        delta = (timedelta(minutes=n) if u.startswith("m")
                 else timedelta(hours=n) if u.startswith("h")
                 else timedelta(days=n))
        when = now + delta
    else:
        m = _HHMM_RE.match(s)
        if not m:
            return None
        when = now.replace(hour=int(m.group(1)), minute=int(m.group(2)),
                           second=0, microsecond=0)
        if when <= now:
            when += timedelta(days=1)
    if when <= now or when > now + timedelta(days=MAX_REMIND_DAYS):
        return None
    return when


import json  # noqa: E402  (kept local to the reminder store)

REMINDERS_PATH = wp.ROOT / ".agent-inbox" / "reminders.json"


def _load_reminders(path: Path) -> list:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError, json.JSONDecodeError):
        return []


def add_reminder(when: datetime, text: str, chat_id: str, path: Path = REMINDERS_PATH) -> dict:
    """Persist a reminder. when is a UTC datetime (from parse_when)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"due": when.astimezone(timezone.utc).isoformat(), "text": text.strip()[:400],
           "chat_id": str(chat_id)}
    items = _load_reminders(path)
    items.append(rec)
    path.write_text(json.dumps(items, indent=2, ensure_ascii=False))
    return rec


def due_reminders(now: datetime, path: Path = REMINDERS_PATH) -> list:
    """Pop and return reminders whose due time has passed (rewrites the file without
    them). Returns [] if none/none-due. Safe to call on a schedule."""
    path = Path(path)
    items = _load_reminders(path)
    if not items:
        return []
    now = now.astimezone(timezone.utc)
    due, keep = [], []
    for r in items:
        try:
            d = datetime.fromisoformat(r["due"]).astimezone(timezone.utc)
        except (ValueError, KeyError):
            continue          # drop malformed
        (due if d <= now else keep).append(r)
    if due:
        path.write_text(json.dumps(keep, indent=2, ensure_ascii=False))
    return due
