#!/usr/bin/env python3
"""
scripts/telegram-bot.py — Telegram bot for Prytan.

Routes human messages to the chief-of-staff Claude agent and sends back
the response. Uses only Python stdlib — no pip dependencies.

TOKEN-SAVING DESIGN: The chief-of-staff runs from a lean home directory
(~/.prytan-cs-home/) instead of the project root. This means the full
CLAUDE.md + MEMORY.md (~11K tokens) do NOT auto-load into every chat turn.
The agent's persona symlinks to the real .claude/agents/chief-of-staff.md,
and a `cg` wrapper script lets the agent query the knowledge graph on demand.

Environment variables (set in ~/.prytan.env or export before running):
    TELEGRAM_BOT_TOKEN          Your bot token from @BotFather
    TELEGRAM_ALLOWED_CHAT_ID    Single allowed chat ID (security gate)
    PRYTAN_CHIEF_AGENT          Agent name to invoke (default: chief-of-staff)
    PRYTAN_PROJECT_ROOT         Absolute path to project root (default: cwd)
    PRYTAN_CLAUDE_BIN           Path to claude binary (default: claude)
    PRYTAN_MAX_RESPONSE_LEN     Max chars sent per Telegram message (default: 3800)
    WRITE_MODE                  Set to 1 to allow agent to write files from chat
                                (default: 0 = read-only, safer for remote input)

Setup:
    1. In Telegram, message @BotFather → /newbot → copy the HTTP API token.
    2. Message your new bot once ("hi"), then get your chat id:
       curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -c
           "import sys,json; [print(u['message']['chat']['id'])
            for u in json.load(sys.stdin)['result']]"
    3. Create ~/.prytan.env (chmod 600):
           TELEGRAM_BOT_TOKEN=123456:ABC...
           TELEGRAM_ALLOWED_CHAT_ID=123456789
           # WRITE_MODE=1   # uncomment to allow file writes from chat
    4. Run:
           source ~/.prytan.env && python3 scripts/telegram-bot.py
       Or background:
           nohup source ~/.prytan.env && python3 scripts/telegram-bot.py &

Commands available in chat:
    /start  /help   — usage info
    /status         — ask chief-of-staff for a status update
    /standup        — today's standup digest
    /brief          — daily brief (inbox + open decisions)
    /reset          — start a fresh conversation (clears session continuity)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

BOT_TOKEN           = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_ID     = os.environ.get("TELEGRAM_ALLOWED_CHAT_ID", "")
CHIEF_AGENT         = os.environ.get("PRYTAN_CHIEF_AGENT", "chief-of-staff")
PROJECT_ROOT        = Path(os.environ.get("PRYTAN_PROJECT_ROOT", os.getcwd())).resolve()
CLAUDE_BIN          = os.environ.get("PRYTAN_CLAUDE_BIN", "claude")
MAX_RESPONSE_LEN    = int(os.environ.get("PRYTAN_MAX_RESPONSE_LEN", "3800"))
WRITE_MODE          = os.environ.get("WRITE_MODE", "0").strip() == "1"

POLL_TIMEOUT    = 30    # long-poll seconds
RETRY_DELAY     = 5     # seconds between retries on poll errors
MAX_AGENT_WAIT  = 300   # seconds before timing out an agent call

# Lean home — chief-of-staff runs from here, NOT from PROJECT_ROOT.
# This keeps the full CLAUDE.md + MEMORY.md out of every chat turn.
CS_HOME     = Path.home() / ".prytan-cs-home"
CG_WRAPPER  = CS_HOME / "cg"
CG_GRANT    = f"Bash({CG_WRAPPER} *)"

# Session persistence — conversation continues across bot restarts.
SESSION_PATH = Path.home() / ".prytan-cs-session"

# Conversations are saved here and indexed by codegrapher.
CONV_DIR = PROJECT_ROOT / ".agent-logs" / CHIEF_AGENT / "conversations"

# ──────────────────────────────────────────────
# Tool scoping — read-only by default (safer for remote input)
# Set WRITE_MODE=1 in ~/.prytan.env to allow file writes from chat.
# cg (the graph wrapper) is always granted — querying is read-only.
# ──────────────────────────────────────────────

READONLY_TOOLS = f"Read,Glob,Grep,{CG_GRANT}"
WRITE_TOOLS = (
    f"Read,Write,Edit,Glob,Grep,{CG_GRANT},"
    "Bash(ls *),Bash(cat *),Bash(grep *),Bash(find *),Bash(date *),"
    "Bash(head *),Bash(tail *),Bash(wc *),Bash(mkdir *),Bash(cp *),"
    "Bash(python3 codegrapher.py *),"
    "Bash(git status*),Bash(git log*),Bash(git diff*)"
    # NOTE: deliberately NO Bash(claude *). Letting a remote Telegram message
    # spawn `claude -p` = arbitrary code execution from chat (RCE risk).
    # Agents run via handoffs; live agent runs happen in Claude Code (human-gated).
)

TOOLS = WRITE_TOOLS if WRITE_MODE else READONLY_TOOLS

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────

(PROJECT_ROOT / ".agent-logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(PROJECT_ROOT / ".agent-logs" / "telegram-bot.log")),
    ],
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Lean home setup
# ──────────────────────────────────────────────

def _ensure_cs_home() -> None:
    """Prepare the lean home directory for the chief-of-staff.

    Runs the agent from CS_HOME instead of PROJECT_ROOT so the full CLAUDE.md
    and MEMORY.md do NOT auto-load into every chat turn (saves ~11K tokens/msg).

    Two things make CS_HOME self-sufficient:
      1. A symlink: CS_HOME/.claude/agents/<name>.md → real agent file.
         Single source of truth — no drift, no second copy.
      2. A `cg` wrapper script: cd PROJECT_ROOT && python3 codegrapher.py "$@"
         So the agent can query the org knowledge graph on demand, even though
         its cwd is the lean home, not the project root.
    """
    agents_dir = CS_HOME / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    # Persona symlink
    link   = agents_dir / f"{CHIEF_AGENT}.md"
    target = PROJECT_ROOT / ".claude" / "agents" / f"{CHIEF_AGENT}.md"
    try:
        if link.is_symlink() or link.exists():
            if not (link.is_symlink() and link.resolve() == target.resolve()):
                link.unlink()
                link.symlink_to(target)
        else:
            link.symlink_to(target)
    except OSError as e:
        log.warning("Persona symlink failed: %s", e)

    # cg wrapper
    try:
        CG_WRAPPER.write_text(
            "#!/bin/sh\n"
            "# Prytan knowledge-graph wrapper. Auto-generated by telegram-bot.py.\n"
            f'cd "{PROJECT_ROOT}" && exec python3 codegrapher.py "$@"\n'
        )
        CG_WRAPPER.chmod(0o755)
    except OSError as e:
        log.warning("cg wrapper failed: %s", e)

    log.info("CS home ready at %s (mode: %s)", CS_HOME, "WRITE" if WRITE_MODE else "READ-ONLY")


# ──────────────────────────────────────────────
# Telegram API helpers
# ──────────────────────────────────────────────

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def _tg_request(method: str, params: Dict[str, Any]) -> Optional[dict]:
    url  = f"{BASE_URL}/{method}"
    data = json.dumps(params).encode("utf-8")
    req  = urllib.request.Request(url, data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        log.error("Telegram HTTP %s for %s: %s", e.code, method,
                  e.read().decode("utf-8", errors="replace")[:200])
    except Exception as e:
        log.error("Telegram request error (%s): %s", method, e)
    return None


def get_updates(offset: int) -> List[dict]:
    resp = _tg_request("getUpdates", {
        "offset": offset,
        "timeout": POLL_TIMEOUT,
        "allowed_updates": ["message"],
    })
    return (resp or {}).get("result", []) if (resp or {}).get("ok") else []


def send_message(chat_id: str, text: str) -> None:
    """Send text, chunking if it exceeds Telegram's limit."""
    while text:
        chunk = text[:MAX_RESPONSE_LEN]
        text  = text[MAX_RESPONSE_LEN:]
        _tg_request("sendMessage", {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown",
        })


