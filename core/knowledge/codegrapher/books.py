from __future__ import annotations
import re
from pathlib import Path
import yaml

_FM = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a leading `---\\n...\\n---` YAML block from the body.
    Returns ({}, text) when there is no frontmatter."""
    m = _FM.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, m.group(2)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def index_books(books_dir: str | Path) -> dict:
    """Index books/<book>/<page>.md into book/chapter/page nodes + edges.
    Output shape matches build_graph (lists of dicts) so the two merge."""
    books_dir = Path(books_dir)
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    if not books_dir.exists():
        return {"nodes": [], "edges": []}
    for md in sorted(books_dir.rglob("*.md")):
        if md.name.upper() == "README.MD":
            continue
        rel = md.relative_to(books_dir)
        book = rel.parts[0] if len(rel.parts) > 1 else rel.stem
        meta, body = parse_frontmatter(md.read_text(errors="replace"))
        chapter = str(meta.get("chapter") or "general")
        title = str(meta.get("title") or md.stem)
        book_id = f"book:{book}"
        chap_id = f"chapter:{book}.{chapter}"
        page_id = f"page:{book}.{chapter}.{_slug(title)}"
        nodes.setdefault(book_id, {"id": book_id, "kind": "book", "name": book,
                                   "file": str(md.parent), "line": 0, "doc": ""})
        if chap_id not in nodes:
            nodes[chap_id] = {"id": chap_id, "kind": "chapter", "name": chapter,
                              "file": str(md.parent), "line": 0, "doc": ""}
            edges.append({"src": book_id, "dst": chap_id, "kind": "contains"})
        nodes[page_id] = {"id": page_id, "kind": "page", "name": title,
                          "file": str(md), "line": 0, "doc": body.strip()[:200]}
        edges.append({"src": chap_id, "dst": page_id, "kind": "contains"})
        ex = meta.get("explains") or []
        if isinstance(ex, str):
            ex = [ex]
        if not isinstance(ex, list):
            ex = []
        for sym in ex:
            edges.append({"src": page_id, "dst": str(sym), "kind": "explains"})
    return {"nodes": list(nodes.values()), "edges": edges}
