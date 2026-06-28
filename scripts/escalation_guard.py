#!/usr/bin/env python3
"""
escalation_guard.py — Deterministic backstop for agent permission-escalation confabulation.

Prompt guards alone don't hold: an agent can be told never to ask the human to widen
write permissions, and still override that in production. Since instructions alone
don't hold, the bot enforces it: before the agent's reply reaches the human, the bot
checks ESCALATION_RE — if it matches, the reply is NEVER relayed.

Two confabulation shapes are covered:
  (1) the settings.json / Write-glob permission ask
  (2) the "Allow-button" variant — the agent inventing a Claude Code UI / approval
      prompt for the human to click, which does not exist over Telegram.

Pure stdlib (re). No heavy imports, so this is unit-testable without the Claude SDK.
"""
import re

# Matches the ACT of asking to widen write permission (not mere mentions).
ESCALATION_RE = re.compile(
    r"Write\(/"                         # Write(/abs/...**) glob
    r"|Edit\(/"                         # Edit(/abs/...**) glob
    r"|permissions\.allow"              # the settings key
    r"|--dangerously"                   # --dangerously-skip-permissions
    r"|chmod"
    r"|(?:add|edit).{0,25}settings\.json"
    r"|(?:open|enable).{0,15}write"
    # "Allow-button" confabulation: agent invents a Claude Code UI approval prompt.
    # No such UI exists over Telegram — same backstop, never relay it.
    r"|(?:click|press|tap|ללחוץ|לחיצה)(?:\s+(?:on|על))?\W{0,3}allow"
    r"|allow\s*(?:button|כפתור)"
    r"|claude\s*code.{0,12}ui"
    r"|(?:approval|אישור)\s*(?:prompt|dialog|pop-?up)"
    r"|inline\s*prompt",
    re.IGNORECASE,
)


def caught(reply: str) -> bool:
    """True if the agent's reply is a permission-escalation ask that must NOT be relayed."""
    return bool(reply) and bool(ESCALATION_RE.search(reply))