def send_typing(chat_id: str) -> None:
    _tg_request("sendChatAction", {"chat_id": chat_id, "action": "typing"})


# ──────────────────────────────────────────────
# Session continuity
# ──────────────────────────────────────────────

def _load_session() -> Optional[str]:
    """Return stored session ID, or None."""
    try:
        return SESSION_PATH.read_text().strip() or None
    except OSError:
        return None


def _save_session(session_id: str) -> None:
    try:
        SESSION_PATH.write_text(session_id)
    except OSError as e:
        log.warning("Could not save session: %s", e)


def _clear_session() -> None:
    SESSION_PATH.unlink(missing_ok=True)
    log.info("Session cleared")


# ──────────────────────────────────────────────
# Conversation saving (indexed by codegrapher)
# ──────────────────────────────────────────────

def _conversation_path() -> Path:
    """Path for today's conversation note."""
    CONV_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sid = _load_session()
    sid8 = (sid or "nosession").replace("-", "")[:8]
    return CONV_DIR / f"{day}-{sid8}.md"


def _save_exchange(human_msg: str, agent_reply: str) -> None:
    """Append this exchange to the session's markdown note.

    These notes are indexed by codegrapher as [conversation] nodes, so
    any agent can recall a past exchange with a graph query — no tokens
    spent re-reading whole conversation logs.
    """
    path = _conversation_path()
    ts   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        if not path.exists():
            path.write_text(
                f"---\ntype: conversation\nagent: {CHIEF_AGENT}\ndate: {ts}\n---\n\n"
            )
        with path.open("a") as f:
            f.write(f"\n**Human [{ts}]:** {human_msg}\n\n")
            f.write(f"**{CHIEF_AGENT} [{ts}]:** {agent_reply}\n\n---\n")
    except OSError as e:
        log.warning("Could not save conversation: %s", e)


