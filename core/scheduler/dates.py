from __future__ import annotations
from datetime import datetime, timedelta


def workday(now: datetime) -> str:
    """The work-day a post-midnight job should process: the prior CALENDAR day.

    Tenet: a job firing at 02:00 rolls up YESTERDAY's output, not today's.
    `now` is injected (never read from the wall clock here) so the rule is
    deterministic and testable.
    """
    return (now - timedelta(days=1)).date().isoformat()


def is_work_day(day_iso: str, work_week: list[int]) -> bool:
    """True if `day_iso` (YYYY-MM-DD) falls on a configured work-week day.
    Weekday convention: Monday=0 .. Sunday=6 (datetime.weekday())."""
    return datetime.fromisoformat(day_iso).weekday() in set(work_week)


def prior_work_day(now: datetime, work_week: list[int]) -> str:
    """Most recent work-week day strictly before `now` — skips weekends/off-days.
    Falls back to the prior calendar day if no work day is found within a week."""
    d = (now - timedelta(days=1)).date()
    for _ in range(7):
        if d.weekday() in set(work_week):
            return d.isoformat()
        d = d - timedelta(days=1)
    return (now - timedelta(days=1)).date().isoformat()
