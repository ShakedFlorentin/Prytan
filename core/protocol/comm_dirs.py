from __future__ import annotations
from pathlib import Path

COMM_DIRS = (".inbox", ".handoffs", ".proposals", ".logs")


def ensure_comm_dirs(root: str | Path) -> list[Path]:
    root = Path(root)
    made = []
    for name in COMM_DIRS:
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        made.append(d)
    return made
