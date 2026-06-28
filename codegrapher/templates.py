"""
codegrapher/templates.py — prompt injection templates for hooks.

Used by:
  - codegrapher_hook.py (PreToolUse: query reminder)
  - .claude/hooks/codegrapher-memo.py (UserPromptSubmit: memory injection)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────
# Query reminder (injected before Grep/Glob/Read)
# ──────────────────────────────────────────────

QUERY_REMINDER = """
---
**[Codegrapher] Check the knowledge graph before searching files.**

Run one of:
```bash
python3 codegrapher.py query "<topic or symbol>"   # ranked search
python3 codegrapher.py explain "<symbol>"           # symbol + edges
python3 codegrapher.py path "<a>" "<b>"             # connection path
```

If the graph returns a relevant file path, read only that file.
Only use Grep/Glob/Read for things not in the graph.
---
""".strip()


# ──────────────────────────────────────────────
# Memory header
# ──────────────────────────────────────────────

MEMORY_HEADER = "## [Prytan] Relevant past context auto-recalled"

MEMORY_FOOTER = """
---
*Auto-injected by codegrapher-memo hook. Relevance ranked by query match + recency.*
""".strip()


# ──────────────────────────────────────────────
# Formatters
# ──────────────────────────────────────────────

def format_memory_block(
    memories: List[Dict[str, Any]],
    query: str = "",
    max_snippet: int = 300,
) -> str:
    """
    Format a list of memory dicts into a markdown block for prompt injection.

    Each memory dict should have keys: agent, ts, snippet, tags, source.
    """
    if not memories:
        return ""

    lines = [MEMORY_HEADER]
    if query:
        lines.append(f"*(query: `{query[:100]}`)*")
    lines.append("")

    for i, mem in enumerate(memories, 1):
        agent = mem.get("agent", "unknown")
        source = mem.get("source", "?")
        snippet = (mem.get("snippet") or "").strip()[:max_snippet]
        tags = mem.get("tags") or []
        ts = mem.get("ts") or 0

        date_str = ""
        if ts:
            try:
                from datetime import datetime, timezone
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                date_str = f" · {dt.strftime('%Y-%m-%d')}"
            except Exception:
                pass

        tag_str = f" · tags: {', '.join(tags[:5])}" if tags else ""
        lines.append(f"### Memory {i} — `{agent}`{date_str}{tag_str}")

        if snippet:
            # Indent snippet as blockquote
            for line in snippet.splitlines():
                lines.append(f"> {line}")
        lines.append("")

    lines.append(MEMORY_FOOTER)
    return "\n".join(lines)


def format_graph_hit_block(hits: List[Any], query: str = "") -> str:
    """
    Format codegrapher query results (list of (score, Node)) as a
    brief markdown summary for the QUERY_REMINDER follow-up.
    """
    if not hits:
        return f"No graph results for `{query}`."

    lines = [f"**Graph results for `{query}`:**", ""]
    for score, node in hits[:8]:
        loc = f"`{node.file}:{node.line}`" if node.file and node.line else (f"`{node.file}`" if node.file else "")
        kind = node.kind
        lines.append(f"- **{node.label}** ({kind}) {loc} — score {score:.1f}")
    return "\n".join(lines)
