from __future__ import annotations
from datetime import datetime
from pathlib import Path
from core.config import Config
from core.runtime.agent_runner import run_agent
from core.runtime.log_rotate import rotate_logs
from core.scheduler.dates import prior_work_day
from core.scheduler.skills_store import add_lesson
from core.scheduler.templates import load_template, render

# fixed facilitators for the close-out chain
SUMMARIZE_AGENT = "governance"
REFLECT_AGENT = "reflection"
RELIABILITY_AGENT = "reliability"
PREPARE_AGENT = "governance"


def _write(cwd: str, rel: str, text: str) -> Path:
    p = Path(cwd) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def run_nightly(config: Config, *, cwd: str, run=run_agent,
                now: datetime) -> dict:
    """summarize -> reflection -> reliability -> morning-prepare, in order.

    Post-midnight tenet: every step processes the PRIOR work-day. Agents run
    read-only; this function owns all writes.
    """
    # Rotate logs before starting — keeps ledger and cron.log from growing unbounded
    rotate_logs(cwd)

    day = prior_work_day(now, config.work_week)
    proj = config.project_name

    # 1. summarize -> EOD digest
    digest_text = run(SUMMARIZE_AGENT,
                      render(load_template("nightly/summarize"),
                             facilitator=SUMMARIZE_AGENT, project=proj, day=day),
                      cwd=cwd)
    digest = _write(cwd, f".inbox/{day}-eod-digest.md", digest_text)

    # 2. reflection -> design-agnostic lessons (consumes the digest)
    lessons_text = run(REFLECT_AGENT,
                       render(load_template("nightly/reflect"),
                              facilitator=REFLECT_AGENT, project=proj, day=day,
                              digest=digest_text),
                       cwd=cwd)
    for line in (lessons_text or "").splitlines():
        line = line.strip().lstrip("-* ").strip()
        if line:
            add_lesson(cwd, line, day=day)

    # 3. reliability -> health report (runs last as the integrity backstop)
    health_text = run(RELIABILITY_AGENT,
                      render(load_template("nightly/reliability"),
                             facilitator=RELIABILITY_AGENT, project=proj, day=day),
                      cwd=cwd)
    health = _write(cwd, f".logs/{day}-health.md", health_text)

    # 4. morning-prepare (consumes the digest)
    prepare_text = run(PREPARE_AGENT,
                       render(load_template("nightly/prepare"),
                              facilitator=PREPARE_AGENT, project=proj, day=day,
                              digest=digest_text),
                       cwd=cwd)
    prepare = _write(cwd, f".inbox/{day}-prepare.md", prepare_text)

    return {"day": day, "digest": digest, "health": health, "prepare": prepare}
