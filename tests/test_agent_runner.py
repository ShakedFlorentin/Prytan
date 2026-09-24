import json
from core.runtime.agent_runner import run_agent
from core.runtime.agent_runner import run_agent_metered, AgentResult

class _FakeCompleted:
    def __init__(self, stdout): self.stdout = stdout; self.returncode = 0

def test_run_agent_builds_command_and_returns_text():
    captured = {}
    def fake_runner(cmd, input=None, capture_output=None, text=None, cwd=None):
        captured["cmd"] = cmd
        captured["input"] = input
        return _FakeCompleted(json.dumps({"result": "hello from neo"}))
    out = run_agent("neo", "what is up?", cwd="/tmp/proj", runner=fake_runner)
    assert out == "hello from neo"
    assert captured["cmd"][:4] == ["claude", "-p", "--agent", "neo"]
    assert "--output-format" in captured["cmd"]
    assert captured["input"] == "what is up?"

def test_run_agent_falls_back_to_raw_stdout_when_not_json():
    def fake_runner(cmd, **kw): return _FakeCompleted("plain text reply")
    out = run_agent("neo", "hi", cwd="/tmp", runner=fake_runner)
    assert out == "plain text reply"


class _FakeProc:
    def __init__(self, stdout): self.stdout = stdout; self.returncode = 0

def test_run_agent_metered_returns_text_and_usage():
    import json as _j
    def fake(cmd, **kw):
        return _FakeProc(_j.dumps({"result": "done", "usage": {"output_tokens": 12}}))
    r = run_agent_metered("backend", "do x", cwd="/tmp", runner=fake)
    assert isinstance(r, AgentResult)
    assert r.text == "done"
    assert r.usage["output_tokens"] == 12

def test_write_mode_uses_perms_file_not_allowedtools():
    captured = {}
    def fake(cmd, **kw):
        captured["cmd"] = cmd
        return _FakeProc('{"result":"ok"}')
    run_agent_metered("backend", "edit", cwd="/tmp", write=True,
                      perms_file="/tmp/.perms.json", runner=fake)
    assert "--settings" in captured["cmd"]
    assert "/tmp/.perms.json" in captured["cmd"]
    assert "--allowedTools" not in captured["cmd"]

def test_scan_mode_passes_model():
    captured = {}
    def fake(cmd, **kw):
        captured["cmd"] = cmd
        return _FakeProc('{"result":"ok"}')
    run_agent_metered("security", "grep", cwd="/tmp", model="claude-haiku-4-5", runner=fake)
    assert "--model" in captured["cmd"] and "claude-haiku-4-5" in captured["cmd"]
