import importlib
import tomllib
from pathlib import Path


def test_console_scripts_resolve_to_callables():
    data = tomllib.loads(Path("pyproject.toml").read_text())
    scripts = data["project"]["scripts"]
    assert "org" in scripts
    assert "org-schedule" in scripts
    for entry in scripts.values():
        mod_name, func_name = entry.split(":")
        mod = importlib.import_module(mod_name)
        assert callable(getattr(mod, func_name)), f"{entry} is not callable"


def test_schedule_entry_points_at_scheduler_main():
    data = tomllib.loads(Path("pyproject.toml").read_text())
    assert data["project"]["scripts"]["org-schedule"].startswith("core.scheduler")
