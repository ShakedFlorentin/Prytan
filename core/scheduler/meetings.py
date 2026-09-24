from __future__ import annotations
from datetime import datetime
from pathlib import Path
from core.config import Config
from core.runtime.agent_runner import run_agent
from core.scheduler.templates import load_template, render

# which base-agent facilitates each cadence meeting (read-only governance runs)
MEETING_FACILITATOR = {
    "pod-daily": "governance",
    "weekly-sprint": "governance",
    "monthly-milestone": "governance",
}


def run_meeting(config: Config, kind: str, *, cwd: str, run=run_agent,
                now: datetime) -> Path:
    if kind not in MEETING_FACILITATOR:
        raise ValueError(f"unknown meeting kind: {kind}")
    facilitator = MEETING_FACILITATOR[kind]
    day = now.date().isoformat()                       # meetings run for TODAY
    prompt = render(load_template(f"meetings/{kind}"),
                    facilitator=facilitator, project=config.project_name, day=day)
    text = run(facilitator, prompt, cwd=cwd)
    out = Path(cwd) / ".inbox" / f"{day}-{kind}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    return out
