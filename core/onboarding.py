from __future__ import annotations
import json
import shutil
from pathlib import Path
import yaml
from core.config import DEFAULTS
from core.knowledge.codegrapher.graph import build_graph

FRAMEWORK = Path(__file__).resolve().parent.parent   # plugin/repo root
GRAPH_OUT = "codegrapher_out/graph.json"
HOOK_MODULE = "core.knowledge.codegrapher.hook"
# ${CLAUDE_PLUGIN_ROOT} is set when Prytan runs as an installed plugin; fall back to
# this checkout's path so a plain clone works too. Without one of the two, the hook
# fires in the *project's* cwd and dies with ModuleNotFoundError — silently, because
# a failing hook does not surface to the user.
HOOK_CMD = ('PYTHONPATH="${CLAUDE_PLUGIN_ROOT:-' + str(FRAMEWORK) + '}" '
            "python3 -m " + HOOK_MODULE)


def _ensure_config(cwd: Path) -> Path:
    p = Path(cwd) / "config.yaml"
    if not p.exists():
        p.write_text(yaml.safe_dump(DEFAULTS, sort_keys=False))
    return p


def config_set(cwd, key_path: str, value) -> Path:
    p = _ensure_config(Path(cwd))
    data = yaml.safe_load(p.read_text()) or {}
    cur = data
    keys = key_path.split(".")
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = value
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    return p


def scan_sources(cwd, dirs: list[str], books_dir=None) -> Path:
    cwd = Path(cwd)
    nodes: dict = {}
    edges: list = []
    # Pass books_dir only on the first build call to avoid duplicate book nodes;
    # subsequent dir builds are code-only (books are merged once below).
    first = True
    for d in dirs:
        bd = (Path(books_dir) if books_dir is not None else None) if first else None
        g = build_graph(cwd / d, books_dir=bd)
        first = False
        for n in g["nodes"]:
            nodes[n["id"]] = n
        edges.extend(g["edges"])
    seen, deduped = set(), []
    for e in edges:
        k = (e["src"], e["dst"], e["kind"])
        if k not in seen:
            seen.add(k)
            deduped.append(e)
    out = cwd / GRAPH_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"nodes": list(nodes.values()), "edges": deduped}, indent=2))
    return out


def install_agent(cwd, agent_id: str, force: bool = False) -> Path:
    src = FRAMEWORK / "agents" / "_base" / f"{agent_id}.md"
    if not src.exists():
        raise FileNotFoundError(f"no base agent template: {agent_id}")
    dst_dir = Path(cwd) / ".claude" / "agents"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{agent_id}.md"
    if dst.exists() and not force:
        return dst                       # non-destructive: never clobber the project's own
    shutil.copy(src, dst)
    return dst


# role_type distinguishes who AUTHORS a domain's deliverable (writes the actual
# artifact — RTL, ML models, firmware, infra manifests, ...) from who is merely
# ADVISORY (reviews/audits it but never produces it). Every project domain that
# has a real deliverable needs an authoring agent, not just an advisor — an
# advisor-only roster silently leaves nobody chartered to do the work.
AUTHORING_TOOLS = ("Read", "Glob", "Grep", "Write", "Edit")
ADVISORY_TOOLS = ("Read", "Glob", "Grep")


def author_agent(cwd, agent_id: str, name: str, description: str, body: str,
                 tools=None, role_type: str = "authoring") -> Path:
    if role_type not in ("authoring", "advisory"):
        raise ValueError(f"role_type must be 'authoring' or 'advisory', got {role_type!r}")
    if tools is None:
        tools = AUTHORING_TOOLS if role_type == "authoring" else ADVISORY_TOOLS
    dst_dir = Path(cwd) / ".claude" / "agents"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{agent_id}.md"
    tl = "\n".join(f"  - {t}" for t in tools)
    dst.write_text(
        f"---\nname: {agent_id}\ndescription: {description}\n"
        f"model: claude-sonnet-4-6\nrole_type: {role_type}\ntools:\n{tl}\n---\n\n"
        f"# {name}\n\n{body}\n")
    config_set(cwd, f"agents.{agent_id}", name)
    return dst


def wire_hook(cwd) -> Path:
    sp = Path(cwd) / ".claude" / "settings.json"
    settings = json.loads(sp.read_text()) if sp.exists() else {}
    hooks = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
    # Match on the module, not the full command: an older/broken invocation of the
    # same hook should be replaced, not left sitting alongside the fixed one.
    hooks[:] = [h for h in hooks if HOOK_MODULE not in json.dumps(h)]
    hooks.append({"matcher": "Grep|Glob",
                  "hooks": [{"type": "command", "command": HOOK_CMD}]})
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(settings, indent=2))
    return sp
