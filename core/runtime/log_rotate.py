"""Log rotation for the Prytan usage ledger and cron log.

The usage ledger (.logs/usage.tsv) grows unboundedly. This module archives it
once it exceeds a configurable size threshold, keeping up to `keep` archives.

Rotation convention:
    .logs/usage.tsv          ← active ledger
    .logs/usage.tsv.1        ← most recent archive
    .logs/usage.tsv.2        ← ...
    .logs/usage.tsv.{keep}   ← oldest archive (deleted on next rotate)

Same scheme applies to .logs/cron.log.
"""
from __future__ import annotations
from pathlib import Path

DEFAULT_MAX_BYTES = 5 * 1024 * 1024   # 5 MB
DEFAULT_KEEP = 5


def rotate(path: str | Path, *,
           max_bytes: int = DEFAULT_MAX_BYTES,
           keep: int = DEFAULT_KEEP) -> bool:
    """Rotate `path` if it exceeds `max_bytes`. Return True if rotation happened."""
    path = Path(path)
    if not path.exists() or path.stat().st_size < max_bytes:
        return False

    # Shift existing archives: .N → .N+1, dropping anything > keep
    for i in range(keep, 0, -1):
        src = path.with_suffix(path.suffix + f".{i}")
        dst = path.with_suffix(path.suffix + f".{i + 1}")
        if src.exists():
            if i >= keep:
                src.unlink()
            else:
                src.rename(dst)

    # Archive the active file
    path.rename(path.with_suffix(path.suffix + ".1"))
    path.touch()          # re-create empty active file
    return True


def rotate_logs(cwd: str | Path, *,
                max_bytes: int = DEFAULT_MAX_BYTES,
                keep: int = DEFAULT_KEEP) -> list[str]:
    """Rotate all standard Prytan log files under <cwd>/.logs/.

    Returns list of paths that were rotated.
    """
    logs_dir = Path(cwd) / ".logs"
    rotated = []
    for name in ("usage.tsv", "cron.log"):
        p = logs_dir / name
        if rotate(p, max_bytes=max_bytes, keep=keep):
            rotated.append(str(p))
    return rotated
