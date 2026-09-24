import json
from core.knowledge.codegrapher.graph import build_graph, write_graph
from core.knowledge.codegrapher.query import query_graph


def _mk(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "m.py").write_text("def sanitize_input(x):\n    return x\n")
    books = tmp_path / "books" / "engineering"
    books.mkdir(parents=True)
    (books / "iv.md").write_text(
        "---\ntitle: Input Validation\nchapter: security\n"
        "explains:\n  - sanitize_input\n---\nValidate at the boundary.\n")
    return src, tmp_path / "books"


def test_build_graph_without_books_is_unchanged(tmp_path):
    src, _ = _mk(tmp_path)
    g = build_graph(src)                      # no books_dir -> code only
    assert all(not n["id"].startswith("book:") for n in g["nodes"])


def test_build_graph_merges_books(tmp_path):
    src, books = _mk(tmp_path)
    g = build_graph(src, books_dir=books)
    ids = {n["id"] for n in g["nodes"]}
    assert "function:m.sanitize_input" in ids   # code node
    assert "book:engineering" in ids            # book node
    assert any(e["kind"] == "explains" for e in g["edges"])


def test_query_finds_book_page(tmp_path):
    src, books = _mk(tmp_path)
    g = build_graph(src, books_dir=books)
    hits = query_graph(g, "input validation")
    assert any(n["kind"] == "page" and n["name"] == "Input Validation" for n in hits)


def test_write_graph_accepts_books_dir(tmp_path):
    src, books = _mk(tmp_path)
    out = write_graph(src, tmp_path / "g.json", books_dir=books)
    data = json.loads(out.read_text())
    assert any(n["id"] == "book:engineering" for n in data["nodes"])
