"""
books.py — index reference documentation under .claude/books/ into the graph.

Each markdown file carries YAML frontmatter:

    ---
    id: auth-design
    type: page              # or: book
    chapter: security
    book: architecture
    keywords: oauth, jwt, session, ...
    explains: auth.verify_token, auth.create_session
    ---

We emit:
  • book    node per `type: book`
  • chapter node synthesized per (book, chapter)
  • page    node per `type: page`
  • book --contains--> chapter --contains--> page  (hierarchy)
  • page --explains--> <code symbol>               (resolved to a code node
    when the symbol exists in the graph, else an external node)

No third-party YAML dependency — a tiny line parser handles flat frontmatter.
"""

import re
from pathlib import Path

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
DEFAULT_BOOKS_ROOT = Path(".claude/books")


def _parse_frontmatter(text: str) -> dict:
    m = _FRONTMATTER.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        fm[key.strip()] = val.strip()
    return fm


def _split_list(val: str) -> list[str]:
    return [x.strip() for x in val.split(",") if x.strip()]


def index_books(books_root: Path = DEFAULT_BOOKS_ROOT) -> tuple[list, list]:
    """Return (nodes, edges) describing every book/chapter/page found."""
    nodes: list[dict] = []
    edges: list[dict] = []
    if not books_root.exists():
        return nodes, edges

    seen_chapters: set[str] = set()

    for md in sorted(books_root.rglob("*.md")):
        try:
            text = md.read_text(errors="replace")
        except OSError:
            continue
        fm = _parse_frontmatter(text)
        if not fm:
            continue

        ntype = fm.get("type", "")
        nid = fm.get("id") or md.stem
        rel = str(md)

        if ntype == "book":
            nodes.append({"id": f"book:{nid}", "type": "book", "label": fm.get("title", nid), "file": rel})

        elif ntype == "page":
            page_id = f"page:{nid}"
            nodes.append({"id": page_id, "type": "page", "label": fm.get("title", nid), "file": rel, "keywords": fm.get("keywords", "")})

            book = fm.get("book", "")
            chapter = fm.get("chapter", "")
            if book and chapter:
                chap_id = f"chapter:{book}/{chapter}"
                if chap_id not in seen_chapters:
                    seen_chapters.add(chap_id)
                    nodes.append({"id": chap_id, "type": "chapter", "label": chapter, "file": ""})
                    edges.append({"src": f"book:{book}", "tgt": chap_id, "rel": "contains"})
                edges.append({"src": chap_id, "tgt": page_id, "rel": "contains"})
            elif book:
                edges.append({"src": f"book:{book}", "tgt": page_id, "rel": "contains"})

            for sym in _split_list(fm.get("explains", "")):
                edges.append({"src": page_id, "tgt": sym, "rel": "explains"})

    return nodes, edges


def resolve_explains_target(symbol: str, label_index: dict) -> str | None:
    """Map an explains: symbol to a code node id. Returns node id or None."""
    exact = label_index.get(symbol, [])
    if exact:
        return exact[0][0]
    module, _, sym = symbol.partition(".")
    if not sym:
        return None
    candidates = label_index.get(sym, [])
    if not candidates:
        return None
    for node_id, file_rel in candidates:
        if file_rel and Path(file_rel).stem == module:
            return node_id
    return candidates[0][0]
