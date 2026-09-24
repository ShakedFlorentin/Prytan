from __future__ import annotations
import sys
from core.knowledge.codegrapher.graph import write_graph
from core.knowledge.codegrapher.query import load_graph, query_graph

DEFAULT_OUT = "codegrapher_out/graph.json"


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: codegrapher <scan DIR | query TERM>", file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "scan":
        src = rest[0] if rest else "."
        out = write_graph(src, DEFAULT_OUT)
        g = load_graph(out)
        print(f"scanned {src} -> {out} ({len(g['nodes'])} nodes, {len(g['edges'])} edges)")
        return 0
    if cmd == "query":
        try:
            g = load_graph(DEFAULT_OUT)
        except FileNotFoundError:
            print("no graph found — run 'scan .' first", file=sys.stderr)
            return 1
        hits = query_graph(g, " ".join(rest))
        for h in hits:
            print(f"[{h['kind']}] {h['id']}  ({h['file']}:{h['line']})")
        if not hits:
            print("(no matches)")
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
