from core.config import Config
from core.runtime.orchestrator import Orchestrator
from core.runtime.agent_runner import AgentResult

def _res(text): return AgentResult(text=text, usage={"output_tokens": 1}, model="claude-sonnet-4-6")

def test_no_markers_returns_neo_reply(tmp_path):
    cfg = Config.load("/nonexistent")
    calls = []
    def fake(agent_id, task, *, cwd, write=False, model=None, perms_file=None):
        calls.append(agent_id)
        return _res("just a chat answer")
    orch = Orchestrator(cfg, cwd=str(tmp_path), run=fake)
    assert orch.handle("hi") == "just a chat answer"
    assert calls == ["atlas"]            # only neo ran, no dispatch

def test_dispatch_runs_agent_then_relays(tmp_path):
    cfg = Config.load("/nonexistent")
    seq = iter([
        _res("on it.\n@@RUN: backend :: audit auth"),   # neo turn 1: dispatch
        _res("backend findings: looks ok"),              # backend run
        _res("Summary: auth looks ok."),                 # neo relay
    ])
    seen = []
    def fake(agent_id, task, *, cwd, write=False, model=None, perms_file=None):
        seen.append((agent_id, write))
        return next(seq)
    orch = Orchestrator(cfg, cwd=str(tmp_path), run=fake)
    out = orch.handle("check auth")
    assert out == "Summary: auth looks ok."
    assert seen[0][0] == "atlas" and seen[1][0] == "backend" and seen[2][0] == "atlas"
    # ledger written
    assert (tmp_path / ".logs" / "usage.tsv").exists()


# L4: unrouted/unknown dispatch ids must fail loudly, never be silently forwarded
def test_unrouted_dispatch_id_is_rejected_not_silently_run(tmp_path):
    cfg = Config.load("/nonexistent")
    seq = iter([
        _res("on it.\n@@RUN: totally_made_up_agent :: do the thing"),  # neo dispatches junk
        _res("Summary: could not route."),                              # neo relay
    ])
    seen = []
    def fake(agent_id, task, *, cwd, write=False, model=None, perms_file=None):
        seen.append(agent_id)
        return next(seq)
    orch = Orchestrator(cfg, cwd=str(tmp_path), run=fake)
    orch.handle("do something vague")
    # the bogus agent id was never actually invoked — only atlas ran (dispatch, then relay)
    assert seen == ["atlas", "atlas"]


# L2/L5: even a read-only (non-write) dispatch gets a perms_file scoped to its own
# journal/memory — it is never forced onto the bare Read/Glob/Grep allowedTools path.
def test_readonly_dispatch_still_gets_a_scoped_perms_file(tmp_path):
    cfg = Config.load("/nonexistent")
    seq = iter([
        _res("on it.\n@@RUN: security :: audit the auth flow"),
        _res("security findings: looks ok"),
        _res("Summary: auth looks ok."),
    ])
    captured = {}
    def fake(agent_id, task, *, cwd, write=False, model=None, perms_file=None):
        if agent_id == "security":
            captured["perms_file"] = perms_file
            captured["write"] = write
        return next(seq)
    orch = Orchestrator(cfg, cwd=str(tmp_path), run=fake)
    orch.handle("check auth")
    assert captured["write"] is False
    assert captured["perms_file"] is not None   # scoped write access, not None