# ──────────────────────────────────────────────
# Agent invocation
# ──────────────────────────────────────────────

def _build_prompt(user_message: str, reply_to_text: Optional[str] = None) -> str:
    """Build the prompt injected into the agent's context.

    reply_to_text: if the human replied to a specific prior bot message, include
    it as context so the agent knows which response is being addressed.
    Injects pending human decisions so the agent can resolve them from this reply.
    """
    parts = ["[Telegram message from human]\n"]

    if reply_to_text:
        parts.append(
            f"[Human is replying to this prior message from you:]\n"
            f"> {reply_to_text[:600]}\n"
            f"[End of quoted message]\n"
        )

    parts.append(user_message)
    parts.append(
        f"\n\n[Context: project root is {PROJECT_ROOT}. "
        f"Read files via absolute paths or use the `cg` wrapper to query the knowledge graph.]"
    )

    # Inject open decisions — agent can resolve them inline with @@RESOLVE markers
    pending_block = _pending_decisions_block()
    if pending_block:
        parts.append(pending_block)

    parts.append(
        "\n\nRespond helpfully and concisely (max ~3500 chars for Telegram). "
        "If this requires delegating to another agent, write a handoff file "
        f"to {PROJECT_ROOT}/.agent-handoffs/ and tell the human what you've done."
    )
    return "\n".join(parts)


def invoke_agent(user_message: str, reply_to_text: Optional[str] = None) -> str:
    """Invoke the chief-of-staff agent. Runs from CS_HOME (lean, no CLAUDE.md overhead).
    Uses --resume <session_id> for conversation continuity across messages."""
    prompt = _build_prompt(user_message, reply_to_text=reply_to_text)
    session_id = _load_session()

    cmd = [
        CLAUDE_BIN,
        "--agent", CHIEF_AGENT,
        "--print",
        "--allowedTools", TOOLS,
        "--max-turns", "8",
    ]
    if session_id:
        cmd += ["--resume", session_id]

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=MAX_AGENT_WAIT,
            cwd=str(CS_HOME),   # ← lean home, not PROJECT_ROOT
        )
        if result.returncode == 0:
            response = result.stdout.strip()
            # Try to extract session ID from output (claude --print may emit it)
            for line in result.stderr.splitlines():
                if line.startswith("session:"):
                    _save_session(line.split(":", 1)[1].strip())
                    break
            return response or "(Agent returned empty response)"
        else:
            err = result.stderr.strip()[:500]
            log.error("Agent error: %s", err)
            return f"Agent error (check `.agent-logs/telegram-bot.log`): {err[:300]}"
    except subprocess.TimeoutExpired:
        log.error("Agent timed out after %ds", MAX_AGENT_WAIT)
        return f"Timed out after {MAX_AGENT_WAIT}s. Try a shorter question or /reset."
    except FileNotFoundError:
        return f"Claude binary not found at `{CLAUDE_BIN}`. Is Claude Code installed?"
    except Exception as e:
        log.exception("Unexpected error invoking agent")
        return f"Unexpected error: {e}"


