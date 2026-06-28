#!/usr/bin/env python3
"""
agent_violations.py — Deterministic record of when an agent broke its rules.

Why this exists: "the agent noted it and moved on" is itself an UNVERIFIED agent
claim. A violation log that depends on the agent narrating that it logged something
will silently not happen. So the write lives HERE, in the trusted bot/Python layer:
the moment a guard fires (claim_guard flags an impossible claim, or an org-path/perm
check rejects a write), the bot calls record() — no agent, no narration.

Two consumers, two cadences:
  - IMMEDIATE: the bot reads severity at dispatch time. A `hard` violation taints the
    CURRENT result the human is about to act on, so the bot flags it loudly and
    refuses to chain follow-on work off the tainted output.
  - NIGHTLY: the nightly skill-compiler reads recent() to turn recurring patterns for
    one agent into a proposed definition fix.

Pure stdlib, fail-safe (a logging failure must never break a dispatch). JSONL so it's
append-only and trivially machine-readable.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
LOG_PATH = PROJ / ".agent-logs" / "violations.jsonl"

HARD = "hard"
SOFT = "soft"


def record(agent: str, vtype: str, severity: str, detail: str, task: str = "") -> None:
    """Append one violation. Never raises — a broken log must not break a dispatch."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": (agent or "?").lower(),
            "type": vtype,
            "severity": severity if severity in (HARD, SOFT) else SOFT,
            "detail": (detail or "")[:400],
            "task": (task or "")[:200],
        }
        with LOG_PATH.open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def load(path: Path = LOG_PATH) -> list:
    """All recorded violations (oldest first). Skips corrupt lines."""
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except (ValueError, TypeError):
            continue
    return out


def recent(days: int = 1, now: datetime = None, path: Path = LOG_PATH) -> list:
    """Violations within the last `days` — what the nightly loop reads."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    out = []
    for r in load(path):
        try:
            ts = datetime.fromisoformat(r["ts"])
        except (ValueError, KeyError, TypeError):
            continue
        if ts >= cutoff:
            out.append(r)
    return out


def by_agent(rows: list = None) -> dict:
    """Group → {agent: [violations]} to spot 'this agent keeps doing X'."""
    rows = load() if rows is None else rows
    grouped = {}
    for r in rows:
        grouped.setdefault(r.get("agent", "?"), []).append(r)
    return grouped


if __name__ == "__main__":
    import sys
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    rows = recent(days=d)
    print(f"{len(rows)} violation(s) in the last {d}d:")
    for r in rows:
        print(f"  {r['ts'][:19]}  {r['agent']:8}  [{r['severity']}] {r['type']}: {r['detail'][:80]}")
