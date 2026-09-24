from core.knowledge.codegrapher.graph import build_graph, write_graph

def test_build_graph_extracts_modules_functions_classes(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "m.py").write_text(
        '"""mod doc."""\n'
        "import os\n"
        "def greet(name):\n"
        '    "say hi"\n'
        "    return name\n"
        "class Thing:\n"
        "    pass\n"
    )
    g = build_graph(tmp_path)
    ids = {n["id"] for n in g["nodes"]}
    assert "module:pkg.m" in ids
    assert "function:pkg.m.greet" in ids
    assert "class:pkg.m.Thing" in ids
    kinds = {(e["src"], e["dst"], e["kind"]) for e in g["edges"]}
    assert ("module:pkg.m", "function:pkg.m.greet", "contains") in kinds
    assert any(e["kind"] == "imports" and "os" in e["dst"] for e in g["edges"])

def test_write_graph_emits_json(tmp_path):
    (tmp_path / "a.py").write_text("def f():\n    return 1\n")
    out = write_graph(tmp_path, tmp_path / "out" / "graph.json")
    assert out.exists()
    import json
    data = json.loads(out.read_text())
    assert "nodes" in data and "edges" in data
