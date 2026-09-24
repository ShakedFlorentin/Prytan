import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

def test_manifest_is_valid_and_references_resolve():
    m = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text())
    assert m["name"] and m["version"] and m["description"]
    # component dirs/files the manifest points at must exist
    assert (REPO / "commands" / "org-init.md").exists()
    assert (REPO / "skills" / "org-onboarding" / "SKILL.md").exists()
    assert (REPO / "agents" / "_base").is_dir()
    assert (REPO / "hooks" / "hooks.json").exists()
    assert (REPO / "templates" / "agent-template.md").exists()

def test_hooks_declare_codegrapher_pretooluse():
    h = json.loads((REPO / "hooks" / "hooks.json").read_text())
    assert "codegrapher" in json.dumps(h)


# L1: authoring vs advisory must be a decision every authored charter makes explicit
def test_agent_template_asks_for_role_type():
    t = (REPO / "templates" / "agent-template.md").read_text()
    assert "role_type" in t
    assert "authoring" in t.lower() and "advisory" in t.lower()


# L3: forbidden git write commands + the stated alternative are standard in every charter
def test_agent_template_has_hard_rules_git_block():
    t = (REPO / "templates" / "agent-template.md").read_text()
    for cmd in ("git add", "git commit", "git push", "git branch",
               "git checkout", "git stash", "git tag"):
        assert cmd in t, f"missing forbidden command: {cmd}"
    assert "human owns git" in t.lower()
