# Leadership Board — Circle Table Protocol

**Cadence:** Human-triggered, NOT a cron. Start it via your chief-of-staff agent.
**Facilitator:** chief-of-staff agent (the one wired to Telegram).
**Standing panel:** coordinator + one lead per active pod.
**Advisory (pull in as needed):** security-advisor, any domain expert relevant to the blocker.

> This is where cross-pod conflicts, strategic forks, and major scope decisions get
> resolved. One topic per session. The panel argues, then the decision-writer closes
> with a numbered DECISION + owner.

---

## How the chief-of-staff runs it

1. **Frame** — read the latest pod digests in `.agent-inbox/` + open `.agent-proposals/`.
   State the single most consequential open question as the topic.

2. **Assemble panel** — always: coordinator + pod leads.
   Pull domain advisors only if the blocker is in their area.

3. **Run @@BOARD rounds** — spawn each panelist IN ORDER, each seeing all prior rounds.
   Keep to 2–3 rounds max. Each panelist speaks first-person, with a concrete position.

4. **Close** — the coordinator (or domain owner) writes:
   ```
   DECISION [N]: <what was decided>
   Owner: <agent or human>
   Next action: <concrete step>
   ```

5. **Report up** — chief-of-staff writes a tight summary to the human:
   who proposed what, who objected, what was decided.
   Archive the transcript to `.planning/boardroom-YYYY-MM-DD-<topic>.md`.
   Do NOT auto-execute — owners pick up via handoffs.

---

## When to call it

- A pod daily escalated a cross-pod blocker neither facilitator can resolve.
- Two pods are competing for the same resource or week.
- A `.agent-proposals/` item needs an executive verdict.
- The human asks "what should we do about X" at the strategy level.
- A one-way / irreversible decision needs senior sign-off before proceeding.

---

## Trigger (via Telegram or Claude Code)

```
<chief-of-staff name>, run the leadership board on: <topic>.
Standing panel: coordinator + [pod leads]. Pull [advisor] if needed.
Run @@BOARD, return me the bottom line.
```

---

## @@BOARD spawn pattern

Each agent is spawned in order, reading the prior transcript. Facilitator prompt per agent:

```
You are <agent>. The topic is: <topic>.
Prior discussion:
---
<transcript so far>
---
Give your position clearly. Be concrete, not diplomatic. If you disagree, say why.
If you support, say what you'd add. Max 3 paragraphs.
```
