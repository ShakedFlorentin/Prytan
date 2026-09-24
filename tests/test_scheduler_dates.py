from datetime import datetime
from core.scheduler.dates import workday, is_work_day, prior_work_day


def test_workday_is_prior_calendar_day():
    # a job firing post-midnight Wednesday processes Tuesday
    assert workday(datetime(2026, 6, 24, 2, 0)) == "2026-06-23"


def test_workday_handles_month_boundary():
    assert workday(datetime(2026, 7, 1, 3, 30)) == "2026-06-30"


def test_is_work_day_default_mon_fri():
    # Mon=0 .. Sun=6 ; default work_week = Mon-Fri
    assert is_work_day("2026-06-22", [0, 1, 2, 3, 4]) is True   # Monday
    assert is_work_day("2026-06-21", [0, 1, 2, 3, 4]) is False  # Sunday


def test_prior_work_day_skips_weekend():
    # firing Monday 02:00 -> prior WORK day is Friday, not Sunday
    assert prior_work_day(datetime(2026, 6, 22, 2, 0), [0, 1, 2, 3, 4]) == "2026-06-19"


def test_prior_work_day_midweek_is_yesterday():
    assert prior_work_day(datetime(2026, 6, 24, 2, 0), [0, 1, 2, 3, 4]) == "2026-06-23"
