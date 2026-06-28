#!/usr/bin/env python3
"""
skills_store.py — The single versioned artifact that decouples the two concepts.

  Concept 1 (skill_compiler.py)  --writes-->  .agent-logs/skills.json
  Concept 2 (telegram-bot.py)   --reads--->  (soft: absence/staleness/bad-version
                                               degrade to an empty lesson set, the
                                               parser then uses its static schema)

This is a DATA dependency through a file, not a code dependency — the seam the
design calls for. Pure stdlib (json + os). Enforcement rules implemented here:
  1. Versioned & ignorable: a file whose schema_version != SCHEMA_VERSION loads as
     EMPTY (the parser must never choke on a format it doesn't understand).
  2. Per-lesson robustness: malformed lessons are dropped individually, not fatally.
  3. mtime-cached reads: re-parse only when the file actually changes (hot-path cheap).
"""
import json
import os
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
SKILLS_PATH = PROJ / ".agent-logs/skills.json"
SCHEMA_VERSION = 1

# Required key -> accepted python type(s) for one lesson record.
_LESSON_FIELDS = {
    "id": str, "kind": str, "pattern": str, "guidance": str,
}
_LESSON_KINDS = {"intent_mapping", "constraint", "failure_pattern", "scope_hint"}

_cache = {"mtime": None, "data": None}


def _valid_lesson(x) -> bool:
    if not isinstance(x, dict):
        return False
    for k, t in _LESSON_FIELDS.items():
        if not isinstance(x.get(k), t) or not x.get(k):
            return False
    return x["kind"] in _LESSON_KINDS


def _empty() -> dict:
    return {"schema_version": SCHEMA_VERSION, "lessons": []}


def load() -> dict:
    """Return {schema_version, lessons:[...]} — always well-formed. Any problem
    (missing file, unreadable, wrong version, junk) yields an EMPTY lesson set so
    the parser degrades to its static schema. mtime-cached; never raises."""
    try:
        st = SKILLS_PATH.stat()
    except OSError:
        return _empty()
    if _cache["mtime"] == st.st_mtime and _cache["data"] is not None:
        return _cache["data"]
    data = _empty()
    try:
        raw = json.loads(SKILLS_PATH.read_text(errors="ignore"))
        if isinstance(raw, dict) and raw.get("schema_version") == SCHEMA_VERSION:
            data = {
                "schema_version": SCHEMA_VERSION,
                "lessons": [x for x in raw.get("lessons", []) if _valid_lesson(x)],
            }
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        data = _empty()
    _cache["mtime"], _cache["data"] = st.st_mtime, data
    return data


def lessons(kind: str | None = None) -> list:
    ls = load()["lessons"]
    return [x for x in ls if x.get("kind") == kind] if kind else ls


def save(lesson_list: list) -> bool:
    """Atomically write a validated lesson set. Drops malformed records. Returns
    True on success. Used only by the offline compiler (never the hot path)."""
    clean = [x for x in lesson_list if _valid_lesson(x)]
    payload = {"schema_version": SCHEMA_VERSION, "lessons": clean}
    try:
        SKILLS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = SKILLS_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        os.replace(tmp, SKILLS_PATH)
        _cache["mtime"] = None  # invalidate
        return True
    except OSError:
        return False
