from pathlib import Path
from core.config import DEFAULTS, ROLE_TO_AGENT_ID as ROLE_TO_ID

BASE = Path(__file__).resolve().parent.parent / "agents" / "_base"
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "agent-template.md"

def test_every_role_has_a_persona_file():
    base = Path(__file__).resolve().parent.parent / "agents" / "_base"
    assert set(ROLE_TO_ID) == set(DEFAULTS["agents"])   # mapping covers all 16 roles
    for role, pid in ROLE_TO_ID.items():
        f = base / f"{pid}.md"
        assert f.exists(), f"missing persona: {pid}.md"
        text = f.read_text()
        assert "name:" in text and "description:" in text and "tools:" in text


# L8: legal's charter must state the gate belongs at selection time, not later
def test_legal_persona_states_selection_time_gate():
    base = Path(__file__).resolve().parent.parent / "agents" / "_base"
    text = (base / "legal.md").read_text().lower()
    assert "selection" in text and "implementation" in text


# L6: the dispatch protocol doc must encode the model-tier routing rule
def test_atlas_persona_documents_model_tier_rule():
    base = Path(__file__).resolve().parent.parent / "agents" / "_base"
    text = (base / "atlas.md").read_text().lower()
    assert "fully-specified" in text
    assert "adjudicate" in text or "novel-judgment" in text


# L9/L10: governance (owns decision frameworks) and product (owns prioritization)
# must point at the single shared scoring-rubric template, not fork their own
# parallel scoring logic.
def test_governance_and_product_defer_to_shared_scoring_rubric():
    base = Path(__file__).resolve().parent.parent / "agents" / "_base"
    gov = (base / "governance.md").read_text()
    prod = (base / "product.md").read_text()
    assert "templates/decisions/scoring-rubric.md" in gov
    assert "templates/decisions/scoring-rubric.md" in prod
    assert "veto" in gov.lower()


# L11: review-capable personas (qa, security) must distinguish a read review
# (re-reading) from a run review (executing) and refuse to bless a fix as
# closing a finding on a read review alone. The agent-template must carry the
# same rule so future project-authored review roles inherit it.
def test_review_personas_distinguish_read_review_from_run_review():
    for name in ("qa", "security"):
        text = (BASE / f"{name}.md").read_text().lower()
        assert "read review" in text and "run review" in text
        assert "bless" in text
    tpl = TEMPLATE.read_text().lower()
    assert "read review" in tpl and "run review" in tpl


# L12: execution-protocol personas must restate a finding as externally
# observable behavior before fixing, and validate against that restatement
# rather than the finding's prose or an internally-named signal.
def test_execution_protocol_personas_restate_finding_before_fixing():
    for name in ("content", "ux", "qa", "backend", "build", "growth",
                 "frontend", "devops"):
        text = (BASE / f"{name}.md").read_text()
        assert "EXTERNALLY-OBSERVABLE BEHAVIOR" in text
        assert "step-0 restatement" in text


# L13: any persona that might propose a NEW verification/detection check as a
# deliverable must test it against a negative control before recommending it.
def test_review_personas_require_negative_control_for_new_checks():
    for name in ("qa", "security"):
        text = (BASE / f"{name}.md").read_text().lower()
        assert "negative control" in text
    tpl = TEMPLATE.read_text().lower()
    assert "negative control" in tpl


# L14: atlas's dispatch protocol must default to blind-parallel review by 2+
# domain lenses for security/correctness-stakes decisions, not a single or
# sequential reviewer.
def test_atlas_persona_requires_blind_parallel_review_for_stakes_decisions():
    text = (BASE / "atlas.md").read_text().lower()
    assert "blind-parallel" in text or "blind parallel" in text
    assert "independently" in text


# L15: atlas's synthesis step (its "relay another agent's findings" role) must
# be chartered to re-verify against source, not transcribe. The shared
# agent-template must carry the same rule for any project-authored relay role.
def test_atlas_persona_requires_synthesis_reverification_not_transcription():
    text = (BASE / "atlas.md").read_text().lower()
    assert "verification pass" in text and "transcription pass" in text
    tpl = TEMPLATE.read_text().lower()
    assert "re-verify" in tpl and "transcribe" in tpl


# L16: gaining a new detection capability mid-task that finds a real defect
# must trigger a full sweep of the artifact, not just a fix at the one site.
def test_new_detection_capability_triggers_full_sweep():
    for name in ("security", "backend"):
        text = (BASE / f"{name}.md").read_text().lower()
        assert "new detection capability" in text
        assert "sweep" in text
    tpl = TEMPLATE.read_text().lower()
    assert "new detection capability" in tpl and "sweep" in tpl


# L18: a refactor that splits/duplicates a previously-single condition
# invalidates existing checks scoped to the original — "still green" after
# such a refactor is not evidence every resulting copy is still covered.
def test_refactor_split_condition_requires_coverage_audit():
    for name in ("qa", "security", "backend"):
        text = (BASE / f"{name}.md").read_text().lower()
        assert "split" in text and "duplicat" in text
        assert "still green" in text
        assert "audit" in text
    tpl = TEMPLATE.read_text().lower()
    assert "split" in tpl and "duplicat" in tpl
    assert "still green" in tpl


# L19: a heuristic-derived classifier that emits a CONFIDENCE label is an
# unearned claim unless validated against ground truth — a confident WRONG
# answer is a worse failure mode than staying silent.
def test_confidence_labels_require_validation_not_defensible_logic():
    for name in ("qa", "security", "backend"):
        text = (BASE / f"{name}.md").read_text().lower()
        assert "confidence label" in text
        assert "unearned" in text
        assert "unvalidated" in text
        assert "silen" in text  # silent / silence
    tpl = TEMPLATE.read_text().lower()
    assert "confidence label" in tpl and "unearned" in tpl


# L20: tech (owns architecture docs) and product (cites architecture numbers
# outward) must defer to the shared quantitative-claims provenance template
# rather than forking their own rule about modelled-vs-measured numbers.
def test_tech_and_product_defer_to_quantitative_claims_template():
    tech = (BASE / "tech.md").read_text()
    prod = (BASE / "product.md").read_text()
    assert "templates/decisions/quantitative-claims.md" in tech
    assert "templates/decisions/quantitative-claims.md" in prod
    assert "modelled" in tech.lower()
