from datetime import datetime
from core.config import Config
from core.scheduler.meetings import run_meeting, MEETING_FACILITATOR


def _fake_run(calls):
    def run(agent_id, task, *, cwd):
        calls.append({"agent": agent_id, "task": task, "cwd": cwd})
        return f"<<{agent_id} output>>"
    return run


def test_run_meeting_dispatches_facilitator_and_writes_inbox(tmp_path):
    cfg = Config.load(tmp_path / "config.yaml")
    calls = []
    out = run_meeting(cfg, "pod-daily", cwd=str(tmp_path),
                      run=_fake_run(calls), now=datetime(2026, 6, 23, 9, 0))
    # facilitator for pod-daily is the governance agent
    assert calls[0]["agent"] == MEETING_FACILITATOR["pod-daily"]
    # the rendered prompt carries the project name from config
    assert cfg.project_name in calls[0]["task"]
    # result written to .inbox dated TODAY (a meeting runs for the current day)
    assert out == tmp_path / ".inbox" / "2026-06-23-pod-daily.md"
    assert out.read_text() == "<<governance output>>"


def test_unknown_meeting_kind_raises(tmp_path):
    cfg = Config.load(tmp_path / "config.yaml")
    import pytest
    with pytest.raises(ValueError):
        run_meeting(cfg, "nope", cwd=str(tmp_path), run=_fake_run([]),
                    now=datetime(2026, 6, 23, 9, 0))
