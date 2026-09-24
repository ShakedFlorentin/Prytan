You are {facilitator}, recording a VALIDATION verdict on a finding/gap for
{project} ({decision}).

A finding-validation artifact records whether a domain reviewer confirms a
reported finding (bug, gap, vulnerability, defect) as real, before it is acted
on. One rule governs the `validator` field on every such artifact:

## The validator field is a declared, per-project list — never a hardcoded pair

Do NOT hardcode the set of valid validators to a fixed pair or a fixed list of
role names baked into the schema itself (e.g. `{priya, ethan}` or
`{security, qa}`) — a project's real set of domain advisors is whatever this
project's roster actually contains, and a hardcoded enum silently has no slot
for a validator outside it (a security review, a legal review, any
project-authored domain advisor) the day one is needed.

The correct source of truth already exists in this framework: this project's
declared agent roster (`config.agents` / `core.config.agent_ids(config)`,
the same single source of truth `Orchestrator` uses to validate dispatch
routing). The `validator` field's valid values are exactly that declared
list — any agent id in the project's roster may validate a finding in their
own domain, including a project-authored advisor added after this template
was written. Do not fork a second, parallel list of "who's allowed to
validate" anywhere else; if the roster doesn't yet include the right domain
advisor for a finding, that's an onboarding gap (author the advisor — see
`skills/org-onboarding/SKILL.md` step 4), not a reason to force the
validation into a field that wasn't built for it (e.g. stuffing a real
validation into a free-text `evidence` field just because `validator` has no
slot for it — that hides the verdict from any tooling that reads
`validation.verdict` to route or count validated findings).

## Output sections

FINDING (restated as externally-observable behavior, per the execution
protocol) / VALIDATOR (an agent id from this project's declared roster) /
EVIDENCE (source trace the validator actually walked, not the reporter's
prose) / VERDICT (`validated` | `rejected` | `open`) / RATIONALE.
