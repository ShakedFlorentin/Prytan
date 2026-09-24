"""The candidate pool for prompt-time recall, read fresh from disk on every call.

The org's knowledge lives in plain files: the curated `memory/` dir, the comm
dirs (.handoffs, .inbox, .proposals), per-agent logs under `.logs/<agent>/`, and
saved conversation turns in `.logs/conversations.jsonl`. Nothing is indexed, so
a deleted file can never be recalled; each file contributes its first
BODY_CHARS characters, not a short preview.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.knowledge.relevance import Candidate
from core.protocol.comm_dirs import COMM_DIRS
from core.runtime.perms import LOG_ROOT, MEMORY_DIR

BODY_CHARS = 4000
CONVERSATIONS = f"{LOG_ROOT}/conversations.jsonl"
INDEX = "MEMORY.md"

# Tie-break tiers (lower = more curated). Scheduled chatter — standups, sprint
# plans, digests, briefs — mentions everything and decides nothing.
TIER_MEMORY = 0
TIER_HANDOFF = 2
TIER_LOG = 3
TIER_CONVERSATION = 4
TIER_CHATTER = 5

_CHATTER = re.compile(
    r"(standup|stand-up|sprint|daily|digest|all-?hands|brief|weekly|sync|eod|nightly)",
    re.IGNORECASE,
)
_DATED = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)$")
_FRONTMATTER = re.compile(r"^---\s*\n.*?\n---\s*\n?", re.DOTALL)
_DESCRIPTION = re.compile(r"^description:\s*\"?(.*?)\"?\s*$", re.MULTILINE)
_BASE_AGENTS = Path(__file__).resolve().parents[3] / "agents" / "_base"


def known_agents(root: Path) -> set[str]:
    """Agent ids: the plugin's base roster, the project's own agents, and every
    per-agent log dir that exists."""
    names = {p.stem for p in _BASE_AGENTS.glob("*.md")}
    names |= {p.stem for p in (root / ".claude" / "agents").glob("*.md")}
    logs = root / LOG_ROOT
    if logs.is_dir():
        names |= {d.name for d in logs.iterdir() if d.is_dir()}
    return names


def author_of(path: Path, base: Path, agents: set[str]) -> str:
    """Owning agent: the log's folder (.logs/<agent>/...) or the name right after
    the date in a dated filename (2026-06-18-atlas-backend-x.md → atlas).
    Never the year — the leading date is not an author."""
    rel = path.relative_to(base)
    if len(rel.parts) > 1 and rel.parts[0] in agents:
        return rel.parts[0]
    m = _DATED.match(path.stem)
    if m:
        first = m.group(1).split("-", 1)[0]
        if first in agents:
            return first
    return ""


def _read(path: Path) -> str:
    try:
        with path.open(errors="replace") as fh:
            return fh.read(BODY_CHARS)
    except OSError:
        return ""


def _title(path: Path, text: str) -> str:
    m = _DESCRIPTION.search(text[:1500])
    if m and m.group(1):
        return m.group(1).replace('\\"', '"')
    for line in _FRONTMATTER.sub("", text, count=1).splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line[:160]
    return path.stem


def _files(root: Path, sub: str, source: str, tier: int, agents: set[str]) -> list[Candidate]:
    base = root / sub
    if not base.is_dir():
        return []
    out = []
    for md in sorted(base.rglob("*.md")):
        if md.name == INDEX:
            continue  # the index — every line would match everything
        text = _read(md)
        if not text:
            continue
        t = TIER_CHATTER if tier != TIER_MEMORY and _CHATTER.search(md.stem) else tier
        rel = str(md.relative_to(root))
        out.append(Candidate(id=f"{source}:{rel}", text=text, source=source,
                             title=_title(md, text), path=rel,
                             author=author_of(md, base, agents), tier=t))
    return out


def _conversations(root: Path, exclude_session: str) -> list[Candidate]:
    path = root / CONVERSATIONS
    if not path.is_file():
        return []
    out = []
    for i, line in enumerate(path.read_text(errors="replace").splitlines()):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if exclude_session and rec.get("session_id") == exclude_session:
            continue  # this session's own turns are already in context
        prompt = rec.get("prompt", "")
        out.append(Candidate(id=f"conversation:{i}", text=f"{prompt}\n{rec.get('reply', '')}",
                             source="conversation",
                             title=f"{rec.get('ts', '')[:16]} — {prompt[:120]}",
                             path=CONVERSATIONS, tier=TIER_CONVERSATION))
    return out


EMBED_CACHE = ".agent-runtime/embeddings"


def semantic_enabled(root: str | Path) -> bool:
    """True only when the project opted in: `memory: {semantic: true}` in
    config.yaml. Any problem reading the config means off."""
    try:
        from core.config import Config

        return bool(Config.load(Path(root) / "config.yaml").memory.get("semantic"))
    except Exception:  # noqa: BLE001 — unreadable config: stay on the word gate
        return False


def embedder(root: str | Path, timeout: float = 1.5, max_new: int = 6):
    """The semantic checker (a local Ollama embedding model), cached under
    .agent-runtime/. Callers use it only when semantic_enabled(); if Ollama or the
    model is missing even then, recall uses words alone."""
    from core.knowledge.semantic import Embedder

    return Embedder(Path(root) / EMBED_CACHE, timeout=timeout, max_new=max_new)


def gather(root: str | Path, exclude_session: str = "") -> list[Candidate]:
    """Every recallable candidate under a project root, read fresh from disk."""
    root = Path(root)
    agents = known_agents(root)
    tiers = {".handoffs": TIER_HANDOFF}
    pool = _files(root, MEMORY_DIR, "memory", TIER_MEMORY, agents)
    for d in COMM_DIRS:
        pool += _files(root, d, d.lstrip("."), tiers.get(d, TIER_LOG), agents)
    return pool + _conversations(root, exclude_session)
