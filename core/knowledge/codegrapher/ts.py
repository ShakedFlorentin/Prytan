"""TypeScript / JavaScript source parsing for codegrapher.

The Python side of codegrapher uses `ast`, which is exact. There is no stdlib
equivalent for TS, and pulling a real parser would mean a Node dependency — which
this project explicitly does not have ("zero runtime dependencies", fully local).

So this is a deliberately shallow scanner: it finds *declarations*, not semantics.
That is enough for what the graph is actually for — answering "which file holds
the thing called X" in one lookup instead of a blind grep. It does not try to
resolve types, follow re-exports, or understand generics.

Handles .ts .tsx .js .jsx .mjs .cjs, including the shapes this codebase leans on:
arrow-function consts, `export function`, React components, hooks, and interfaces.
"""
from __future__ import annotations

import re
from pathlib import Path

SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

# Directories that are never source.
SKIP_DIRS = {
    "node_modules", ".next", "dist", "build", "out", "coverage",
    ".git", "__pycache__", ".turbo", ".vercel",
}

_DECL = [
    # kind, regex. Each must expose a named group `name`.
    ("function", re.compile(
        r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(?P<name>[A-Za-z_$][\w$]*)")),
    ("class", re.compile(
        r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)")),
    ("interface", re.compile(
        r"^\s*(?:export\s+)?interface\s+(?P<name>[A-Za-z_$][\w$]*)")),
    ("type", re.compile(
        r"^\s*(?:export\s+)?type\s+(?P<name>[A-Za-z_$][\w$]*)\s*=")),
    ("enum", re.compile(
        r"^\s*(?:export\s+)?(?:const\s+)?enum\s+(?P<name>[A-Za-z_$][\w$]*)")),
    # const Foo = (...) => ...   |   const Foo = function ... |  const Foo = async (
    ("function", re.compile(
        r"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*"
        r"(?::[^=]+)?=\s*(?:async\s*)?(?:function\b|\(|<[^>]*>\s*\()")),
    # plain exported const that is not a function — still worth locating
    ("const", re.compile(
        r"^\s*export\s+(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*(?::[^=]+)?=")),
]

_IMPORT = re.compile(r"""^\s*(?:import\b[^'"]*|export\s+[^'"]*\bfrom\s*)['"](?P<mod>[^'"]+)['"]""")
_REQUIRE = re.compile(r"""\brequire\(\s*['"](?P<mod>[^'"]+)['"]\s*\)""")

# `/** ... */` immediately above a declaration, or a run of `//` lines.
_BLOCK_DOC_END = re.compile(r"^\s*\*/")
_BLOCK_DOC_START = re.compile(r"^\s*/\*\*")
# The whole comment on one line — by far the most common shape for a short doc.
_ONE_LINE_DOC = re.compile(r"^\s*/\*\*\s*(?P<text>.*?)\s*\*/\s*$")
_LINE_DOC = re.compile(r"^\s*//\s?(?P<text>.*)$")


def is_ts_source(path: Path) -> bool:
    if path.suffix not in SUFFIXES:
        return False
    return not any(part in SKIP_DIRS for part in path.parts)


def _doc_above(lines: list[str], idx: int) -> str:
    """Collect the comment directly above line `idx` (0-based), if any."""
    i = idx - 1
    while i >= 0 and not lines[i].strip():
        i -= 1
    if i < 0:
        return ""

    m = _ONE_LINE_DOC.match(lines[i])
    if m:
        return m.group("text")[:200]

    if _BLOCK_DOC_END.match(lines[i]):
        out: list[str] = []
        j = i - 1
        while j >= 0 and not _BLOCK_DOC_START.match(lines[j]):
            out.append(re.sub(r"^\s*\*?\s?", "", lines[j]).rstrip())
            j -= 1
        if j < 0:
            return ""
        return " ".join(reversed([o for o in out if o]))[:200]

    out = []
    while i >= 0:
        m = _LINE_DOC.match(lines[i])
        if not m:
            break
        out.append(m.group("text").strip())
        i -= 1
    return " ".join(reversed([o for o in out if o]))[:200]


def module_id(rel: Path) -> str:
    """`src/lib/time/hebrew.ts` -> `module:src.lib.time.hebrew`.

    Matches the dotted convention the Python scanner uses so both languages land
    in one namespace and `query` treats them identically.
    """
    return "module:" + str(rel.with_suffix("")).replace("/", ".")


def parse_file(path: Path, rel: Path) -> tuple[dict, list[dict], list[dict]]:
    """Return (module_node, decl_nodes, edges) for one TS/JS file."""
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    mod = module_id(rel)

    header = ""
    for i, ln in enumerate(lines[:40]):
        one = _ONE_LINE_DOC.match(ln)
        if one:
            header = one.group("text")[:200]
            break
        if _BLOCK_DOC_START.match(ln):
            body = []
            for j in range(i + 1, min(len(lines), i + 40)):
                if _BLOCK_DOC_END.match(lines[j]):
                    break
                body.append(re.sub(r"^\s*\*?\s?", "", lines[j]).rstrip())
            header = " ".join(b for b in body if b)[:200]
            break

    module_node = {"id": mod, "kind": "module", "name": str(rel),
                   "file": str(path), "line": 0, "doc": header}

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    seen_imports: set[str] = set()

    for n, raw in enumerate(lines):
        line = raw.rstrip()
        if not line.strip():
            continue

        m = _IMPORT.match(line) or _REQUIRE.search(line)
        if m:
            target = m.group("mod")
            if target not in seen_imports:
                seen_imports.add(target)
                edges.append({"src": mod, "dst": f"import:{target}", "kind": "imports"})
            continue

        for kind, rx in _DECL:
            m = rx.match(line)
            if not m:
                continue
            name = m.group("name")
            nid = f"{kind}:{mod[len('module:'):]}.{name}"
            if nid in nodes:
                break
            nodes[nid] = {"id": nid, "kind": kind, "name": name, "file": str(path),
                          "line": n + 1, "doc": _doc_above(lines, n)}
            edges.append({"src": mod, "dst": nid, "kind": "contains"})
            break

    return module_node, list(nodes.values()), edges


def build_ts_graph(source_dir: str | Path) -> dict:
    source_dir = Path(source_dir)
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    for f in sorted(source_dir.rglob("*")):
        if not f.is_file() or not is_ts_source(f):
            continue
        rel = f.relative_to(source_dir)
        mod_node, decls, es = parse_file(f, rel)
        nodes[mod_node["id"]] = mod_node
        for d in decls:
            nodes[d["id"]] = d
        edges.extend(es)
    return {"nodes": list(nodes.values()), "edges": edges}
