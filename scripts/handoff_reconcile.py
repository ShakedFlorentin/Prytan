#!/usr/bin/env python3
"""
handoff_reconcile.py — Auto-close stale agent handoffs.

A validation handoff in `.agent-handoffs/` can stay `status: open` after its
referenced findings were ALREADY closed in review reports, causing later cycles to
re-validate work that's done (wasted agent tokens).

The fix: a reconciler that auto-resolves a handoff IFF:
  - its status is still resolvable (open / none — never touch accepted/in-progress/done), AND
  - it references ≥1 finding id (e.g. GAP-<name>-<n>), AND
  - EVERY referenced finding is found in reports AND is no longer `open`.

If any referenced finding is still `open`, or any id can't be found, the handoff is
left untouched (fail-safe — never close a genuinely-open handoff).

Pure stdlib. Run on startup + hourly, or standalone:
  python3 scripts/handoff_reconcile.py [--apply]   (dry-run by default)
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HANDOFFS_DIR = ROOT / ".agent-handoffs"
REPORTS_DIR = ROOT / ".agent-inbox" / "reports"

FINDING_RE = re.compile(r"GAP-[a-z0-9_]+-\d+", re.IGNORECASE)
_STATUS_LINE = re.compile(r"^status:\s*(.*)$", re.IGNORECASE | re.MULTILINE)

RESOLVABLE = {"open", "none"}


def referenced_findings(text: str) -> set[str]:
    """The finding ids a handoff references (normalized lower-case)."""
    return {m.lower() for m in FINDING_RE.findall(text or "")}


def _status_of(text: str) -> str:
    m = _STATUS_LINE.search(text or "")
    return (m.group(1).strip().lower() if m else "")


def finding_status_index(reports_dir: Path = REPORTS_DIR) -> dict[str, str]:
    """Map every finding id → its current status, across all report JSONs."""
    index: dict[str, str] = {}
    for p in sorted(Path(reports_dir).glob("*.json")):
        try:
            data = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        for f in (data.get("findings") or data.get("gaps") or []):
            fid = (f.get("id") or "").lower()
            if fid:
                index[fid] = (f.get("status") or "open").lower()
    return index


def _apply_resolution(text: str, reason: str) -> str:
    """Rewrite the frontmatter: set status→resolved and add a resolved-by line."""
    lines = text.splitlines()
    out, done_status = [], False
    for ln in lines:
        if not done_status and _STATUS_LINE.match(ln):
            out.append("status: resolved")
            done_status = True
            if "resolved-by:" not in text:
                out.append(f"resolved-by: {reason}")
            continue
        out.append(ln)
    if not done_status:
        return text
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def reconcile(handoffs_dir: Path = HANDOFFS_DIR, reports_dir: Path = REPORTS_DIR,
              now: datetime | None = None, dry_run: bool = False) -> list[dict]:
    """Auto-resolve stale handoffs. Returns list of resolved {file, findings, statuses}.
    Leaves everything else untouched. Fail-safe: unknown/open finding → skip."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    index = finding_status_index(reports_dir)
    resolved = []
    for p in sorted(Path(handoffs_dir).glob("*.md")):
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        if _status_of(text) not in RESOLVABLE:
            continue
        refs = referenced_findings(text)
        if not refs:
            continue
        statuses = {r: index.get(r) for r in refs}
        if any(s is None for s in statuses.values()):
            continue   # can't prove done
        if any(s == "open" for s in statuses.values()):
            continue   # real work still open
        reason = (f"auto-reconcile {now.date().isoformat()} — referenced findings already "
                  f"closed ({', '.join(f'{k}={v}' for k, v in sorted(statuses.items()))})")
        if not dry_run:
            try:
                p.write_text(_apply_resolution(text, reason))
            except OSError:
                continue
        resolved.append({"file": p.name, "findings": sorted(refs), "statuses": statuses})
    return resolved


if __name__ == "__main__":
    import sys
    dry = "--apply" not in sys.argv
    res = reconcile(dry_run=dry)
    mode = "WOULD RESOLVE (dry-run; pass --apply to write)" if dry else "RESOLVED"
    print(f"{mode}: {len(res)} stale handoff(s)")
    for r in res:
        print(f"  - {r['file']}  ({', '.join(r['findings'])})")
