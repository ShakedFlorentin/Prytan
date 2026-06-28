"""
codegrapher/cache.py — incremental scanner with mtime cache.

Indexes:
  - Python (.py): functions, classes, methods
  - JavaScript / TypeScript (.js, .ts, .jsx, .tsx): functions, classes, arrow functions
  - Go (.go): functions, structs, interfaces
  - Markdown (.md): H1/H2 headings, `explains:` frontmatter links to code

The cache stores per-file mtime so unchanged files are skipped on re-scan.
"""

from __future__ import annotations

import ast
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .graph import Edge, Graph, Node


CACHE_PATH = "codegrapher_out/scan_cache.json"

# File extensions this scanner handles
PYTHON_EXT = {".py"}
JS_EXT = {".js", ".ts", ".jsx", ".tsx"}
GO_EXT = {".go"}
MD_EXT = {".md"}
ALL_EXT = PYTHON_EXT | JS_EXT | GO_EXT | MD_EXT


# ──────────────────────────────────────────────
# Cache helpers
# ──────────────────────────────────────────────

def _load_cache(cache_path: str = CACHE_PATH) -> Dict[str, float]:
    """Return {file_path: mtime} from the cache file."""
    p = Path(cache_path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: Dict[str, float], cache_path: str = CACHE_PATH) -> None:
    p = Path(cache_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cache, indent=2))


# ──────────────────────────────────────────────
# Python scanner
# ──────────────────────────────────────────────

def _scan_python(file_path: Path, graph: Graph) -> List[Node]:
    """Extract functions and classes from a Python file using ast."""
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    nodes = []
    rel = str(file_path)

    # File node
    file_node = Node(
        id=f"file::{rel}",
        kind="file",
        label=file_path.name,
        file=rel,
        tags=["python"],
    )
    graph.add_node(file_node)
    nodes.append(file_node)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nid = f"{rel}::{node.name}"
            n = Node(
                id=nid,
                kind="symbol",
                label=node.name,
                file=rel,
                line=node.lineno,
                tags=["python", "function"],
            )
            graph.add_node(n)
            graph.add_edge(Edge(src=file_node.id, dst=nid, rel="defines"))
            nodes.append(n)
        elif isinstance(node, ast.ClassDef):
            nid = f"{rel}::{node.name}"
            n = Node(
                id=nid,
                kind="symbol",
                label=node.name,
                file=rel,
                line=node.lineno,
                tags=["python", "class"],
            )
            graph.add_node(n)
            graph.add_edge(Edge(src=file_node.id, dst=nid, rel="defines"))
            nodes.append(n)
            # Methods
            for child in ast.walk(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    mnid = f"{rel}::{node.name}.{child.name}"
                    mn = Node(
                        id=mnid,
                        kind="symbol",
                        label=f"{node.name}.{child.name}",
                        file=rel,
                        line=child.lineno,
                        tags=["python", "method"],
                    )
                    graph.add_node(mn)
                    graph.add_edge(Edge(src=nid, dst=mnid, rel="defines"))
                    nodes.append(mn)

    return nodes


# ──────────────────────────────────────────────
# JS/TS scanner (regex-based)
# ──────────────────────────────────────────────

_JS_PATTERNS = [
    # function declarations
    re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)", re.M),
    # class declarations
    re.compile(r"^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)", re.M),
    # arrow function assignments: const foo = async (...) =>
    re.compile(r"^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(", re.M),
]


def _scan_js(file_path: Path, graph: Graph) -> List[Node]:
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel = str(file_path)
    ext = file_path.suffix.lstrip(".")
    file_node = Node(
        id=f"file::{rel}",
        kind="file",
        label=file_path.name,
        file=rel,
        tags=[ext],
    )
    graph.add_node(file_node)
    nodes = [file_node]

    seen = set()
    for pat in _JS_PATTERNS:
        for m in pat.finditer(source):
            name = m.group(1)
            if name in seen:
                continue
            seen.add(name)
            line = source[: m.start()].count("\n") + 1
            nid = f"{rel}::{name}"
            n = Node(
                id=nid,
                kind="symbol",
                label=name,
                file=rel,
                line=line,
                tags=[ext, "symbol"],
            )
            graph.add_node(n)
            graph.add_edge(Edge(src=file_node.id, dst=nid, rel="defines"))
            nodes.append(n)

    return nodes


# ──────────────────────────────────────────────
# Go scanner (regex-based)
# ──────────────────────────────────────────────

