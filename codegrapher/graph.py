"""
codegrapher/graph.py — Node, Edge, and Graph data model with JSON persistence.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────

@dataclass
class Node:
    """A vertex in the knowledge graph."""

    id: str                          # Unique identifier (e.g. "src/app.py::MyClass")
    kind: str                        # "symbol", "file", "page", "conversation", "agent-log"
    label: str                       # Human-readable name
    file: Optional[str] = None       # Absolute or relative file path
    line: Optional[int] = None       # Line number (for symbols)
    tags: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Node":
        return cls(**d)


@dataclass
class Edge:
    """A directed relationship between two nodes."""

    src: str          # Node.id of source
    dst: str          # Node.id of destination
    rel: str          # Relationship type: "imports", "calls", "defines", "explains", "contains", "handoff"
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Edge":
        return cls(**d)


class Graph:
    """
    In-memory knowledge graph with JSON persistence.

    Usage:
        g = Graph.load("codegrapher_out/graph.json")
        g.add_node(Node(id="x", kind="symbol", label="x"))
        g.save()
    """

    DEFAULT_PATH = "codegrapher_out/graph.json"

    def __init__(self, path: str = DEFAULT_PATH):
        self.path = Path(path)
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self._meta: Dict[str, Any] = {
            "version": 1,
            "created_at": time.time(),
            "updated_at": time.time(),
        }

    # ── Mutation ──

    def add_node(self, node: Node, overwrite: bool = True) -> None:
        if not overwrite and node.id in self.nodes:
            return
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        # Deduplicate
        for e in self.edges:
            if e.src == edge.src and e.dst == edge.dst and e.rel == edge.rel:
                return
        self.edges.append(edge)

    def remove_node(self, node_id: str) -> None:
        self.nodes.pop(node_id, None)
        self.edges = [e for e in self.edges if e.src != node_id and e.dst != node_id]

    def clear_kind(self, kind: str) -> None:
        """Remove all nodes of a given kind (and their edges)."""
        ids = {nid for nid, n in self.nodes.items() if n.kind == kind}
        for nid in ids:
            self.remove_node(nid)

    # ── Query helpers ──

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def neighbors(self, node_id: str, rel: Optional[str] = None) -> List[Node]:
        """Return nodes reachable from node_id via outgoing edges."""
        result = []
        for e in self.edges:
            if e.src == node_id and (rel is None or e.rel == rel):
                n = self.nodes.get(e.dst)
                if n:
                    result.append(n)
        return result

    def incoming(self, node_id: str, rel: Optional[str] = None) -> List[Node]:
        """Return nodes that point TO node_id."""
        result = []
        for e in self.edges:
            if e.dst == node_id and (rel is None or e.rel == rel):
                n = self.nodes.get(e.src)
                if n:
                    result.append(n)
        return result

    def edges_from(self, node_id: str) -> List[Edge]:
        return [e for e in self.edges if e.src == node_id]

    def edges_to(self, node_id: str) -> List[Edge]:
        return [e for e in self.edges if e.dst == node_id]

    # ── Persistence ──

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._meta["updated_at"] = time.time()
        data = {
            "meta": self._meta,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.path)

    @classmethod
    def load(cls, path: str = DEFAULT_PATH) -> "Graph":
        g = cls(path)
        p = Path(path)
        if not p.exists():
            return g
        try:
            data = json.loads(p.read_text())
            g._meta = data.get("meta", g._meta)
            for nd in data.get("nodes", []):
                g.nodes[nd["id"]] = Node.from_dict(nd)
            for ed in data.get("edges", []):
                g.edges.append(Edge.from_dict(ed))
        except (json.JSONDecodeError, KeyError) as exc:
            print(f"[codegrapher] Warning: could not load graph ({exc}). Starting fresh.")
        return g

    # ── Stats ──

    def stats(self) -> Dict[str, Any]:
        kind_counts: Dict[str, int] = {}
        for n in self.nodes.values():
            kind_counts[n.kind] = kind_counts.get(n.kind, 0) + 1
        rel_counts: Dict[str, int] = {}
        for e in self.edges:
            rel_counts[e.rel] = rel_counts.get(e.rel, 0) + 1
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "nodes_by_kind": kind_counts,
            "edges_by_rel": rel_counts,
            "updated_at": self._meta.get("updated_at"),
        }
