from __future__ import annotations
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from core.config import Config
from core.runtime.agent_runner import run_agent
from core.scheduler.meetings import run_meeting
from core.scheduler.nightly import run_nightly

USAGE = "usage: python -m core.scheduler {nightly | meeting <kind>}"


def main(argv: list[str] | None = None, *, cwd: str | None = None, run=run_agent,
         now: datetime | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    cwd = cwd or str(Path.cwd())
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2
    cfg = Config.load(Path(cwd) / "config.yaml")
    now = now or datetime.now(ZoneInfo(cfg.timezone))
    cmd = argv[0]
    if cmd == "nightly":
        res = run_nightly(cfg, cwd=cwd, run=run, now=now)
        print(f"nightly complete for {res['day']}: {res['digest']}")
        return 0
    if cmd == "meeting":
        if len(argv) < 2:
            print(USAGE, file=sys.stderr)
            return 2
        out = run_meeting(cfg, argv[1], cwd=cwd, run=run, now=now)
        print(f"meeting written: {out}")
        return 0
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":               # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
