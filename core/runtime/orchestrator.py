from __future__ import annotations
from pathlib import Path
from core.config import Config, agent_ids
from core.protocol.comm_dirs import COMM_DIRS
from core.runtime.agent_runner import run_agent_metered
from core.runtime.markers import parse_markers
from core.runtime.perms import write_scoped_perms_file
from core.runtime.metering import turn_cost, log_usage, check_budget

CHIEF_OF_STAFF_ID = "atlas"


class Orchestrator:
    def __init__(self, config: Config, *, cwd: str, run=run_agent_metered):
        self.config = config
        self.cwd = cwd
        self._run = run
        self._ledger = Path(cwd) / ".logs" / "usage.tsv"

    def _meter(self, agent: str, result) -> None:
        cost = turn_cost(result.usage, result.model)
        log_usage(self._ledger, agent, result.model or "default", result.usage, cost)

    def handle(self, message: str) -> str:
        neo = self._run(CHIEF_OF_STAFF_ID, message, cwd=self.cwd)
        self._meter(CHIEF_OF_STAFF_ID, neo)
        cleaned, dispatches = parse_markers(neo.text)
        if not dispatches:
            return cleaned or neo.text
        limit = self.config.budget.get("daily_limit_usd")
        valid_agents = agent_ids(self.config)
        results = []
        for d in dispatches:
            # Explicit-routing requirement: never silently run an unknown/unrouted
            # agent id. A dispatch marker names its agent explicitly by construction
            # (see markers.py), but the name must also resolve to a real roster
            # entry (base role or project-authored domain agent) — fail loudly here
            # instead of forwarding a bad id to the CLI.
            if d.agent not in valid_agents:
                results.append(
                    f"[{d.agent}] ROUTING ERROR: '{d.agent}' is not a known agent "
                    "id in this org's roster — dispatch skipped rather than "
                    "silently defaulted.")
                continue
            check_budget(self._ledger, limit)
            # Model priority: marker override > config tier > None (agent default)
            model = d.model or self.config.agents_model.get(d.agent)
            # Deliverable write scope is additive and gated by d.write; the
            # agent's own journal + shared memory are always writable regardless
            # (write_scoped_perms_file) — dispatch scoping constrains deliverables
            # only, never charter-mandated persistence.
            deliverable_dirs = list(COMM_DIRS) if d.write else []
            perms = write_scoped_perms_file(self.cwd, d.agent,
                                            deliverable_dirs=deliverable_dirs)
            r = self._run(d.agent, d.task, cwd=self.cwd, write=d.write,
                          model=model, perms_file=perms)
            self._meter(d.agent, r)
            results.append(f"[{d.agent}] {r.text}")
        relay = (message + "\n\n--- agent results ---\n" + "\n\n".join(results)
                 + "\n\n--- end ---\nSynthesize ONE concise answer for the human.")
        final = self._run(CHIEF_OF_STAFF_ID, relay, cwd=self.cwd)
        self._meter(CHIEF_OF_STAFF_ID, final)
        return final.text
