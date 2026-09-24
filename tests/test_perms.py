import json
from core.runtime.perms import write_perms_file, write_scoped_perms_file, agent_log_dir


def test_perms_scopes_writes_to_org_dirs(tmp_path):
    p = write_perms_file(tmp_path, [".inbox", ".handoffs"])
    assert p.exists()
    # perms file lives OUTSIDE the writable org dirs (no self-escalation)
    assert ".agent-runtime" in str(p) and "/.logs/" not in str(p)
    data = json.loads(p.read_text())
    perms = data["permissions"]
    allow = perms["allow"]
    assert "Write(.inbox/**)" in allow and "Edit(.handoffs/**)" in allow
    assert "Read(**)" in allow
    assert "deny" not in perms   # no global deny (deny beats allow in Claude Code)


def test_agent_log_dir_is_nested_under_dot_logs():
    # matches templates/nightly/summarize.md's expected `.logs/*/{day}-*.md` layout
    assert agent_log_dir("security") == ".logs/security"


# L2/L5: every dispatch — including read-only advisors — always gets a
# scoped-writable journal + shared memory, independent of deliverable scoping.
def test_scoped_perms_always_grants_own_log_dir_and_memory(tmp_path):
    p = write_scoped_perms_file(tmp_path, "security")   # no deliverable_dirs at all
    allow = json.loads(p.read_text())["permissions"]["allow"]
    assert "Write(.logs/security/**)" in allow and "Edit(.logs/security/**)" in allow
    assert "Write(memory/**)" in allow


def test_scoped_perms_deliverable_dirs_are_additive_not_substitutive(tmp_path):
    p = write_scoped_perms_file(tmp_path, "backend", deliverable_dirs=[".handoffs"])
    allow = json.loads(p.read_text())["permissions"]["allow"]
    # deliverable scope granted...
    assert "Write(.handoffs/**)" in allow
    # ...but the always-writable journal/memory paths are still present, not dropped
    assert "Write(.logs/backend/**)" in allow
    assert "Write(memory/**)" in allow


def test_scoped_perms_isolates_one_agents_journal_from_anothers(tmp_path):
    p = write_scoped_perms_file(tmp_path, "backend")
    allow = json.loads(p.read_text())["permissions"]["allow"]
    assert "Write(.logs/backend/**)" in allow
    assert "Write(.logs/security/**)" not in allow
