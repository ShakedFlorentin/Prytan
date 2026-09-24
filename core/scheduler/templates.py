from __future__ import annotations
from pathlib import Path

# core/scheduler/templates.py -> parents[2] == repo root (where templates/ lives)
FRAMEWORK = Path(__file__).resolve().parents[2]
TEMPLATES = FRAMEWORK / "templates"


def load_template(name: str) -> str:
    """Load templates/<name>.md (name uses '/' subdirs, no extension)."""
    f = TEMPLATES / f"{name}.md"
    if not f.exists():
        raise FileNotFoundError(f"template not found: {f}")
    return f.read_text()


def render(template_text: str, **tokens: str) -> str:
    """Replace {key} for each provided token. Brace-safe: unknown braces survive.

    Pass free-text tokens (e.g. digest) LAST so a digest containing a literal
    {project} is not re-substituted by a later iteration.
    """
    out = template_text
    for k, v in tokens.items():
        out = out.replace("{" + k + "}", str(v))
    return out
