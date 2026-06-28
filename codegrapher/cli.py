"""
codegrapher/cli.py — CLI commands: scan, query, explain, path, stats.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List

from .graph import Graph
from .query import query_graph, shortest_path, explain_node
from .cache import scan_directory


GRAPH_PATH = "codegrapher_out/graph.json"


def _load_graph() -> Graph:
    return Graph.load(GRAPH_PATH)


def _save_graph(g: Graph) -> None:
    g.save()


# ──────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────

def cmd_scan(args: List[str]) -> int:
    """scan <directory> [--force]"""
    if not args:
        print("Usage: codegrapher.py scan <directory> [--force]", file=sys.stderr)
        return 1

    directory = args[0]
    force = "--force" in args

    # Also scan agent logs if they exist
    from .agents import scan_agent_logs

    g = _load_graph()
    t0 = time.time()

    scanned, skipped = scan_directory(directory, g, force=force)

    # Agent logs
    for log_dir in [".agent-logs", ".agent-inbox"]:
        if Path(log_dir).exists():
            n = scan_agent_logs(log_dir, g, force=force)
            if n:
                print(f"  Agent logs indexed: {n} from {log_dir}/")

    _save_graph(g)
    elapsed = time.time() - t0
    print(f"Scanned {scanned} files, skipped {skipped} (unchanged) in {elapsed:.2f}s")
    print(f"Graph: {len(g.nodes)} nodes, {len(g.edges)} edges → {GRAPH_PATH}")
    return 0


def cmd_query(args: List[str]) -> int:
    """query <text> [--top N] [--kind symbol|file|page|agent-log]"""
    if not args:
        print("Usage: codegrapher.py query <text> [--top N] [--kind KIND]", file=sys.stderr)
        return 1

    # Parse flags
    top_n = 10
    kinds = None
    query_tokens = []
    i = 0
    while i < len(args):
        if args[i] == "--top" and i + 1 < len(args):
            top_n = int(args[i + 1])
            i += 2
        elif args[i] == "--kind" and i + 1 < len(args):
            kinds = [args[i + 1]]
            i += 2
        else:
            query_tokens.append(args[i])
            i += 1

    query = " ".join(query_tokens)
    g = _load_graph()

    if not g.nodes:
        print("Graph is empty. Run: python3 codegrapher.py scan <directory>")
        return 0

    hits = query_graph(g, query, top_n=top_n, kinds=kinds)

    if not hits:
        print(f"No results for: {query!r}")
        return 0

    print(f"Results for {query!r} ({len(hits)} found):\n")
    for score, node in hits:
        loc = ""
        if node.file:
            loc = f"  {node.file}"
            if node.line:
                loc += f":{node.line}"
        tags = f"  [{', '.join(node.tags[:4])}]" if node.tags else ""
        print(f"  {score:5.1f}  {node.kind:<12}  {node.label}{tags}{loc}")

    return 0


def cmd_explain(args: List[str]) -> int:
    """explain <symbol or title>"""
    if not args:
        print("Usage: codegrapher.py explain <symbol>", file=sys.stderr)
        return 1

    query = " ".join(args)
    g = _load_graph()
    result = explain_node(g, query)

    if result is None:
        print(f"No match for: {query!r}")
        return 0

    node, context = result
    print(f"Node: {node.label}")
    print(f"  kind:  {node.kind}")
    print(f"  id:    {node.id}")
    if node.file:
        print(f"  file:  {node.file}" + (f":{node.line}" if node.line else ""))
    if node.tags:
        print(f"  tags:  {', '.join(node.tags)}")
    if node.meta:
        for k, v in node.meta.items():
            if k.startswith("_"):
                continue
            print(f"  {k}:  {str(v)[:120]}")

    out = context["outgoing"]
    inn = context["incoming"]

    if out:
        print(f"\nOutgoing edges ({len(out)}):")
        for e in out[:10]:
            print(f"  --[{e['rel']}]--> {e['label']} ({e['kind']})" + (f"  {e['file']}" if e.get("file") else ""))

    if inn:
        print(f"\nIncoming edges ({len(inn)}):")
        for e in inn[:10]:
            print(f"  <--[{e['rel']}]-- {e['label']} ({e['kind']})" + (f"  {e['file']}" if e.get("file") else ""))

    return 0


def cmd_path(args: List[str]) -> int:
    """path <node-id-or-label-a> <node-id-or-label-b>"""
    if len(args) < 2:
        print("Usage: codegrapher.py path <a> <b>", file=sys.stderr)
        return 1

    a_query = args[0]
    b_query = args[1]
    g = _load_graph()

    def resolve(q: str) -> str | None:
        if q in g.nodes:
            return q
        hits = query_graph(g, q, top_n=1)
        return hits[0][1].id if hits else None

    a_id = resolve(a_query)
    b_id = resolve(b_query)

    if not a_id:
        print(f"Could not find node for: {a_query!r}")
        return 1
    if not b_id:
        print(f"Could not find node for: {b_query!r}")
        return 1

    path = shortest_path(g, a_id, b_id)
    if path is None:
        print(f"No path found between {a_query!r} and {b_query!r} (max depth 6)")
        return 0

    print(f"Path ({len(path)} hops):")
    for i, nid in enumerate(path):
        n = g.nodes.get(nid)
        label = n.label if n else nid
        kind = n.kind if n else "?"
        prefix = "  " + ("→ " if i > 0 else "  ")
        print(f"{prefix}{label} ({kind})  [{nid}]")

    return 0


def cmd_stats(args: List[str]) -> int:
    """stats"""
    g = _load_graph()
    s = g.stats()

    from datetime import datetime, timezone
    updated = s.get("updated_at")
    if updated:
        dt = datetime.fromtimestamp(updated, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    else:
        dt = "never"

    print(f"Graph: {GRAPH_PATH}")
    print(f"  Updated:      {dt}")
    print(f"  Total nodes:  {s['total_nodes']}")
    print(f"  Total edges:  {s['total_edges']}")
    print()
    print("Nodes by kind:")
    for kind, count in sorted(s["nodes_by_kind"].items()):
        print(f"  {kind:<18}  {count}")
    print()
    print("Edges by relationship:")
    for rel, count in sorted(s["edges_by_rel"].items()):
        print(f"  {rel:<18}  {count}")

    return 0


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

COMMANDS = {
    "scan": cmd_scan,
    "query": cmd_query,
    "explain": cmd_explain,
    "path": cmd_path,
    "stats": cmd_stats,
}

USAGE = """
Usage: python3 codegrapher.py <command> [args]

Commands:
  scan <directory> [--force]          Index source files into the graph
  query <text> [--top N] [--kind K]   Search for nodes matching text
  explain <symbol>                    Show a node and its edges
  path <a> <b>                        Shortest path between two nodes
  stats                               Graph statistics
""".strip()


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        sys.exit(0)

    cmd_name = args[0]
    cmd_fn = COMMANDS.get(cmd_name)
    if cmd_fn is None:
        print(f"Unknown command: {cmd_name!r}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    sys.exit(cmd_fn(args[1:]))
