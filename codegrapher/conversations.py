"""
codegrapher/conversations.py — conversation storage and relevant-memory retrieval.

Stores conversation snippets as JSON Lines in .agent-logs/conversations.jsonl.
get_relevant_memories() returns the top-N most relevant past entries for a query.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .graph import Graph
from .query import query_graph


CONVERSATIONS_FILE = ".agent-logs/conversations.jsonl"
MAX_SNIPPET_LEN = 500


# ──────────────────────────────────────────────
# Storage
# ──────────────────────────────────────────────

def store_conversation(
    agent: str,
    prompt: str,
    response: str,
    tags: Optional[List[str]] = None,
    conversations_file: str = CONVERSATIONS_FILE,
) -> None:
    """
    Append a conversation record to the JSONL store.

    Args:
        agent:    Name of the agent that produced the response.
        prompt:   The human prompt (or a summary of it).
        response: The agent response (or a summary).
        tags:     Optional list of topic tags for better retrieval.
    """
    p = Path(conversations_file)
    p.parent.mkdir(parents=True, exist_ok=True)

    record: Dict[str, Any] = {
        "ts": time.time(),
        "agent": agent,
        "prompt_snippet": prompt[:MAX_SNIPPET_LEN],
        "response_snippet": response[:MAX_SNIPPET_LEN],
        "tags": tags or [],
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def load_conversations(
    conversations_file: str = CONVERSATIONS_FILE,
    max_records: int = 2000,
) -> List[Dict[str, Any]]:
    """
    Load conversation records from JSONL store.

    Returns up to max_records, most recent first.
    """
    p = Path(conversations_file)
    if not p.exists():
        return []

    records = []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
        for line in lines[-max_records:]:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass

    return list(reversed(records))  # most recent first


# ──────────────────────────────────────────────
# Retrieval
# ──────────────────────────────────────────────

def _score_record(record: Dict[str, Any], tokens: List[str]) -> float:
    """Score a conversation record against query tokens."""
    import re
    text = " ".join([
        record.get("prompt_snippet", ""),
        record.get("response_snippet", ""),
        " ".join(record.get("tags", [])),
        record.get("agent", ""),
    ]).lower()

    score = 0.0
    for tok in tokens:
        tok_l = tok.lower()
        count = text.count(tok_l)
        score += count * 1.0

    # Recency bonus: decay over 30 days
    age_days = (time.time() - record.get("ts", 0)) / 86400
    recency = max(0.0, 1.0 - age_days / 30.0)
    score *= (1.0 + 0.5 * recency)

    return score


def get_relevant_memories(
    query: str,
    graph: Optional[Graph] = None,
    top_n: int = 5,
    conversations_file: str = CONVERSATIONS_FILE,
    include_graph_hits: bool = True,
) -> List[Dict[str, Any]]:
    """
    Return the top-N most relevant memories for a query.

    Searches:
    1. Conversation JSONL store (recency-weighted)
    2. Graph nodes of kind agent-log (if graph provided)

    Returns list of dicts with keys:
        source, agent, ts, snippet, tags, score
    """
    import re
    tokens = re.split(r"[\s_\-./]+", query.strip())
    tokens = [t for t in tokens if len(t) > 2]

    results = []

    # ── Source 1: conversation store ──
    for record in load_conversations(conversations_file):
        s = _score_record(record, tokens)
        if s > 0:
            results.append({
                "source": "conversation",
                "agent": record.get("agent", "?"),
                "ts": record.get("ts", 0),
                "snippet": record.get("response_snippet", ""),
                "prompt": record.get("prompt_snippet", ""),
                "tags": record.get("tags", []),
                "score": s,
            })

    # ── Source 2: graph agent-log nodes ──
    if include_graph_hits and graph is not None:
        hits = query_graph(graph, query, top_n=top_n * 2, kinds=["agent-log"])
        for score, node in hits:
            results.append({
                "source": "graph",
                "agent": node.meta.get("agent", "?"),
                "ts": 0,
                "snippet": node.meta.get("snippet", ""),
                "prompt": "",
                "tags": node.tags,
                "score": score,
                "file": node.file,
            })

    results.sort(key=lambda x: -x["score"])
    return results[:top_n]


def format_memories_for_prompt(
    memories: List[Dict[str, Any]],
    header: str = "## Relevant past context",
) -> str:
    """
    Format retrieved memories as a markdown block suitable for injection
    into an agent prompt.
    """
    if not memories:
        return ""

    lines = [header, ""]
    for i, mem in enumerate(memories, 1):
        agent = mem.get("agent", "?")
        source = mem.get("source", "?")
        snippet = mem.get("snippet", "").strip()
        tags = ", ".join(mem.get("tags", []))
        ts = mem.get("ts", 0)

        if ts:
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            date_str = f" ({dt})"
        else:
            date_str = ""

        lines.append(f"**Memory {i}** — agent: `{agent}`{date_str}, source: {source}")
        if tags:
            lines.append(f"  Tags: {tags}")
        if snippet:
            lines.append(f"  > {snippet[:300]}")
        lines.append("")

    return "\n".join(lines)
