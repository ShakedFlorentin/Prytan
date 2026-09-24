from __future__ import annotations
import json
from pathlib import Path

SKILLS_FILE = ".logs/skills.json"


def load_lessons(root: str | Path) -> list[dict]:
    f = Path(root) / SKILLS_FILE
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text())
        return data if isinstance(data, list) else []
    except ValueError:
        return []


def add_lesson(root: str | Path, lesson: str, *, day: str) -> Path:
    """Append one design-agnostic lesson; dedupe by exact lesson text."""
    f = Path(root) / SKILLS_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    lessons = load_lessons(root)
    if any(x.get("lesson") == lesson for x in lessons):
        return f
    lessons.append({"day": day, "lesson": lesson})
    f.write_text(json.dumps(lessons, indent=2) + "\n")
    return f
