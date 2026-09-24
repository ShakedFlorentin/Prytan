from core.knowledge.codegrapher.__main__ import main

def test_scan_then_query(tmp_path, monkeypatch, capsys):
    (tmp_path / "a.py").write_text("def parse_thing():\n    return 1\n")
    monkeypatch.chdir(tmp_path)
    assert main(["scan", "."]) == 0
    out = capsys.readouterr().out
    assert "graph.json" in out and "nodes" in out
    assert main(["query", "parse"]) == 0
    out = capsys.readouterr().out
    assert "parse_thing" in out

def test_unknown_command_returns_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["frobnicate"]) == 2
