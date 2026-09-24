from core.onboarding_cli import main

def test_cli_scan_and_author(tmp_path, monkeypatch):
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "x.py").write_text("def f():\n    return 1\n")
    monkeypatch.chdir(tmp_path)
    assert main(["scan", "lib"]) == 0
    assert (tmp_path / "codegrapher_out" / "graph.json").exists()
    assert main(["install-agent", "backend"]) == 0
    assert (tmp_path / ".claude" / "agents" / "backend.md").exists()
    assert main(["config-set", "project_name", "acme"]) == 0
    import yaml
    assert yaml.safe_load((tmp_path / "config.yaml").read_text())["project_name"] == "acme"

def test_cli_unknown_returns_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["bogus"]) == 2


def test_cli_author_agent_from_stdin(tmp_path, monkeypatch):
    import io
    import sys
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO("You review RTL designs."))
    assert main(["author-agent", "rtl", "Rtl", "RTL specialist"]) == 0
    f = tmp_path / ".claude" / "agents" / "rtl.md"
    assert f.exists() and "You review RTL designs." in f.read_text()
