import json
import yaml
from core.onboarding import (config_set, scan_sources, install_agent,
                             author_agent, wire_hook)

def test_config_set_creates_and_nests(tmp_path):
    config_set(tmp_path, "codegrapher.source_dir", "lib")
    data = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert data["codegrapher"]["source_dir"] == "lib"

def test_scan_multiple_dirs_merges_and_excludes_others(tmp_path):
    (tmp_path / "lib").mkdir(); (tmp_path / "app").mkdir(); (tmp_path / "tests").mkdir()
    (tmp_path / "lib" / "a.py").write_text("def la():\n    return 1\n")
    (tmp_path / "app" / "b.py").write_text("def ab():\n    return 2\n")
    (tmp_path / "tests" / "t.py").write_text("def tt():\n    return 3\n")
    out = scan_sources(tmp_path, ["lib", "app"])
    ids = {n["id"] for n in json.loads(out.read_text())["nodes"]}
    assert "function:a.la" in ids and "function:b.ab" in ids
    assert not any("tt" in i for i in ids)        # tests/ not in the scanned set

def test_install_agent_is_non_destructive(tmp_path):
    # a project that already owns a backend agent
    d = tmp_path / ".claude" / "agents"; d.mkdir(parents=True)
    (d / "backend.md").write_text("MINE")
    install_agent(tmp_path, "backend")            # must NOT clobber
    assert (d / "backend.md").read_text() == "MINE"
    install_agent(tmp_path, "backend", force=True)  # explicit overwrite
    assert (d / "backend.md").read_text() != "MINE"

def test_author_agent_writes_persona_and_registers(tmp_path):
    f = author_agent(tmp_path, "rtl", "Rtl — hardware",
                     "RTL/Verilog specialist", "You review RTL.", tools=["Read", "Grep"])
    assert f.exists()
    text = f.read_text()
    assert "name: rtl" in text and "RTL/Verilog specialist" in text and "- Grep" in text
    cfg = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert cfg["agents"]["rtl"] == "Rtl — hardware"

def test_wire_hook_merges_into_settings(tmp_path):
    wire_hook(tmp_path)
    s = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert any("codegrapher" in json.dumps(e) for e in s["hooks"]["PreToolUse"])

def test_scan_sources_with_books_dir_merges_book_nodes(tmp_path):
    """scan_sources with books_dir must include book: nodes in the written graph."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.py").write_text("def greet():\n    return 'hi'\n")
    books = tmp_path / "books"
    (books / "engineering").mkdir(parents=True)
    (books / "engineering" / "input-validation.md").write_text(
        "---\ntitle: Input Validation\nchapter: security\n"
        "explains: sanitize_input\n---\nAlways validate.\n")
    out = scan_sources(tmp_path, ["src"], books_dir=books)
    data = json.loads(out.read_text())
    ids = {n["id"] for n in data["nodes"]}
    # Code node from src
    assert "function:hello.greet" in ids
    # Book node from books_dir
    assert any(i.startswith("book:") for i in ids), f"no book: node in {ids}"
