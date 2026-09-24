---
name: circle-meeting
description: Run an ad hoc multi-agent design review or debate — propose, react, respond, close with numbered decisions — with any topic and any panel of 2+ named agents from the project's roster, triggered directly from the main session mid-conversation. Use when the user asks to "send <agents> to a circle meeting", wants a design/technical review or debate between two or more named agents (e.g. ux + frontend on a UI direction, backend + security on an auth design), or asks for a cross-domain discussion that isn't a scheduled cadence meeting.
version: 1.0.0
---

# Circle meeting (ad hoc multi-agent review)

## When to use
The user names two or more agents from the project's roster (base agents in
`agents/_base/`, enabled via `config.agents`, plus any project-authored domain
agents added per `skills/org-onboarding/SKILL.md` step 4) and wants them to
discuss, debate, or jointly plan something — a design direction, a technical
trade-off, a cross-domain proposal. This is the main session's own tool for
spinning up a review on demand; it does not require Atlas, the scheduler, or a
fixed cadence.

**Not this skill:**
- Scheduled cadence meetings (fixed facilitator, cron-triggered via
  `core.scheduler.meetings.run_meeting`, templated in `templates/meetings/`:
  `pod-daily.md`, `weekly-sprint.md`, `monthly-milestone.md`) — status/planning
  reviews with a fixed roster, output written to `.inbox/`. Don't reuse this
  skill to fake one of those; if the ask is genuinely "run today's pod daily",
  route to the scheduler instead.
- Atlas's own dispatch loop (`@@RUN`/`@@RUNW`/`@@SCAN` markers, parsed by
  `core.runtime.orchestrator.Orchestrator` when running as the standalone
  `core.runtime.cli_main` chat loop) — that's a separate, headless operating
  mode with its own dispatch protocol. This skill is for an interactive
  session where you (the main session) spawn each panelist directly via the
  `Agent` tool.

Both of those use a similar shape — a facilitator running participants through
rounds to a close — but neither is a freeform panel on an arbitrary topic with
an arbitrary member list. This skill exists so that shape isn't locked to a
fixed roster or a cron/marker trigger.

## Inputs
- **Topic** — one concrete question or goal, not a vague area. "Bring the
  dashboard UX to a professional baseline without generic AI-slop styling" is
  a topic; "talk about the frontend" is not — narrow it with the user first if
  it's too broad to close on.
- **Panel** — an ORDERED list of 2+ agent ids, each a valid id in this
  project's declared roster (`core.config.agent_ids(config)` — the base roles
  enabled in `config.agents` plus any project-authored domain agent; never a
  generic/general-purpose stand-in, and never an id outside the roster — a
  persona written into the prompt is not routing, the `subagent_type` field is
  what actually selects the agent's model, tools, and charter). Order the
  panel so a real debate emerges: the domain owner who should frame the
  problem goes first (propose), the agent whose feasibility/constraints
  matter most goes last (respond + close). E.g. for a UI-direction review:
  `ux` proposes the direction, `frontend` reacts and closes, because frontend
  owns what's actually buildable.
- **Facilitator** — defaults to the main session itself (you). Only hand this
  to `atlas` as facilitator if the user explicitly wants the human-facing
  chief-of-staff framing instead of running it inline — that changes who
  synthesizes and reports to the human, not the panel shape.

## Procedure
1. **Frame the topic.** State it back to the user in one sentence before
   spawning anyone, so a vague ask gets narrowed up front instead of producing
   a board that can't close.
2. **Round 1 — propose.** Spawn the first panelist via the `Agent` tool with
   `subagent_type` set to their exact agent id. Give them the topic and tell
   them explicitly: ground the proposal in the real project, not guesses
   (read the actual code/config/docs relevant to the topic first — use
   `python3 -m core.knowledge.codegrapher query "<topic>"` first if this
   project has the knowledge graph wired, per `README.md`), be concrete (name
   specific reference points, file:line locations, whatever "concrete" means
   for this topic), first person, opinionated. This round is planning/design
   only — read-only investigation is fine and expected, but no file edits
   during the board.
3. **Round 2+ — react and respond.** Spawn the next panelist with the FULL
   text of every prior round pasted verbatim into their prompt — not
   summarized. A summary flattens the disagreement that makes the board worth
   running; the next panelist needs to see exactly what was argued to react to
   it, the same way a human would in a real meeting. Ask them to say where
   they agree, where they push back (feasibility, sequencing, scope, missing
   dependencies), and flag anything blocked on a domain outside the current
   panel (e.g. "needs backend for an API change" when backend isn't on this
   board — name it as a follow-up, don't route around it by inventing
   backend's answer).
4. **Keep going only if the debate is still live.** Most topics close in 2
   rounds (propose, react-and-close). Add a round only if the last panelist's
   response raises something the first panelist should get to answer before a
   decision is fair to write down — don't pad the board for its own sake.
5. **Close with a numbered DECISION list.** The last panelist (or whichever
   panelist is the actual implementation/domain owner for what's being
   decided) closes the board. Each decision line is: **what** we're doing,
   **who owns it** (a specific panel member, someone named as a needed
   follow-up, or "none yet" if genuinely unowned), and **sequencing** (now /
   next / later). The close must stay honest about constraints raised during
   the board — if someone flagged a migration cost or a blocking dependency,
   the decision list sequences around it instead of promising a big-bang
   version of the thing.
6. **Archive the transcript.** Write the full board — topic, panel, every
   round verbatim, the closing decision list — to
   `.inbox/YYYY-MM-DD-circle-<topic-slug>.md`, matching the scheduled
   meetings' own output convention (`core/scheduler/meetings.py` writes
   `.inbox/{day}-{kind}.md`) so both land in the same place:
   ```
   ---
   type: circle-meeting
   topic: <the topic, one line>
   panel: [<agent id>, <agent id>, ...]
   date: YYYY-MM-DD-HHMMSS
   ---

   # Circle meeting — <the topic>

   ## Round 1 — <panelist>
   <that panelist's full round, first person>

   ## Round 2 — <panelist>
   ...

   ## DECISIONS — <closing panelist>
   <the numbered decision list>
   ```
   `.inbox/` is already gitignored in this framework — this is a durable local
   record, not something to commit. What you report to the user is not the
   full transcript.
7. **Report up.** Give the user a short human-facing summary in chat: who
   proposed what, where the pushback was, and the numbered decisions with
   owners. Point them at the archived file if they want the full transcript.
   Do not paste the full transcript into chat — that defeats the point of
   archiving it separately.

## Notes
- Each panelist is a genuinely fresh `Agent` call (not a fork) unless a round
  needs to continue a specific panelist's own prior subagent — in the normal
  case, each round is a new spawn of that panelist with the accumulated
  transcript as context, not a resumed conversation.
- If a panelist's response reveals the panel is wrong (the real owner of a
  point isn't in the room), say so in the close rather than letting a
  panelist speak for a domain that isn't theirs — that's a follow-up decision
  ("needs backend"), not something to fake. If the project's roster genuinely
  has no agent for that domain, that's an onboarding gap — see
  `skills/org-onboarding/SKILL.md` step 4 (author a new domain agent) rather
  than stretching an existing panelist to cover it.
- This produces planning artifacts and decisions, not code. If the closing
  decision list is meant to turn into actual work, that's a separate task
  after the board closes, using the decisions as the spec — don't blur the
  board itself into an execution wave.
