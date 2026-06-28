# Door Types — Decision Classification

Before recording any decision, classify it by door type. This determines who acts on it.

---

## two_way

**Definition:** Reversible, internal, execution-level call. The agent owns it.

- Can be undone if wrong
- Affects only internal state, code, or files
- No outward-facing consequences
- No money, legal, or customer impact

**What to do:** Decide, record in the decision ledger with `--door-type two_way`,
and move on. This never reaches the human.

**Examples:**
- Choosing between two internal refactoring approaches
- Selecting a library version for a new internal module
- Restructuring internal documentation
- Assigning a task to one agent vs. another

---

## one_way

**Definition:** Irreversible, outward-facing, or carries money/legal/customer risk.
The human decides.

Includes — **any action that involves:**
- Publishing content to a live audience
- Spending money or committing budget
- Deleting data permanently
- Deploying to an external/production environment
- Sending email to customers or external parties
- Legal commitments or external contracts

**What to do:** Stop. Write a handoff to the chief-of-staff describing the action,
the risk, and your recommendation. Record in the decision ledger with
`--door-type one_way`. Do not act until the human approves.

**Examples:**
- Publishing a blog post or announcement
- Sending a customer notification email
- Dropping a production database table
- Deploying a breaking API change to production
- Purchasing a third-party service

---

## strategic_fork

**Definition:** A direction or roadmap change that affects the product's trajectory.
The human decides.

**What to do:** Write a proposal (use `.agent-templates/proposal.md`) and send it
to the coordinator. Record in the decision ledger with `--door-type strategic_fork`.
Do not act; the coordinator surfaces it to the human.

**Examples:**
- Abandoning a feature mid-build for a new approach
- Entering a new market or targeting a new user segment
- Changing the product's primary value proposition
- Deciding to sunset a major feature

---

## The Rule of Doubt

**When unsure, it is NOT two_way.**

If you find yourself wondering "is this two_way or one_way?", it is one_way.
Escalate. The cost of an unnecessary escalation is low. The cost of a unilateral
one_way action is high.

---

## Nightly Lint

A nightly lint job checks two_way decisions in the ledger whose `title` or
`resolution` contains any of these keywords:

```
publish  spend  delete  deploy  email  customer  external  legal  money  irreversible
```

If found, the lint flags them for human review. This is a safety net, not a substitute
for correct classification.