# ──────────────────────────────────────────────
# Security gate
# ──────────────────────────────────────────────

def is_allowed(chat_id: Any) -> bool:
    if not ALLOWED_CHAT_ID:
        log.warning("TELEGRAM_ALLOWED_CHAT_ID not set — rejecting all messages")
        return False
    return str(chat_id) == str(ALLOWED_CHAT_ID)


# ──────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────

HELP_TEXT = (
    "*Prytan Agent Bot*\n\n"
    f"Your chief-of-staff agent (`{CHIEF_AGENT}`) is listening.\n"
    "Send any message and it will respond, route, or escalate.\n\n"
    "*Commands:*\n"
    "  /start /help — this message\n"
    "  /status — active priorities and blockers\n"
    "  /standup — today's standup digest\n"
    "  /brief — daily brief (inbox + open decisions)\n"
    "  /reset — start a fresh conversation\n\n"
    f"*Mode:* {'WRITE (agent can edit files)' if WRITE_MODE else 'READ-ONLY (safe default)'}\n"
    f"*Project:* `{PROJECT_ROOT}`"
)


def validate_config() -> bool:
    ok = True
    if not BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN is not set")
        ok = False
    if not ALLOWED_CHAT_ID:
        log.warning("TELEGRAM_ALLOWED_CHAT_ID not set — bot will reject all messages")
    return ok


def main() -> None:
    if not validate_config():
        sys.exit(1)

    _ensure_cs_home()

    log.info("Prytan Telegram bot starting")
    log.info("Chief agent : %s", CHIEF_AGENT)
    log.info("Project root: %s", PROJECT_ROOT)
    log.info("CS home     : %s", CS_HOME)
    log.info("Allowed chat: %s", ALLOWED_CHAT_ID or "(none — all rejected)")
    log.info("Mode        : %s", "WRITE" if WRITE_MODE else "READ-ONLY")

    offset = 0

    while True:
        try:
            updates = get_updates(offset)
        except KeyboardInterrupt:
            log.info("Bot stopped by user")
            break
        except Exception as e:
            log.error("Poll error: %s", e)
            time.sleep(RETRY_DELAY)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            msg  = update.get("message")
            if not msg:
                continue

            chat_id = str(msg["chat"]["id"])
            text    = msg.get("text", "").strip()

            if not text:
                continue

            if not is_allowed(chat_id):
                log.warning("Rejected message from chat_id=%s", chat_id)
                send_message(chat_id, "Access denied.")
                continue

            log.info("Message from chat %s: %s", chat_id, text[:80])
            send_typing(chat_id)

            # ── Built-in commands ──────────────────────
            if text.lower() in ("/start", "/help"):
                send_message(chat_id, HELP_TEXT)
                continue

            if text.lower() == "/reset":
                _clear_session()
                send_message(chat_id, "Conversation reset. Starting fresh.")
                continue

            if text.lower() == "/status":
                text = "Give me a brief status update: active priorities and any open blockers across all pods."

            elif text.lower() == "/standup":
                text = f"Read today's standup digests from {PROJECT_ROOT}/.agent-inbox/ and give me a summary."

            elif text.lower() == "/brief":
                text = (
                    f"Run /daily-brief: read {PROJECT_ROOT}/.agent-inbox/ for latest activity, "
                    f"check open decisions in {PROJECT_ROOT}/.agent-inbox/decisions.jsonl, "
                    "and tell me what's done, in-flight, blocked, and waiting for my decision."
                )

            # ── Reply-to threading ────────────────────
            # If the human replied to a specific bot message, pass the quoted
            # text as context so the agent knows what's being addressed.
            reply_to_text: Optional[str] = None
            if msg.get("reply_to_message"):
                reply_to_text = msg["reply_to_message"].get("text", "")[:600]

            # ── Invoke chief-of-staff ──────────────────
            response = invoke_agent(text, reply_to_text=reply_to_text)

            # ── Strip @@RESOLVE markers, resolve decisions ─
            clean_response, resolved_ids = _apply_resolve_markers(response)
            if resolved_ids:
                log.info("Resolved decisions from reply: %s", resolved_ids)
                # Append a quiet note so human knows decisions were acted on
                note = "\n\n_✓ Resolved: " + ", ".join(resolved_ids) + "_"
                clean_response = clean_response + note

            send_message(chat_id, clean_response)
            _save_exchange(text, clean_response)
            log.info("Sent %d chars to chat %s", len(clean_response), chat_id)


