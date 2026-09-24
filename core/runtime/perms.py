from __future__ import annotations
import json
from pathlib import Path

# The perms file lives OUTSIDE the write-allowed org dirs so a write-scoped agent
# cannot overwrite its own permission boundary (self-escalation).
PERMS_DIR = ".agent-runtime"

# Per-agent run-log dir, nested under the existing `.logs` comm dir (this is the
# layout templates/nightly/summarize.md already expects when it scans
# `.logs/*/{day}-*.md` for "per-agent run logs"). Charter-mandated, org-wide
# memory also always persists here regardless of dispatch scoping.
LOG_ROOT = ".logs"
MEMORY_DIR = "memory"


def agent_log_dir(agent_id: str) -> str:
    """Path (relative to project root) of one agent's own run-log/journal dir."""
    return f"{LOG_ROOT}/{agent_id}"


def write_perms_file(cwd: str | Path, org_dirs: list[str]) -> Path:
    """Generate a Claude Code settings file that ALLOW-LISTS Write/Edit to the org
    dirs only. No global deny: in Claude Code deny beats allow, so a global
    `Write(**)` deny would override the org-dir allows and block ALL writes. With an
    allow-list and no deny, writes outside the listed dirs are simply not permitted.
    Returns the settings path (under .agent-runtime/, which is NOT write-allowed)."""
    cwd = Path(cwd)
    allow = ["Read(**)", "Glob(**)", "Grep(**)"]
    for d in org_dirs:
        allow += [f"Write({d}/**)", f"Edit({d}/**)"]
    settings = {"permissions": {"allow": allow}}
    dst = cwd / PERMS_DIR / ".perms.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(settings, indent=2))
    return dst


def write_scoped_perms_file(cwd: str | Path, agent_id: str, *,
                            deliverable_dirs: list[str] | None = None) -> Path:
    """Perms for ONE dispatch of `agent_id`.

    Always writable, no matter whether this dispatch is read-only or write-scoped:
    - the agent's own run-log/journal dir (`agent_log_dir`)
    - the shared `memory/` dir (charter-mandated persistence)

    These are charter-mandated paths, not deliverables — "read-only advisor" means
    read-only on PRODUCT SOURCE, never on the agent's own journal or memory writes.
    A read-only advisor with no deliverable scope still gets this much.

    `deliverable_dirs` (e.g. COMM_DIRS) are ADDITIVE and represent the per-dispatch
    write scope for actual deliverables (handoffs, proposals, …) — pass them only
    for write dispatches. Dispatch scoping constrains deliverables only; it never
    narrows the always-writable paths above.
    """
    dirs = [agent_log_dir(agent_id), MEMORY_DIR, *(deliverable_dirs or [])]
    return write_perms_file(cwd, dirs)
