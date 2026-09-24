"""STATE.md utility — read/write structured phase-tracking state for multi-phase work.

Convention:
  STATE.md lives at the project root and is a Markdown table with two columns:
  Phase and Status. Agents update it during GSD execute cycles; Atlas reads it
  for synthesis and progress reports.

Example STATE.md:
  # Work State
  | Phase | Status |
  | --- | --- |
  | 1 · Schema migration | ✅ done |
  | 2 · API endpoints | 🔄 in progress |
  | 3 · Frontend wiring | ⏳ pending |
"""
from __future__ import annotations
import re
from pathlib import Path

STATE_FILE = "STATE.md"

# Status shorthand aliases (optional)
DONE = "✅ done"
IN_PROGRESS = "🔄 in progress"
PENDING = "⏳ pending"
BLOCKED = "🚫 blocked"
SKIPPED = "⏭ skipped"


def load(cwd: str | Path) -> dict[str, str]:
    """Return {phase: status} dict from STATE.md, or {} if missing."""
    path = Path(cwd) / STATE_FILE
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|", line)
        if m:
            key, val = m.group(1).strip(), m.group(2).strip()
            if key.lower() not in {"phase", "---", ":---", "---:"}:
                out[key] = val
    return out


def save(cwd: str | Path, phases: dict[str, str],
         title: str = "Work State") -> None:
    """Write phases dict to STATE.md as a Markdown table."""
    path = Path(cwd) / STATE_FILE
    lines = [
        f"# {title}",
        "",
        "| Phase | Status |",
        "| --- | --- |",
    ]
    for phase, status in phases.items():
        lines.append(f"| {phase} | {status} |")
    path.write_text("\n".join(lines) + "\n")


def update(cwd: str | Path, phase: str, status: str,
           title: str = "Work State") -> None:
    """Set the status of a single phase, creating STATE.md if needed."""
    phases = load(cwd)
    phases[phase] = status
    save(cwd, phases, title)


def clear(cwd: str | Path) -> None:
    """Delete STATE.md (call at the start of a fresh GSD plan cycle)."""
    path = Path(cwd) / STATE_FILE
    path.unlink(missing_ok=True)
