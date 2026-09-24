from core.knowledge.codegrapher.books import parse_frontmatter, index_books


def test_parse_frontmatter_splits_meta_and_body():
    text = "---\ntitle: Input Validation\nchapter: security\n---\nBody here.\n"
    meta, body = parse_frontmatter(text)
    assert meta["title"] == "Input Validation"
    assert meta["chapter"] == "security"
    assert body.strip() == "Body here."


def test_parse_frontmatter_no_frontmatter():
    meta, body = parse_frontmatter("Just body, no meta.\n")
    assert meta == {}
    assert body.strip() == "Just body, no meta."


def test_index_books_builds_book_chapter_page_nodes(tmp_path):
    b = tmp_path / "books" / "engineering"
    b.mkdir(parents=True)
    (b / "input-validation.md").write_text(
        "---\ntitle: Input Validation\nchapter: security\n"
        "explains:\n  - sanitize_input\n---\nAlways validate at the boundary.\n")
    g = index_books(tmp_path / "books")
    ids = {n["id"] for n in g["nodes"]}
    assert "book:engineering" in ids
    assert "chapter:engineering.security" in ids
    page = next(n for n in g["nodes"] if n["kind"] == "page")
    assert page["name"] == "Input Validation"
    assert "validate at the boundary" in page["doc"].lower()
    kinds = {n["kind"] for n in g["nodes"]}
    assert {"book", "chapter", "page"} <= kinds


def test_index_books_emits_contains_and_explains_edges(tmp_path):
    b = tmp_path / "books" / "engineering"
    b.mkdir(parents=True)
    (b / "p.md").write_text(
        "---\ntitle: P\nchapter: security\nexplains:\n  - sanitize_input\n---\nx\n")
    g = index_books(tmp_path / "books")
    ekinds = {e["kind"] for e in g["edges"]}
    assert "contains" in ekinds and "explains" in ekinds
    explains = [e for e in g["edges"] if e["kind"] == "explains"]
    assert explains[0]["dst"] == "sanitize_input"


def test_index_books_empty_dir_is_safe(tmp_path):
    (tmp_path / "books").mkdir()
    g = index_books(tmp_path / "books")
    assert g == {"nodes": [], "edges": []}


def test_index_books_missing_dir_is_safe(tmp_path):
    g = index_books(tmp_path / "nope")
    assert g == {"nodes": [], "edges": []}


def test_index_books_scalar_explains_produces_one_edge(tmp_path):
    """A scalar `explains: sanitize_input` must produce exactly ONE explains edge,
    not 13 single-character edges."""
    b = tmp_path / "books" / "engineering"
    b.mkdir(parents=True)
    (b / "sanitize.md").write_text(
        "---\ntitle: Sanitize Input\nchapter: security\n"
        "explains: sanitize_input\n---\nBody.\n")
    g = index_books(tmp_path / "books")
    explains = [e for e in g["edges"] if e["kind"] == "explains"]
    assert len(explains) == 1, f"expected 1 explains edge, got {len(explains)}: {explains}"
    assert explains[0]["dst"] == "sanitize_input"
