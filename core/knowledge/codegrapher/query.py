from __future__ import annotations
import json
from pathlib import Path


def load_graph(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def query_graph(graph: dict, term: str, limit: int = 10) -> list[dict]:
    t = term.lower()
    scored = []
    for node in graph.get("nodes", []):
        score = 0
        if t in node.get("name", "").lower():
            score += 3
        if t in node.get("id", "").lower():
            score += 2
        if t in node.get("doc", "").lower():
            score += 1
        if score:
            scored.append((score, node))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return [n for _, n in scored[:limit]]
