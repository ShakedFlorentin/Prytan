from __future__ import annotations
from pathlib import Path


class BudgetExceededError(Exception):
    """Raised when cumulative spend reaches the configured daily limit."""

PRICING = {  # USD per million tokens
    "claude-sonnet-4-6": {"in": 3.0, "cache_read": 0.30, "cache_write": 3.75, "out": 15.0},
    "claude-haiku-4-5":  {"in": 0.80, "cache_read": 0.08, "cache_write": 1.0, "out": 4.0},
    "claude-opus-4-8":   {"in": 15.0, "cache_read": 1.50, "cache_write": 18.75, "out": 75.0},
}
DEFAULT_MODEL = "claude-sonnet-4-6"


def turn_cost(usage: dict, model: str | None = None) -> float:
    p = PRICING.get(model or DEFAULT_MODEL, PRICING[DEFAULT_MODEL])
    u = usage or {}
    return (u.get("input_tokens", 0) * p["in"]
            + u.get("cache_read_input_tokens", 0) * p["cache_read"]
            + u.get("cache_creation_input_tokens", 0) * p["cache_write"]
            + u.get("output_tokens", 0) * p["out"]) / 1_000_000


def log_usage(ledger: str | Path, agent: str, model: str, usage: dict,
              cost: float) -> None:
    ledger = Path(ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    u = usage or {}
    row = "\t".join(str(x) for x in [
        agent, model, u.get("input_tokens", 0),
        u.get("cache_read_input_tokens", 0), u.get("output_tokens", 0),
        f"{cost:.5f}"])
    with ledger.open("a") as f:
        f.write(row + "\n")


def daily_cost(ledger: str | Path) -> float:
    """Sum the USD cost column across every row in the ledger."""
    ledger = Path(ledger)
    if not ledger.exists():
        return 0.0
    total = 0.0
    for line in ledger.read_text().splitlines():
        parts = line.strip().split("\t")
        if len(parts) >= 6:
            try:
                total += float(parts[5])
            except ValueError:
                pass
    return total


def check_budget(ledger: str | Path, limit_usd: float | None) -> None:
    """Raise BudgetExceededError if cumulative ledger spend >= limit_usd.

    Pass limit_usd=None to disable the gate (default when unconfigured).
    """
    if limit_usd is None:
        return
    spent = daily_cost(ledger)
    if spent >= limit_usd:
        raise BudgetExceededError(
            f"Daily budget of ${limit_usd:.2f} exceeded "
            f"(ledger total ${spent:.5f})"
        )