if __name__ == "__main__":
    main()


# ──────────────────────────────────────────────
# @@RESOLVE marker handling
# ──────────────────────────────────────────────
# The chief-of-staff can resolve pending human decisions inline.
# It embeds hidden markers at the END of its reply (the human never sees them):
#   @@RESOLVE: D-2026-06-28-01 :: approve the API redesign
# The bot strips the markers, calls decision_ledger.resolve(), and writes a
# directive handoff to the owning agent so it can act on the decision.

import re as _re
import sys as _sys

_RESOLVE_RE = _re.compile(r"^@@RESOLVE:\s*(\S+)\s*::\s*(.+)$", _re.MULTILINE)

# Ensure scripts/ is on the path so we can import decision_ledger
_scripts_dir = str(PROJECT_ROOT / "scripts")
if _scripts_dir not in _sys.path:
    _sys.path.insert(0, _scripts_dir)


def _apply_resolve_markers(reply: str) -> tuple[str, list]:
    """Strip @@RESOLVE markers from reply, resolve each decision.

    Returns (clean_reply, list_of_resolved_ids).
    Never raises — errors are logged and skipped.
    """
    resolved = []
    matches = list(_RESOLVE_RE.finditer(reply))
    if not matches:
        return reply, resolved

    # Try to import decision_ledger (only present after setup)
    try:
        import importlib, decision_ledger as dl
    except ImportError:
        log.warning("decision_ledger not found — @@RESOLVE markers ignored")
        clean = _RESOLVE_RE.sub("", reply).strip()
        return clean, resolved

    handoffs_dir = PROJECT_ROOT / ".agent-handoffs"
    handoffs_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)

    for m in matches:
        dec_id, answer = m.group(1).strip(), m.group(2).strip()
        try:
            dl.resolve_decision(dec_id, answer, resolved_by="human",
                                ledger=PROJECT_ROOT / ".agent-inbox" / "decisions.jsonl")
            # Write a directive handoff so the owning agent picks up the answer
            fname = f"{now.strftime('%Y-%m-%d')}-human-directive-{dec_id}.md"
            (handoffs_dir / fname).write_text(
                f"# Human directive — {dec_id}\n\n"
                f"**Decision:** {dec_id}\n"
                f"**Answer:** {answer}\n"
                f"**Resolved:** {now.isoformat()} by human\n\n"
                f"Act on this at the next pod run.\n"
            )
            resolved.append(dec_id)
            log.info("Resolved decision %s: %s", dec_id, answer[:60])
        except Exception as e:
            log.warning("Could not resolve %s: %s", dec_id, e)

    clean = _RESOLVE_RE.sub("", reply).strip()
    return clean, resolved


def _pending_decisions_block() -> str:
    """Return a block listing open awaiting_human decisions for injection into the prompt.

    If none are pending, returns empty string (zero token cost).
    """
    try:
        import decision_ledger as dl
        pending = dl.list_decisions(
            status="awaiting_human",
            ledger=PROJECT_ROOT / ".agent-inbox" / "decisions.jsonl",
        )
    except Exception:
        return ""

    if not pending:
        return ""

    lines = [
        "\n\n## Open decisions awaiting human response",
        "When the human's reply clearly answers one of these, add at the END of your response",
        "(the human never sees this line — the bot strips it before sending):",
        "@@RESOLVE: <id> :: <their answer in a few words>",
        "Use the EXACT id in brackets. If the reply is ambiguous, ask ONE clarifying question instead.",
        "Never guess — a @@RESOLVE marker resolves the decision permanently.\n",
    ]
    for r in pending[:10]:  # cap at 10 to keep prompt lean
        rec_text = f" (you recommended: {r['recommendation']})" if r.get("recommendation") else ""
        lines.append(f"  [{r['id']}] {r['title']}{rec_text}")

    return "\n".join(lines)
