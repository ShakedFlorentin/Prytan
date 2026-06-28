#!/usr/bin/env python3
"""
scripts/cost_governor.py — token budget gate for cron runs.

Reads .agent-config/budget.yaml, accumulates spend from spend_log,
then exits with:
  - code 0 + prints "PROCEED" if under throttle threshold
  - code 0 + prints "THROTTLE" if between throttle and halt thresholds
  - code 1 + prints "HALT" if over halt threshold

Crontab pattern:
  python3 scripts/cost_governor.py && echo "prompt" | claude --print ...

The governor also supports recording a completed run's spend:
  python3 scripts/cost_governor.py --record --tokens 45000 --usd 0.14 --run-id standup-20240101

Usage:
  python3 scripts/cost_governor.py              # Gate check
  python3 scripts/cost_governor.py --status     # Print spend summary
  python3 scripts/cost_governor.py --record ... # Record a completed run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ──────────────────────────────────────────────
# YAML parser (stdlib only — no pyyaml dep)
# ──────────────────────────────────────────────

def _parse_yaml_simple(text: str) -> Dict[str, Any]:
    """
    Minimal YAML parser for flat key: value files.
    Handles strings, ints, floats, booleans. No nested structures.
    Lines starting with # are comments.
    """
    result: Dict[str, Any] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, raw_value = line.partition(":")
        key = key.strip()
        value = raw_value.strip()
        # Strip inline comments
        if " #" in value:
            value = value[:value.index(" #")].strip()
        # Type coercion
        if value.lower() in ("true", "yes"):
            result[key] = True
        elif value.lower() in ("false", "no"):
            result[key] = False
        else:
            try:
                result[key] = int(value)
            except ValueError:
                try:
                    result[key] = float(value)
                except ValueError:
                    result[key] = value
    return result


# ──────────────────────────────────────────────
# Config loading
# ──────────────────────────────────────────────

DEFAULT_CONFIG = {
    "monthly_budget_usd": 50.0,
    "throttle_threshold_pct": 80,
    "halt_threshold_pct": 95,
    "per_run_token_cap": 200000,
    "spend_log": ".agent-config/spend.jsonl",
    "reset_day": 1,
}

CONFIG_PATH = ".agent-config/budget.yaml"


def load_config(path: str = CONFIG_PATH) -> Dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    p = Path(path)
    if p.exists():
        try:
            cfg.update(_parse_yaml_simple(p.read_text()))
        except Exception as e:
            print(f"[governor] Warning: could not parse {path}: {e}", file=sys.stderr)
    return cfg


# ──────────────────────────────────────────────
# Spend log
# ──────────────────────────────────────────────

def load_spend_log(spend_log: str) -> List[Dict[str, Any]]:
    p = Path(spend_log)
    if not p.exists():
        return []
    records = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def monthly_spend(records: List[Dict[str, Any]], reset_day: int = 1) -> float:
    """Sum USD spend since the most recent reset_day."""
    now = datetime.now(tz=timezone.utc)
    if now.day >= reset_day:
        cutoff = now.replace(day=reset_day, hour=0, minute=0, second=0, microsecond=0)
    else:
        # Previous month
        if now.month == 1:
            cutoff = now.replace(year=now.year - 1, month=12, day=reset_day,
                                 hour=0, minute=0, second=0, microsecond=0)
        else:
            cutoff = now.replace(month=now.month - 1, day=reset_day,
                                 hour=0, minute=0, second=0, microsecond=0)
    cutoff_ts = cutoff.timestamp()
    return sum(r.get("usd", 0.0) for r in records if r.get("ts", 0) >= cutoff_ts)


def record_spend(spend_log: str, tokens: int, usd: float, run_id: str) -> None:
    p = Path(spend_log)
    p.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.time(),
        "tokens": tokens,
        "usd": usd,
        "run_id": run_id,
        "date": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
    }
    with p.open("a") as f:
        f.write(json.dumps(entry) + "\n")


# ──────────────────────────────────────────────
# Gate logic
# ──────────────────────────────────────────────

def gate(cfg: Dict[str, Any]) -> str:
    """Return 'PROCEED', 'THROTTLE', or 'HALT'."""
    records = load_spend_log(cfg["spend_log"])
    spent = monthly_spend(records, cfg.get("reset_day", 1))
    budget = float(cfg["monthly_budget_usd"])
    pct = (spent / budget * 100) if budget > 0 else 0.0

    halt_pct = float(cfg["halt_threshold_pct"])
    throttle_pct = float(cfg["throttle_threshold_pct"])

    if pct >= halt_pct:
        return "HALT"
    elif pct >= throttle_pct:
        return "THROTTLE"
    else:
        return "PROCEED"


def print_status(cfg: Dict[str, Any]) -> None:
    records = load_spend_log(cfg["spend_log"])
    spent = monthly_spend(records, cfg.get("reset_day", 1))
    budget = float(cfg["monthly_budget_usd"])
    pct = (spent / budget * 100) if budget > 0 else 0.0

    print(f"Monthly budget:  ${budget:.2f}")
    print(f"Spent this month: ${spent:.4f} ({pct:.1f}%)")
    print(f"Throttle at:      {cfg['throttle_threshold_pct']}% (${budget * cfg['throttle_threshold_pct'] / 100:.2f})")
    print(f"Halt at:          {cfg['halt_threshold_pct']}% (${budget * cfg['halt_threshold_pct'] / 100:.2f})")
    print(f"Total log entries: {len(records)}")
    print(f"Gate decision:    {gate(cfg)}")


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Prytan token budget governor")
    parser.add_argument("--status", action="store_true", help="Print spend summary")
    parser.add_argument("--record", action="store_true", help="Record a completed run's spend")
    parser.add_argument("--tokens", type=int, default=0)
    parser.add_argument("--usd", type=float, default=0.0)
    parser.add_argument("--run-id", default="manual")
    parser.add_argument("--config", default=CONFIG_PATH)
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.record:
        record_spend(cfg["spend_log"], args.tokens, args.usd, args.run_id)
        print(f"Recorded: {args.tokens} tokens, ${args.usd:.4f} for run {args.run_id!r}")
        sys.exit(0)

    if args.status:
        print_status(cfg)
        sys.exit(0)

    # Gate check
    decision = gate(cfg)
    print(decision)

    if decision == "HALT":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
