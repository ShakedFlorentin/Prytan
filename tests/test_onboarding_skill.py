from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

def test_command_invokes_skill():
    cmd = (REPO / "commands" / "org-init.md").read_text()
    assert "org-onboarding" in cmd

def test_skill_documents_the_procedure_and_primitives():
    s = (REPO / "skills" / "org-onboarding" / "SKILL.md").read_text()
    # the four decisions Claude must make
    for token in ["analyze", "source", "roster", "author"]:
        assert token.lower() in s.lower()
    # references the primitives it must call
    for prim in ["onboarding_cli", "scan", "install-agent", "author-agent", "wire-hook"]:
        assert prim in s
    # non-destructive + idempotent are stated
    assert "non-destructive" in s.lower() or "do not clobber" in s.lower()


def test_skill_uses_plugin_root_pattern():
    from pathlib import Path
    text = Path("skills/org-onboarding/SKILL.md").read_text()
    # primitives run from the plugin root so no pip install is required
    assert "${CLAUDE_PLUGIN_ROOT}" in text
    assert "PYTHONPATH" in text
    # the bare, install-dependent form must be gone
    assert "python3 -m core.onboarding_cli" not in text.replace(
        'PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m core.onboarding_cli', "")


def test_skill_mentions_books_indexing():
    from pathlib import Path
    text = Path("skills/org-onboarding/SKILL.md").read_text().lower()
    assert "book" in text


def test_books_readme_exists_and_is_license_clean():
    from pathlib import Path
    text = Path("books/README.md").read_text().lower()
    assert "license" in text                # the BYO license caveat is documented
    assert "explains" in text               # documents the frontmatter contract
