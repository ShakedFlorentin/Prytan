"""
codegrapher/agents.py — indexes .agent-logs/ conversation and digest files into the graph.

Each log file becomes a node of kind="agent-log". The file content is also
checked for agent-name mentions so cross-agent handoff edges can be inferred.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from .graph import Edge, Graph, Node


_AGENT_REF = re.compile(r"\b([a-z][a-z0-9-]+)(?:\s+agent)?\b", re.I)


def scan_agent_logs(
    logs_dir: str,
    graph: Graph,
    force: bool = False,
) -> int:
    """
    Scan .agent-logs/ and .agent-inbox/ for digest files.

    Creates one node per file. Infers handoff edges where one agent
    references another in the same log.

    Returns count of files indexed.
    """
    root = Path(logs_dir)
    if not root.exists():
        return 0

    # Collect known agent names from .claude/agents/
    agent_dir = Path(".claude/agents")
    known_agents: set[str] = set()
    if agent_dir.exists():
        for f in agent_dir.glob("*.md"):
            known_agents.add(f.stem.lower())

    count = 0
    for file_path in root.rglob("*.md"):
        rel = str(file_path)
        nid = f"agent-log::{rel}"

        # Skip if already indexed (unless force)
        if not force and nid in graph.nodes:
            continue

        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Derive agent name from filename heuristic
        stem = file_path.stem  # e.g. "backend-20240101" or "standup-20240101"
        agent_guess = stem.split("-")[0] if "-" in stem else stem

        node = Node(
            id=nid,
            kind="agent-log",
            label=file_path.name,
            file=rel,
            tags=["agent-log", agent_guess],
            meta={
                "agent": agent_guess,
                "date": _extract_date(stem),
                "snippet": text[:300],
            },
        )
        graph.add_node(node)
        count += 1

        # Infer handoff edges to mentioned agents
        for m in _AGENT_REF.finditer(text):
            mentioned = m.group(1).lower()
            if mentioned in known_agents and mentioned != agent_guess:
                # Find or create a lightweight agent node
                agent_nid = f"agent::{mentioned}"
                if agent_nid not in graph.nodes:
                    graph.add_node(Node(
                        id=agent_nid,
                        kind="agent",
                        label=mentioned,
                        tags=["agent"],
                    ))
                graph.add_edge(Edge(src=nid, dst=agent_nid, rel="handoff"))

    return count


def _extract_date(stem: str) -> str:
    """Extract YYYYMMDD or YYYY-MM-DD from a file stem."""
    m = re.search(r"(\d{4}[\-_]?\d{2}[\-_]?\d{2})", stem)
    return m.group(1) if m else ""
