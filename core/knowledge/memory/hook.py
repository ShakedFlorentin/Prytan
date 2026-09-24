#!/usr/bin/env python3
"""Memory hooks for Claude Code (wired in hooks/hooks.json).

  • UserPromptSubmit → inject memories relevant to the prompt, each with the
    line that carries the fact. Words propose candidates (per passage, not per
    file) and a strict word gate decides; projects that opt in
    (memory.semantic: true) let a local embedding model decide instead
    (core/knowledge/relevance.py, semantic.py). Usually nothing is printed.
    Candidates: memory/, the comm dirs, per-agent logs and saved turns
    (core/knowledge/memory/sources.py), read fresh from disk.
  • SessionStart → if semantic recall is on, embed new/changed memories in the
    background.
  • Stop → save the finished turn to .logs/conversations.jsonl so later prompts
    can recall it: local only (a .logs/.gitignore keeps it out of git), prompt
    and reply capped at CAP chars, secrets redacted, a repeat save of the same
    turn skipped.

Stdout of UserPromptSubmit is added to the model's context. Any error exits 0
silently: a memory hook must never block a session.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # plugin root

from core.knowledge.memory.sources import (  # noqa: E402
    CONVERSATIONS, embedder, gather, semantic_enabled,
)
from core.knowledge.relevance import render, select  # noqa: E402

N_PROMPT = 3
CAP = 500
_TAIL = 200  # recent records checked for a duplicate save

# Order matters: whole blocks and URLs first, then token shapes, then KEY=value.
_REDACT = [
    # PEM private keys (whitespace is collapsed before redaction; END may be cut off)
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)",
               re.DOTALL),
    # credentials inside URLs: scheme://user:pass@host → scheme://[REDACTED]@host
    re.compile(r"(?<=://)[^/\s:@]+:[^@\s/]+(?=@)"),
    # JWTs: three base64url segments, the first a JSON header ("eyJ")
    re.compile(r"\beyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}"),
    # vendor token prefixes (hyphen and underscore styles)
    re.compile(r"\b(?:sk-|sk_live_|sk_test_|rk_live_|rk_test_|pk_live_|whsec_|ghp_|gho_|ghs_|"
               r"ghu_|github_pat_|glpat-|xox[abprs]-|AKIA|ASIA|AIza|hf_|npm_)[A-Za-z0-9_\-]{8,}"),
    # long hex / base64-ish blobs (keys, hashes, session secrets)
    re.compile(r"\b[A-Fa-f0-9]{32,}\b"),
    # random-looking blobs: 32+ chars mixing digits, upper and lower case (paths and
    # snake_case identifiers don't mix all three, so they survive)
    re.compile(r"(?<![\w+=-])(?=[\w+-]*\d)(?=[\w+-]*[A-Z])(?=[\w+-]*[a-z])[\w+-]{32,}={0,2}"
               r"(?![\w+=-])"),
    # KEY=value / password: value
    re.compile(r"(?i)\b([A-Z0-9_]*(?:password|passwd|pwd|secret|api[_-]?key|token|session_key|"
               r"private[_-]?key|access[_-]?key|credential)s?)(\s*[:=]\s*)\S+"),
]
# Harness wrappers that are not what the user typed.
_WRAPPERS = re.compile(r"<(system-reminder|command-[a-z-]+|local-command-[a-z-]+)>.*?</\1>",
                       re.DOTALL)


def _root(event: dict) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")


# ── UserPromptSubmit ────────────────────────────────────────────────────────

def recall_block(root: Path, prompt: str, session: str = "", n: int = N_PROMPT,
                 semantic: bool | None = None) -> str:
    """semantic=None follows the project's opt-in (memory.semantic in config.yaml)."""
    if semantic is None:
        semantic = semantic_enabled(root)
    emb = embedder(root) if semantic else None
    return render(select(prompt, gather(root, exclude_session=session), n, emb))


def warm_in_background(root: Path) -> None:
    """Embed new/changed memories without delaying the session."""
    import subprocess

    plugin = Path(__file__).resolve().parents[3]
    try:
        subprocess.Popen([sys.executable, "-m", "core.knowledge.memory", "warm", "--root",
                          str(root)], cwd=str(plugin), stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError:
        pass


# ── Stop ────────────────────────────────────────────────────────────────────

def _redact(text: str) -> str:
    for pat in _REDACT:
        if pat.groups >= 2:
            text = pat.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)
        else:
            text = pat.sub("[REDACTED]", text)
    return text


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", _WRAPPERS.sub("", text)).strip()
    return _redact(text)[:CAP]


def _text_of(content) -> str:
    """Plain text of a message; "" for tool results / tool calls."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text" and b.get("text"))
    return ""


def last_turn(transcript: Path) -> tuple[str, str]:
    """(prompt, reply) of the last user turn in a Claude Code transcript."""
    prompt, reply = "", ""
    with transcript.open(errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message") or {}
            if rec.get("type") == "user" and not rec.get("isMeta"):
                text = _clean(_text_of(msg.get("content")))
                if text:  # tool results carry no text → not a new turn
                    prompt, reply = text, ""
            elif rec.get("type") == "assistant":
                text = _text_of(msg.get("content"))
                if text.strip():
                    reply = text
    return prompt, _clean(reply)


def _already_saved(store: Path, key: str) -> bool:
    if not store.exists():
        return False
    for line in store.read_text(errors="replace").splitlines()[-_TAIL:]:
        try:
            if json.loads(line).get("key") == key:
                return True
        except ValueError:
            continue
    return False


def remember(event: dict, root: Path) -> bool:
    transcript = Path(event.get("transcript_path") or "")
    if not transcript.is_file():
        return False
    prompt, reply = last_turn(transcript)
    if event.get("last_assistant_message"):
        reply = _clean(event["last_assistant_message"])
    if not prompt:
        return False
    session = event.get("session_id", "")
    # Keyed on the text alone: the same exchange repeated in another session is
    # still one memory, not a new candidate each time.
    key = hashlib.sha1(f"{prompt}\0{reply}".encode()).hexdigest()[:16]
    store = root / CONVERSATIONS
    if _already_saved(store, key):
        return False
    store.parent.mkdir(parents=True, exist_ok=True)
    ignore = store.parent / ".gitignore"
    if not ignore.exists():
        ignore.write_text(f"{store.name}\n")
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "session_id": session, "prompt": prompt, "reply": reply, "key": key}
    with store.open("a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return True


def main() -> int:
    try:
        event = json.loads(sys.stdin.read())
        name = event.get("hook_event_name", "")
        if name == "UserPromptSubmit":
            prompt = (event.get("prompt") or "").strip()
            block = recall_block(_root(event), prompt, event.get("session_id", "")) if prompt else ""
            if block:
                print(block)
        elif name == "Stop":
            remember(event, _root(event))
        elif name == "SessionStart" and semantic_enabled(_root(event)):
            warm_in_background(_root(event))
    except Exception:  # noqa: BLE001 — a memory hook must never fail the session
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
