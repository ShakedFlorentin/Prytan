import pytest
from core.scheduler.templates import load_template, render


def test_render_replaces_known_tokens_only():
    out = render("Day {day} for {project}. Keep this {literal} brace.",
                 day="2026-06-21", project="acme")
    assert "Day 2026-06-21 for acme." in out
    assert "{literal}" in out          # unknown tokens left untouched (brace-safe)


def test_load_nightly_templates_exist():
    for name in ("nightly/summarize", "nightly/reflect",
                 "nightly/reliability", "nightly/prepare"):
        text = load_template(name)
        assert "{day}" in text         # each references the work-day token


def test_load_meeting_templates_exist():
    for name in ("meetings/pod-daily", "meetings/weekly-sprint",
                 "meetings/monthly-milestone"):
        assert load_template(name).strip()


def test_load_missing_template_raises():
    with pytest.raises(FileNotFoundError):
        load_template("nightly/does-not-exist")


# L7: cross-agent dependencies must be a standard, routable section
def test_meeting_templates_have_blocking_inputs_section():
    for name in ("meetings/pod-daily", "meetings/weekly-sprint",
                 "meetings/monthly-milestone"):
        text = load_template(name)
        assert "BLOCKING INPUTS" in text


# L8: the monthly roadmap review must place legal/compliance gating at selection
# time, not implementation time
def test_monthly_milestone_places_legal_gate_at_selection_time():
    text = load_template("meetings/monthly-milestone")
    assert "selection" in text.lower()


# L9: weighted averages must not be able to launder a disqualifying fact — the
# scoring template needs an explicit veto-floor mechanism and a prospective-only
# rule for rubric changes discovered after seeing scores.
def test_scoring_rubric_template_exists_and_has_veto_and_prospective_rules():
    text = load_template("decisions/scoring-rubric")
    low = text.lower()
    assert "veto" in low and "floor" in low
    assert "prospective" in low
    assert "next cycle" in low


# L10: near-tie decisions require a documented tiebreak rationale, not a silent
# pick of the higher raw score.
def test_scoring_rubric_template_requires_tiebreak_rationale():
    text = load_template("decisions/scoring-rubric")
    assert "TIEBREAK RATIONALE" in text
    assert "sensitivity band" in text.lower()
    assert "required" in text.lower()


# L17: gap-report / finding-validation templates must make the validator
# field an extensible, per-project declared list (this project's actual agent
# roster) rather than a hardcoded pair of role names baked into the schema.
def test_finding_validation_template_exists_and_uses_declared_roster():
    text = load_template("decisions/finding-validation")
    low = text.lower()
    assert "validator" in low
    assert "agent_ids" in text or "config.agents" in text
    assert "hardcoded" in low
    assert "verdict" in low


def test_governance_persona_defers_to_finding_validation_template():
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent / "agents" / "_base"
    gov = (base / "governance.md").read_text()
    assert "templates/decisions/finding-validation.md" in gov


# L20: quantitative claims in architecture/spec docs need inline provenance
# tags (modelled/measured/estimate) at the point of citation, and modelled or
# estimated numbers are banned outward without a measurement or "target".
def test_quantitative_claims_template_exists_and_has_provenance_tags():
    text = load_template("decisions/quantitative-claims")
    low = text.lower()
    assert "[modelled]" in low
    assert "[measured" in low
    assert "[estimate]" in low
    assert "target" in low


def test_tech_persona_defers_to_quantitative_claims_template():
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent / "agents" / "_base"
    text = (base / "tech.md").read_text()
    assert "templates/decisions/quantitative-claims.md" in text


def test_product_persona_defers_to_quantitative_claims_template():
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent / "agents" / "_base"
    text = (base / "product.md").read_text()
    assert "templates/decisions/quantitative-claims.md" in text
