from core.knowledge.codegrapher.query import query_graph

def test_query_ranks_name_over_doc():
    g = {"nodes": [
        {"id": "function:a.parse", "kind": "function", "name": "parse", "file": "a.py", "line": 1, "doc": ""},
        {"id": "function:b.run", "kind": "function", "name": "run", "file": "b.py", "line": 1, "doc": "calls parse"},
        {"id": "function:c.x", "kind": "function", "name": "x", "file": "c.py", "line": 1, "doc": "unrelated"},
    ], "edges": []}
    hits = query_graph(g, "parse")
    assert hits[0]["id"] == "function:a.parse"   # name match ranks first
    assert any(h["id"] == "function:b.run" for h in hits)  # doc match included
    assert all(h["id"] != "function:c.x" for h in hits)    # no match excluded
