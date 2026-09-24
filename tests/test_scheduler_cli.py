from datetime import datetime
from core.scheduler.__main__ import main


def _fake_run(order):
    def run(agent_id, task, *, cwd):
        order.append(agent_id)
        return f"<<{agent_id}>>"
    return run


def test_cli_nightly_runs_chain(tmp_path, capsys):
    order = []
    rc = main(["nightly"], cwd=str(tmp_path), run=_fake_run(order),
              now=datetime(2026, 6, 24, 2, 0))
    assert rc == 0
    assert order == ["governance", "reflection", "reliability", "governance"]
    assert (tmp_path / ".inbox" / "2026-06-23-eod-digest.md").exists()


def test_cli_meeting_runs_one_meeting(tmp_path):
    order = []
    rc = main(["meeting", "pod-daily"], cwd=str(tmp_path), run=_fake_run(order),
              now=datetime(2026, 6, 23, 9, 0))
    assert rc == 0
    assert order == ["governance"]
    assert (tmp_path / ".inbox" / "2026-06-23-pod-daily.md").exists()


def test_cli_unknown_command_returns_nonzero(tmp_path, capsys):
    rc = main(["bogus"], cwd=str(tmp_path), run=_fake_run([]),
              now=datetime(2026, 6, 23, 9, 0))
    assert rc != 0
