from __future__ import annotations
import re
from pathlib import Path

MEMORY_DIR = "memory"
INDEX = "MEMORY.md"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def add_memory(root: str | Path, title: str, description: str, body: str,
               mtype: str = "project") -> Path:
    mem = Path(root) / MEMORY_DIR
    mem.mkdir(parents=True, exist_ok=True)
    slug = _slug(title)
    f = mem / f"{slug}.md"
    f.write_text(f"---\nname: {slug}\ndescription: {description}\ntype: {mtype}\n---\n\n{body}\n")
    idx = mem / INDEX
    if not idx.exists():
        idx.write_text("# Memory Index\n\n")
    line = f"- [{title}]({slug}.md) — {description}\n"
    if line not in idx.read_text():
        with idx.open("a") as h:
            h.write(line)
    return f


def recall(root: str | Path, query: str, limit: int = 5) -> list[dict]:
    """Memory facts relevant to `query`, best first.

    Uses the same relevance gate as prompt-time recall (whole words, IDF-weighted
    coverage of the query's content words), relaxed for an explicit lookup: a
    one-word query may match on that one word.
    """
    from core.knowledge.relevance import score, tokenize
    from core.knowledge.memory.sources import TIER_MEMORY, gather

    pool = [c for c in gather(root) if c.tier == TIER_MEMORY]
    hits = score(query, pool, min_matches=min(2, len(set(tokenize(query)))) or 1)
    return [{"name": Path(c.path).stem, "file": str(Path(root) / c.path),
             "text": c.text[:300]} for _, c, _ in hits[:limit]]
