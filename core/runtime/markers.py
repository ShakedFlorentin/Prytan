from __future__ import annotations
import re
from dataclasses import dataclass

SCAN_MODEL = "claude-haiku-4-5"   # cheap tier for mechanical scans

_RUN = re.compile(r"^@@RUN(W?):\s*([a-z_]+)\s*::\s*(.+)$", re.MULTILINE)
_SCAN = re.compile(r"^@@SCAN:\s*([a-z_]+)\s*::\s*(.+)$", re.MULTILINE)


@dataclass
class Dispatch:
    agent: str
    task: str
    write: bool = False
    model: str | None = None
    kind: str = "run"


def parse_markers(reply: str) -> tuple[str, list[Dispatch]]:
    """Return (cleaned_text, dispatches). Markers are stripped from cleaned_text.
    Markers are parsed ONLY from neo's relay (never raw agent output)."""
    out: list[Dispatch] = []
    for m in _RUN.finditer(reply):
        out.append(Dispatch(agent=m.group(2), task=m.group(3).strip(),
                            write=(m.group(1) == "W"), kind="run"))
    for m in _SCAN.finditer(reply):
        out.append(Dispatch(agent=m.group(1), task=m.group(2).strip(),
                            model=SCAN_MODEL, kind="scan"))
    cleaned = _SCAN.sub("", _RUN.sub("", reply)).strip()
    return cleaned, out