_GO_FUNC = re.compile(r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(", re.M)
_GO_STRUCT = re.compile(r"^type\s+(\w+)\s+struct", re.M)
_GO_INTERFACE = re.compile(r"^type\s+(\w+)\s+interface", re.M)


def _scan_go(file_path: Path, graph: Graph) -> List[Node]:
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel = str(file_path)
    file_node = Node(
        id=f"file::{rel}",
        kind="file",
        label=file_path.name,
        file=rel,
        tags=["go"],
    )
    graph.add_node(file_node)
    nodes = [file_node]

    for pat, tag in [(_GO_FUNC, "function"), (_GO_STRUCT, "struct"), (_GO_INTERFACE, "interface")]:
        for m in pat.finditer(source):
            name = m.group(1)
            line = source[: m.start()].count("\n") + 1
            nid = f"{rel}::{name}"
            n = Node(
                id=nid,
                kind="symbol",
                label=name,
                file=rel,
                line=line,
                tags=["go", tag],
            )
            graph.add_node(n)
            graph.add_edge(Edge(src=file_node.id, dst=nid, rel="defines"))
            nodes.append(n)

    return nodes


# ──────────────────────────────────────────────
# Markdown scanner
# ──────────────────────────────────────────────

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_EXPLAINS = re.compile(r"^explains:\s*(.+)$", re.M)
_HEADING = re.compile(r"^(#{1,3})\s+(.+)$", re.M)


def _scan_markdown(file_path: Path, graph: Graph) -> List[Node]:
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel = str(file_path)
    nodes = []

    # Extract title from first H1
    h1_match = re.search(r"^#\s+(.+)$", source, re.M)
    title = h1_match.group(1).strip() if h1_match else file_path.stem

    # Parse frontmatter for `explains:` links
    explains_targets = []
    fm_match = _FRONTMATTER.match(source)
    if fm_match:
        fm_text = fm_match.group(1)
        for em in _EXPLAINS.finditer(fm_text):
            explains_targets.append(em.group(1).strip())

    # Page node
    page_node = Node(
        id=f"page::{rel}",
        kind="page",
        label=title,
        file=rel,
        tags=["markdown"],
        meta={"explains": explains_targets},
    )
    graph.add_node(page_node)
    nodes.append(page_node)

    # Heading nodes
    for m in _HEADING.finditer(source):
        level = len(m.group(1))
        heading = m.group(2).strip()
        line = source[: m.start()].count("\n") + 1
        hnid = f"page::{rel}::h{level}::{heading}"
        hn = Node(
            id=hnid,
            kind="page",
            label=heading,
            file=rel,
            line=line,
            tags=["markdown", f"h{level}"],
        )
        graph.add_node(hn)
        graph.add_edge(Edge(src=page_node.id, dst=hnid, rel="contains"))
        nodes.append(hn)

    # Add explains edges (dst is looked up after full scan)
    for target in explains_targets:
        page_node.meta.setdefault("_pending_explains", []).append(target)

    return nodes


def _resolve_explains_edges(graph: Graph) -> None:
    """
    After scanning all files, resolve pending `explains` edges from
    markdown pages to code symbols.
    """
    for node in list(graph.nodes.values()):
        targets = node.meta.get("_pending_explains", [])
        for target in targets:
            # Try exact ID first
            if target in graph.nodes:
                graph.add_edge(Edge(src=node.id, dst=target, rel="explains"))
            else:
                # Try label match
                from .query import query_graph
                hits = query_graph(graph, target, top_n=1, kinds=["symbol", "file"])
                if hits:
                    _, matched = hits[0]
                    graph.add_edge(Edge(src=node.id, dst=matched.id, rel="explains"))
        if "_pending_explains" in node.meta:
            del node.meta["_pending_explains"]


# ──────────────────────────────────────────────
# Main scan entry point
# ──────────────────────────────────────────────

def scan_directory(
    directory: str,
    graph: Graph,
    cache_path: str = CACHE_PATH,
    force: bool = False,
) -> Tuple[int, int]:
    """
    Scan a directory tree, indexing source files into graph.

    Uses mtime cache for incremental updates — only changed files are re-indexed.

    Returns (files_scanned, files_skipped).
    """
    root = Path(directory).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {root}")

    cache = {} if force else _load_cache(cache_path)
    new_cache: Dict[str, float] = dict(cache)

    scanned = 0
    skipped = 0

    for file_path in root.rglob("*"):
        if file_path.suffix not in ALL_EXT:
            continue
        if any(part.startswith(".") and part not in (".claude",) for part in file_path.parts):
            continue
        if "node_modules" in file_path.parts or "__pycache__" in file_path.parts:
            continue

        rel = str(file_path)
        mtime = file_path.stat().st_mtime

        if not force and cache.get(rel) == mtime:
            skipped += 1
            continue

        # Re-index this file: remove stale nodes first
        stale_ids = [
            nid for nid, n in graph.nodes.items()
            if n.file == rel
        ]
        for nid in stale_ids:
            graph.remove_node(nid)

        # Scan by type
        if file_path.suffix in PYTHON_EXT:
            _scan_python(file_path, graph)
        elif file_path.suffix in JS_EXT:
            _scan_js(file_path, graph)
        elif file_path.suffix in GO_EXT:
            _scan_go(file_path, graph)
        elif file_path.suffix in MD_EXT:
            _scan_markdown(file_path, graph)

        new_cache[rel] = mtime
        scanned += 1

    _resolve_explains_edges(graph)
    _save_cache(new_cache, cache_path)
    return scanned, skipped
