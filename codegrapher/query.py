"""
codegrapher/query.py — ranked search and shortest-path over the graph.
"""

from __future__ import annotations

import re
from collections import deque
from typing import List, Optional, Tuple

from .graph import Graph, Node


# ──────────────────────────────────────────────
# Ranked full-text search
# ──────────────────────────────────────────────

def _score(node: Node, tokens: List[str]) -> float:
    """
    Score a node against a list of query tokens.
    Higher = more relevant.

    Scoring factors (additive):
      - Exact label match (case-insensitive): +10
      - Token appears in label: +3 each
      - Token appears in tags: +2 each
      - Token appears in file path: +1 each
      - Token appears in meta values (stringified): +0.5 each
    """
    score = 0.0
    label_lower = node.label.lower()
    file_lower = (node.file or "").lower()
    tags_lower = [t.lower() for t in node.tags]
    meta_str = " ".join(str(v) for v in node.meta.values()).lower()

    joined = " ".join(tokens).lower()
    if label_lower == joined:
        score += 10.0

    for tok in tokens:
        tok_l = tok.lower()
        if tok_l in label_lower:
            score += 3.0
        for tag in tags_lower:
            if tok_l in tag:
                score += 2.0
        if tok_l in file_lower:
            score += 1.0
        if tok_l in meta_str:
            score += 0.5

    return score


def query_graph(
    graph: Graph,
    query: str,
    top_n: int = 10,
    kinds: Optional[List[str]] = None,
) -> List[Tuple[float, Node]]:
    """
    Search the graph for nodes matching query.

    Returns list of (score, Node) sorted descending by score.
    Only nodes with score > 0 are returned.

    Args:
        graph:  The loaded Graph instance.
        query:  Free-text query string.
        top_n:  Maximum results to return.
        kinds:  If provided, restrict to nodes of these kinds.
    """
    tokens = re.split(r"[\s_\-./]+", query.strip())
    tokens = [t for t in tokens if t]

    results = []
    for node in graph.nodes.values():
        if kinds and node.kind not in kinds:
            continue
        s = _score(node, tokens)
        if s > 0:
            results.append((s, node))

    results.sort(key=lambda x: (-x[0], x[1].label))
    return results[:top_n]


# ──────────────────────────────────────────────
# Shortest path (BFS, undirected)
# ──────────────────────────────────────────────

def shortest_path(
    graph: Graph,
    src_id: str,
    dst_id: str,
    max_depth: int = 6,
) -> Optional[List[str]]:
    """
    Find the shortest path between two node IDs using BFS.
    Edges are treated as undirected (both directions searched).

    Returns list of node IDs from src to dst, or None if no path found.
    """
    if src_id not in graph.nodes or dst_id not in graph.nodes:
        return None
    if src_id == dst_id:
        return [src_id]

    # Build adjacency (undirected)
    adj: dict[str, set[str]] = {nid: set() for nid in graph.nodes}
    for e in graph.edges:
        if e.src in adj and e.dst in adj:
            adj[e.src].add(e.dst)
            adj[e.dst].add(e.src)

    visited = {src_id}
    queue: deque[List[str]] = deque([[src_id]])

    while queue:
        path = queue.popleft()
        if len(path) > max_depth:
            break
        current = path[-1]
        for neighbor in adj.get(current, []):
            if neighbor == dst_id:
                return path + [dst_id]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(path + [neighbor])

    return None


# ──────────────────────────────────────────────
# Explain: return a node and its immediate edges
# ──────────────────────────────────────────────

def explain_node(graph: Graph, query: str) -> Optional[Tuple[Node, dict]]:
    """
    Find best-matching node for query and return it with its edge context.

    Returns (node, {"outgoing": [...], "incoming": [...]}) or None.
    """
    hits = query_graph(graph, query, top_n=1)
    if not hits:
        return None
    _, node = hits[0]

    out_edges = graph.edges_from(node.id)
    in_edges = graph.edges_to(node.id)

    def edge_summary(edges, direction: str):
        result = []
        for e in edges:
            other_id = e.dst if direction == "out" else e.src
            other = graph.nodes.get(other_id)
            result.append({
                "rel": e.rel,
                "node_id": other_id,
                "label": other.label if other else other_id,
                "kind": other.kind if other else "?",
                "file": other.file if other else None,
            })
        return result

    return node, {
        "outgoing": edge_summary(out_edges, "out"),
        "incoming": edge_summary(in_edges, "in"),
    }
