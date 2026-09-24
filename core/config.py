from __future__ import annotations
import copy
import dataclasses
from pathlib import Path
import yaml

DEFAULTS = {
    "project_name": "my-org",
    "human": {"name": "founder", "role": "owner"},
    "interface": "cli",
    "timezone": "UTC",
    "work_week": [0, 1, 2, 3, 4],  # Mon-Fri
    "agents": {
        "chief_of_staff": "Atlas",
        "governance": "Marcus",
        "tech_architecture": "Alex",
        "product": "Sofia",
        "backend": "Sam",
        "frontend": "Jordan",
        "qa": "Jamie",
        "devops": "Chris",
        "build": "Lee",
        "ux": "Taylor",
        "content": "Maya",
        "growth": "Omar",
        "security": "Nina",
        "legal": "Mike",
        "reflection": "Ada",
        "reliability": "Robin",
    },
    # Per-agent model tier overrides. Read-only advisor agents use Opus for
    # stronger reasoning at higher stakes. Writable workers stay on Sonnet.
    # @@SCAN markers override all of these with Haiku for cheap scans.
    "agents_model": {
        "security": "claude-opus-4-8",
        "legal": "claude-opus-4-8",
        "reflection": "claude-opus-4-8",
    },
    # Token budget enforcement. Set daily_limit_usd to a float (e.g. 5.0) to
    # hard-cap daily spend; None disables the gate.
    "budget": {
        "daily_limit_usd": None,
    },
    "codegrapher": {"enabled": True, "enforce_query_first": True, "source_dir": None},
    "schedule": {
        "summarize": "02:00",
        "reflection": "03:00",
        "reliability": "04:00",
        "morning_prepare": "05:00",
        "pod_daily": "05:30",
        "weekly_sprint": "06:00",
        "monthly_milestone": "07:00",
    },
    "books": {},   # role -> [book names] the role consults; empty by default
}


# Role key (as used in DEFAULTS["agents"] / config.yaml) -> persona/dispatch id
# (the id used in `@@RUN(W?): <id> :: task` markers and the `claude --agent <id>`
# CLI invocation). Most roles share the same id; a few don't. This is the single
# source of truth for "is this a real, routable agent id?" — dispatch validation
# (Orchestrator) checks against AGENT_IDS so an unrouted/misspelled agent id fails
# loudly instead of being silently forwarded to the CLI.
ROLE_TO_AGENT_ID = {
    "chief_of_staff": "atlas", "governance": "governance", "tech_architecture": "tech",
    "product": "product", "backend": "backend", "frontend": "frontend", "qa": "qa",
    "devops": "devops", "build": "build", "ux": "ux", "content": "content",
    "growth": "growth", "security": "security", "legal": "legal",
    "reflection": "reflection", "reliability": "reliability",
}

AGENT_IDS = frozenset(ROLE_TO_AGENT_ID.values())


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


@dataclasses.dataclass
class Config:
    project_name: str
    human: dict
    interface: str
    timezone: str
    work_week: list
    agents: dict
    agents_model: dict
    budget: dict
    codegrapher: dict
    schedule: dict
    books: dict

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        path = Path(path)
        data = _deep_merge(DEFAULTS, {})  # copy — never alias the module constant
        if path.exists():
            loaded = yaml.safe_load(path.read_text()) or {}
            data = _deep_merge(DEFAULTS, loaded)
        names = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: data[k] for k in names})


def shelves_for(config: "Config", role: str) -> list[str]:
    """Book names the given role consults (empty if none mapped)."""
    return list(config.books.get(role, []))


def agent_ids(config: "Config") -> frozenset[str]:
    """All valid dispatch ids for this org: the base roles (mapped through
    ROLE_TO_AGENT_ID) plus any project-authored domain agents. Authored agents'
    config.agents key IS already their dispatch id (core.onboarding.author_agent
    registers them as `agents.<agent_id>`), so only base-role keys need mapping."""
    return frozenset(ROLE_TO_AGENT_ID.get(role, role) for role in config.agents)
