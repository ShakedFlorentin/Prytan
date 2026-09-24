from __future__ import annotations
import ast
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from core.knowledge.codegrapher.books import index_books
from core.knowledge.codegrapher.ts import build_ts_graph, SKIP_DIRS


@dataclass
class Node:
    id: str
    kind: str           # module | class | function
    name: str
    file: str
    line: int = 0
    doc: str = ""


@dataclass
class Edge:
    src: str
    dst: str
    kind: str           # contains | imports


def _py_skipped(path: Path, root: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.relative_to(root).parts)


def build_graph(source_dir: str | Path, books_dir: str | Path | None = None) -> dict:
    source_dir = Path(source_dir)
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    for py in sorted(source_dir.rglob("*.py")):
        if _py_skipped(py, source_dir):
            continue
        rel = py.relative_to(source_dir)
        mod = "module:" + str(rel.with_suffix("")).replace("/", ".")
        try:
            tree = ast.parse(py.read_text(errors="replace"))
        except SyntaxError:
            continue
        nodes[mod] = Node(id=mod, kind="module", name=str(rel), file=str(py),
                          doc=(ast.get_docstring(tree) or "")[:200])
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(n, ast.ClassDef) else "function"
                nid = f"{kind}:{mod[len('module:'):]}.{n.name}"
                nodes[nid] = Node(id=nid, kind=kind, name=n.name, file=str(py),
                                  line=n.lineno, doc=(ast.get_docstring(n) or "")[:200])
                edges.append(Edge(src=mod, dst=nid, kind="contains"))
            elif isinstance(n, ast.Import):
                for a in n.names:
                    edges.append(Edge(src=mod, dst=f"import:{a.name}", kind="imports"))
            elif isinstance(n, ast.ImportFrom):
                edges.append(Edge(src=mod, dst=f"import:{n.module or ''}", kind="imports"))
    graph = {"nodes": [asdict(v) for v in nodes.values()],
             "edges": [asdict(e) for e in edges]}

    # TypeScript / JavaScript. Most projects the org gets pointed at are web apps,
    # and before this they indexed to an empty graph — which silently turned the
    # query-before-grep hook into pure overhead.
    ts = build_ts_graph(source_dir)
    known = {n["id"] for n in graph["nodes"]}
    graph["nodes"].extend(n for n in ts["nodes"] if n["id"] not in known)
    graph["edges"].extend(ts["edges"])

    if books_dir is not None:
        bg = index_books(books_dir)
        graph["nodes"].extend(bg["nodes"])
        graph["edges"].extend(bg["edges"])
    return graph


def write_graph(source_dir: str | Path, out_path: str | Path,
                books_dir: str | Path | None = None) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(build_graph(source_dir, books_dir=books_dir), indent=2))
    return out_path
