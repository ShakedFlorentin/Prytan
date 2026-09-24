from __future__ import annotations
import json
import subprocess
from dataclasses import dataclass, field


@dataclass
class AgentResult:
    text: str
    usage: dict = field(default_factory=dict)
    model: str | None = None


def _build_cmd(agent_id: str, *, write: bool, model: str | None,
               perms_file) -> list[str]:
    cmd = ["claude", "-p", "--agent", agent_id]
    # A perms_file (scoped Write/Edit allow-list) may be supplied for read-only
    # dispatches too — every agent, including read-only advisors, always gets a
    # scoped-writable journal (see core.runtime.perms.write_scoped_perms_file).
    # "write" only decides whether the scope includes deliverable dirs; it is not
    # what gates whether a perms_file is honored here.
    if perms_file:
        cmd += ["--settings", str(perms_file)]
    else:
        cmd += ["--allowedTools", "Read,Glob,Grep"]
    if model:
        cmd += ["--model", model]
    cmd += ["--output-format", "json"]
    return cmd


def run_agent_metered(agent_id: str, task: str, *, cwd: str, write: bool = False,
                      model: str | None = None, perms_file=None,
                      runner=subprocess.run) -> AgentResult:
    if write and perms_file is None:
        raise ValueError("write=True requires a perms_file (scoped-write boundary)")
    cmd = _build_cmd(agent_id, write=write, model=model, perms_file=perms_file)
    proc = runner(cmd, input=task, capture_output=True, text=True, cwd=cwd)
    stdout = (proc.stdout or "").strip()
    try:
        env = json.loads(stdout)
        text = (env.get("result") or stdout).strip()
        usage = env.get("usage", {}) or {}
    except (ValueError, AttributeError):
        text, usage = stdout, {}
    return AgentResult(text=text, usage=usage, model=model)


def run_agent(agent_id: str, task: str, *, cwd: str, write: bool = False,
              model: str | None = None, perms_file=None,
              runner=subprocess.run) -> str:
    """Text-only wrapper (backward compatible with Plan 1)."""
    return run_agent_metered(agent_id, task, cwd=cwd, write=write, model=model,
                             perms_file=perms_file, runner=runner).text
