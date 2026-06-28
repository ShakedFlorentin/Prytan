#!/usr/bin/env python3
"""
.claude/hooks/codegrapher-memo.py — UserPromptSubmit + SessionStart hook.

Auto-injects relevant memories from .agent-logs/ into the beginning of every
Claude Code session/prompt, so agents carry forward institutional knowledge
without manual copy-paste.

Hook protocol:
  - stdin: JSON with keys: prompt, session_id, hook_event_name, ...
  - stdout: JSON with modified_prompt (or empty to pass through unchanged)
  - Exit 0 always (never block)

The injected block is prepended to the user prompt, separated by a horizontal rule.
It is kept short (top 3 memories, 250 chars each) to minimize token cost.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Resolve project root (two levels up from this hook file)
HOOK_FILE = Path(__file__).resolve()
PROJECT_ROOT = HOOK_FILE.parent.parent.parent

sys.path.insert(0, str(PROJECT_ROOT))


MAX_MEMORIES = 3
MAX_SNIPPET = 250
MIN_SCORE = 0.5   # Only inject if at least one memory scores above this


def load_memories(query: str):
    """Load and score relevant memories. Returns [] on any error."""
    try:
        from codegrapher.conversations import get_relevant_memories
        from codegrapher.graph import Graph

        graph_path = PROJECT_ROOT / "codegrapher_out" / "graph.json"
        g = Graph.load(str(graph_path)) if graph_path.exists() else None

        return get_relevant_memories(
            query=query,
            graph=g,
            top_n=MAX_MEMORIES,
            conversations_file=str(PROJECT_ROOT / ".agent-logs" / "conversations.jsonl"),
            include_graph_hits=(g is not None),
        )
    except Exception:
        return []


def format_block(memories: list, query: str) -> str:
    from codegrapher.templates import format_memory_block
    return format_memory_block(memories, query=query, max_snippet=MAX_SNIPPET)


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
    except Exception:
        print(json.dumps({}))
        return

    hook_event = payload.get("hook_event_name", "")
    prompt = payload.get("prompt", "")

    # Only act on UserPromptSubmit and SessionStart
    if hook_event not in ("UserPromptSubmit", "SessionStart", ""):
        print(json.dumps({}))
        return

    if not prompt or len(prompt.strip()) < 5:
        print(json.dumps({}))
        return

    # Use first 200 chars of prompt as the memory query
    query = prompt.strip()[:200]

    memories = load_memories(query)

    # Filter below threshold
    memories = [m for m in memories if m.get("score", 0) >= MIN_SCORE]

    if not memories:
        print(json.dumps({}))
        return

    try:
        block = format_block(memories, query)
    except Exception:
        print(json.dumps({}))
        return

    if not block:
        print(json.dumps({}))
        return

    modified_prompt = block + "\n\n---\n\n" + prompt

    print(json.dumps({"modified_prompt": modified_prompt}))


if __name__ == "__main__":
    main()
