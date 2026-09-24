from pathlib import Path
from core.config import Config, DEFAULTS

def test_load_missing_file_returns_defaults():
    cfg = Config.load(Path("/nonexistent/config.yaml"))
    assert cfg.project_name == DEFAULTS["project_name"]
    assert cfg.interface == "cli"
    assert cfg.agents["chief_of_staff"] == "Atlas"
    assert len(cfg.agents) == 16

def test_load_merges_overrides(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(
        "project_name: acme\n"
        "agents:\n"
        "  chief_of_staff: Atlas\n"
    )
    cfg = Config.load(p)
    assert cfg.project_name == "acme"            # overridden
    assert cfg.agents["chief_of_staff"] == "Atlas"  # overridden
    assert cfg.agents["governance"] == "Marcus"     # default preserved (deep merge)
    assert cfg.interface == "cli"                    # default preserved


def test_schedule_defaults_present(tmp_path):
    from core.config import Config
    cfg = Config.load(tmp_path / "config.yaml")  # no file -> defaults
    assert cfg.schedule["summarize"] == "02:00"
    assert cfg.schedule["reflection"] == "03:00"
    assert cfg.schedule["reliability"] == "04:00"
    assert cfg.schedule["morning_prepare"] == "05:00"


def test_schedule_is_user_overridable(tmp_path):
    import yaml
    from core.config import Config
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({"schedule": {"summarize": "01:30"}}))
    cfg = Config.load(p)
    assert cfg.schedule["summarize"] == "01:30"        # overridden
    assert cfg.schedule["reflection"] == "03:00"       # default preserved (deep-merge)


# C1 regression: _deep_merge must deep-copy nested dicts so configs are independent
def test_agents_dicts_are_independent_across_loads(tmp_path):
    from core.config import Config, DEFAULTS
    p1 = tmp_path / "c1.yaml"
    p2 = tmp_path / "c2.yaml"
    p1.write_text("")
    p2.write_text("")
    cfg1 = Config.load(p1)
    cfg2 = Config.load(p2)
    assert cfg1.agents is not cfg2.agents, "agents dicts must not be the same object"


def test_mutating_loaded_config_does_not_poison_defaults(tmp_path):
    from core.config import Config, DEFAULTS
    p = tmp_path / "config.yaml"
    p.write_text("")
    cfg = Config.load(p)
    original_backend = DEFAULTS["agents"]["backend"]
    cfg.agents["backend"] = "ZZZ"
    # freshly loaded config must still have the original default value
    cfg2 = Config.load(p)
    assert cfg2.agents["backend"] == original_backend
    # module-level DEFAULTS must not be mutated
    assert DEFAULTS["agents"]["backend"] == original_backend


def test_books_default_empty(tmp_path):
    from core.config import Config
    cfg = Config.load(tmp_path / "config.yaml")
    assert cfg.books == {}


def test_shelves_for_returns_role_books(tmp_path):
    import yaml
    from core.config import Config, shelves_for
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({"books": {"security": ["owasp"], "qa": ["testing"]}}))
    cfg = Config.load(p)
    assert shelves_for(cfg, "security") == ["owasp"]
    assert shelves_for(cfg, "qa") == ["testing"]
    assert shelves_for(cfg, "backend") == []      # no shelf -> empty


# L4: explicit-routing table (Orchestrator validates dispatch ids against this)
def test_agent_ids_maps_base_roles_to_dispatch_ids(tmp_path):
    from core.config import Config, agent_ids
    cfg = Config.load(tmp_path / "config.yaml")   # defaults, no authored agents
    ids = agent_ids(cfg)
    # base-role keys that diverge from their dispatch id are mapped, not passed through
    assert "atlas" in ids and "chief_of_staff" not in ids
    assert "tech" in ids and "tech_architecture" not in ids
    # roles whose config key already IS the dispatch id pass through unchanged
    assert "backend" in ids and "security" in ids


def test_agent_ids_includes_project_authored_agents(tmp_path):
    import yaml
    from core.config import Config, agent_ids
    p = tmp_path / "config.yaml"
    # core.onboarding.author_agent registers authored agents as agents.<agent_id>
    p.write_text(yaml.safe_dump({"agents": {"rtl": "Rtl — hardware"}}))
    cfg = Config.load(p)
    assert "rtl" in agent_ids(cfg)
