#!/usr/bin/env python3
"""
Decision Ledger — append-only JSONL ledger for agent decisions.

Usage:
  python3 scripts/decision_ledger.py add --title "..." --raised-by <agent> --pod <pod> \
      --door-type <two_way|one_way|strategic_fork> [--resolution "..."]
  python3 scripts/decision_ledger.py list [--status awaiting_human|auto_resolved]
  python3 scripts/decision_ledger.py resolve <decision-id> --resolution "..."
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

LEDGER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".agent-inbox")
LEDGER_FILE = os.path.join(LEDGER_DIR, "decisions.jsonl")


def _ensure_ledger_dir():
    os.makedirs(LEDGER_DIR, exist_ok=True)


def _load_records():
    if not os.path.exists(LEDGER_FILE):
        return []
    records = []
    with open(LEDGER_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def _append_record(record):
    _ensure_ledger_dir()
    with open(LEDGER_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _next_id(records, today_str):
    prefix = f"D-{today_str}-"
    count = sum(1 for r in records if r.get("id", "").startswith(prefix))
    return f"{prefix}{count + 1:02d}"


def _rewrite_records(records):
    _ensure_ledger_dir()
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def cmd_add(args):
    door_type = args.door_type
    valid_door_types = {"two_way", "one_way", "strategic_fork"}
    if door_type not in valid_door_types:
        print(f"ERROR: --door-type must be one of: {', '.join(sorted(valid_door_types))}", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    records = _load_records()
    decision_id = _next_id(records, today_str)

    if door_type == "two_way":
        status = "auto_resolved"
        resolved_by = args.raised_by
        resolved_at = now.isoformat()
        resolution = args.resolution or "Agent autonomous decision."
    else:
        status = "awaiting_human"
        resolved_by = None
        resolved_at = None
        resolution = args.resolution or None

    record = {
        "id": decision_id,
        "created": now.isoformat(),
        "raised_by": args.raised_by,
        "pod": args.pod,
        "title": args.title,
        "door_type": door_type,
        "status": status,
        "resolution": resolution,
        "resolved_by": resolved_by,
        "resolved_at": resolved_at,
    }

    _append_record(record)
    print(f"Added: {decision_id} [{status}]")
    return record


def cmd_list(args):
    records = _load_records()
    status_filter = args.status if args.status else None

    filtered = records
    if status_filter:
        filtered = [r for r in records if r.get("status") == status_filter]

    if not filtered:
        print("No decisions found.")
        return

    for r in filtered:
        resolution_str = f" | resolution: {r['resolution']}" if r.get("resolution") else ""
        print(
            f"{r['id']} | {r['door_type']} | {r['status']} | {r['raised_by']} ({r['pod']}) "
            f"| {r['title']}{resolution_str}"
        )


def cmd_resolve(args):
    decision_id = args.decision_id
    records = _load_records()

    found = False
    for record in records:
        if record.get("id") == decision_id:
            found = True
            if record.get("status") == "auto_resolved":
                print(f"WARNING: {decision_id} is already auto_resolved. Updating resolution text.")
            now = datetime.now(timezone.utc)
            record["status"] = "auto_resolved"
            record["resolution"] = args.resolution
            record["resolved_by"] = "human"
            record["resolved_at"] = now.isoformat()
            break

    if not found:
        print(f"ERROR: Decision {decision_id} not found.", file=sys.stderr)
        sys.exit(1)

    _rewrite_records(records)
    print(f"Resolved: {decision_id}")


def main():
    parser = argparse.ArgumentParser(description="Agent decision ledger (append-only JSONL).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add
    add_parser = subparsers.add_parser("add", help="Add a new decision record.")
    add_parser.add_argument("--title", required=True, help="Short decision title.")
    add_parser.add_argument("--raised-by", required=True, dest="raised_by", help="Agent name that raised this.")
    add_parser.add_argument("--pod", required=True, help="Pod/domain this belongs to.")
    add_parser.add_argument(
        "--door-type",
        required=True,
        dest="door_type",
        choices=["two_way", "one_way", "strategic_fork"],
        help="Decision door type.",
    )
    add_parser.add_argument("--resolution", default=None, help="Optional resolution text (for two_way).")

    # list
    list_parser = subparsers.add_parser("list", help="List decision records.")
    list_parser.add_argument(
        "--status",
        choices=["awaiting_human", "auto_resolved"],
        default=None,
        help="Filter by status.",
    )

    # resolve
    resolve_parser = subparsers.add_parser("resolve", help="Resolve a decision (human approval).")
    resolve_parser.add_argument("decision_id", help="Decision ID to resolve (e.g. D-2024-01-15-01).")
    resolve_parser.add_argument("--resolution", required=True, help="Resolution text.")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "resolve":
        cmd_resolve(args)


if __name__ == "__main__":
    main()


# ── Query helpers (used by morning_brief and telegram-bot) ───────────────────

def _read_all(ledger: Path = None):
    """Read all records from the ledger."""
    p = ledger or LEDGER
    if not Path(str(p)).exists():
        return []
    import json as _json
    out = []
    for line in Path(str(p)).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(_json.loads(line))
        except (ValueError, TypeError):
            continue
    return out


def _latest_by_id(records):
    """Last record per decision id (newest state wins)."""
    by_id = {}
    for r in records:
        did = r.get("id")
        if did:
            by_id[did] = r
    return by_id


def age_days(record: dict, now=None) -> int:
    """Days since this decision was created."""
    from datetime import datetime, timezone
    now = now or datetime.now(timezone.utc)
    try:
        created = datetime.fromisoformat(record.get("created", "")).astimezone(timezone.utc)
        return max(0, (now.astimezone(timezone.utc) - created).days)
    except (ValueError, TypeError):
        return 0


def pending_for_human(now=None, ledger: Path = None) -> list:
    """awaiting_human decisions (latest state per id), oldest first."""
    from datetime import datetime, timezone
    now = now or datetime.now(timezone.utc)
    out = []
    for r in _latest_by_id(_read_all(ledger)).values():
        if r.get("status") == "awaiting_human":
            r = dict(r)
            r["age_days"] = age_days(r, now)
            out.append(r)
    return sorted(out, key=lambda r: r.get("created", ""))


def auto_resolved_today(now=None, ledger: Path = None) -> list:
    """Decisions auto-resolved today (two_way decisions the agent handled itself)."""
    from datetime import datetime, timezone
    now = now or datetime.now(timezone.utc)
    d = now.strftime("%Y-%m-%d")
    return [r for r in _latest_by_id(_read_all(ledger)).values()
            if r.get("status") == "auto_resolved"
            and r.get("created", "").startswith(d)]
