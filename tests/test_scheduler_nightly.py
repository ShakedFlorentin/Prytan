from datetime import datetime
from core.config import Config
from core.scheduler.nightly import run_nightly
from core.scheduler.skills_store import load_lessons

DIGEST_SENTINEL = "DIGEST-SENTINEL-7Q"


def _recording_run(order, calls=None):
    """Return a fake run() that records (agent, task) tuples.

    The first governance call (summarize) returns DIGEST_SENTINEL so tests can
    assert it propagates into subsequent prompts.  Call order distinguishes the
    two governance invocations.
    """
    governance_calls = [0]

    def run(agent_id, task, *, cwd):
        order.append(agent_id)
        if calls is not None:
            calls.append((agent_id, task))
        if agent_id == "governance":
            governance_calls[0] += 1
            if governance_calls[0] == 1:
                # summarize step -> return unique sentinel
                return DIGEST_SENTINEL
            # morning-prepare step
            return "<<governance-prepare output>>"
        if agent_id == "reflection":
            # the reflect step must receive the digest sentinel in its prompt
            assert DIGEST_SENTINEL in task
            return "Parameterize schedules by config.\nKeep cron jobs idempotent."
        if agent_id == "reliability":
            return "All agent frontmatter valid. NEEDS-REVIEW: none."
        return f"<<{agent_id} output>>"
    return run


def test_nightly_runs_in_order_and_processes_prior_day(tmp_path):
    cfg = Config.load(tmp_path / "config.yaml")
    order = []
    # fire Wednesday 02:00 -> must process Tuesday 2026-06-23
    res = run_nightly(cfg, cwd=str(tmp_path), run=_recording_run(order),
                      now=datetime(2026, 6, 24, 2, 0))
    # dependency order: summarize(governance) -> reflection -> reliability -> prepare(governance)
    assert order == ["governance", "reflection", "reliability", "governance"]
    assert res["day"] == "2026-06-23"


def test_nightly_writes_all_artifacts_for_prior_day(tmp_path):
    cfg = Config.load(tmp_path / "config.yaml")
    res = run_nightly(cfg, cwd=str(tmp_path), run=_recording_run([]),
                      now=datetime(2026, 6, 24, 2, 0))
    digest = tmp_path / ".inbox" / "2026-06-23-eod-digest.md"
    health = tmp_path / ".logs" / "2026-06-23-health.md"
    prepare = tmp_path / ".inbox" / "2026-06-23-prepare.md"
    assert digest.exists() and health.exists() and prepare.exists()
    assert res["digest"] == digest and res["health"] == health and res["prepare"] == prepare
    # reflection persisted design-agnostic lessons to the skills store
    lessons = [x["lesson"] for x in load_lessons(tmp_path)]
    assert "Parameterize schedules by config." in lessons
    assert all(x["day"] == "2026-06-23" for x in load_lessons(tmp_path))


# C2 regression: Monday 02:00 must roll up Friday (prior work day, not prior calendar day)
def test_nightly_monday_rolls_up_friday(tmp_path):
    cfg = Config.load(tmp_path / "config.yaml")
    order = []
    # fire Monday 2026-06-22 02:00 -> must process Friday 2026-06-19
    res = run_nightly(cfg, cwd=str(tmp_path), run=_recording_run(order),
                      now=datetime(2026, 6, 22, 2, 0))
    assert res["day"] == "2026-06-19"
    assert (tmp_path / ".inbox" / "2026-06-19-eod-digest.md").exists()


# I1 regression: sentinel propagates from summarize into reflection AND prepare tasks
def test_nightly_sentinel_propagates_to_reflection_and_prepare(tmp_path):
    cfg = Config.load(tmp_path / "config.yaml")
    order = []
    calls = []
    run_nightly(cfg, cwd=str(tmp_path), run=_recording_run(order, calls),
                now=datetime(2026, 6, 24, 2, 0))
    # collect tasks by agent in call order
    governance_tasks = [task for agent, task in calls if agent == "governance"]
    reflection_tasks = [task for agent, task in calls if agent == "reflection"]
    # sentinel must appear in the reflection prompt (2nd overall call, 1st reflection)
    assert DIGEST_SENTINEL in reflection_tasks[0]
    # sentinel must also appear in the morning-prepare prompt (2nd governance call)
    assert DIGEST_SENTINEL in governance_tasks[1]
