# /init — Prytan Setup

Run a fast, friendly onboarding. Ask only what you genuinely cannot guess. Use smart defaults for everything else. The whole thing should feel like a 60-second chat, not a form.

---

## How to run this

Open with a warm one-liner, then ask the three questions **one at a time**. Never ask two in the same message.

**Opening message:**

> Hey! Let's set up your Prytan council. I just need three quick answers and I'll handle the rest.
> 
> First: **what's the name of your project or business?**

---

## The 3 questions

**Q1 — Name**
What's your project or business called?

**Q2 — What it does**
One sentence: what does it do?
*(This becomes the shared context every agent reads before acting.)*

**Q3 — Team size**
> 1. Just me
> 2. Small team (2–15 people)
> 3. Larger org (15+)

That's it. Don't ask anything else.

---

## Smart defaults (apply silently — do NOT ask about these)

| Setting | Default | Where it lives |
|---|---|---|
| Telegram bot | disabled | `.agent-config/project.yaml` |
| Monthly budget | $25 / month (50M tokens) | `.agent-config/budget.yaml` |
| Standup time | 08:00 | `scripts/org.crontab` |
| Timezone | detect via `python3 -c "import datetime; print(datetime.datetime.now().astimezone().tzname())"` — fall back to UTC | `scripts/org.crontab` |
| Agent preset | see below | `.agent-config/project.yaml` |

**Agent presets by team size:**

- **Just me:** Iris, Nestor, Thea, Lyra, Kairos, Sophia, Chiron *(7 agents)*
- **Small team:** above + Leon, Clio, Argus, Atlas, Muse, Themis, Solon *(14 agents)*
- **Larger org:** all 16 agents

---

## After the 3 answers

Show a compact summary and ask one final yes/no:

> Got it. Here's what I'll set up:
>
> - **Project:** [Q1] — [Q2]
> - **Agents:** [N] active ([preset name])
> - **Budget:** $25/month · standup at 08:00 [timezone]
> - **Telegram:** not enabled (you can add it later — see docs/telegram-setup.md)
>
> Looks good? I'll write the files now. *(yes / change something)*

If they say yes, write files. If they say "change something", ask what specifically — don't restart the whole wizard.

---

## Files to write (show ✓ for each)

**`.agent-config/project.yaml`**
```yaml
project_name: <Q1>
description: "<Q2>"
scale: <solo|small|large>
active_agents: [<preset list>]
telegram_bot: false
monthly_budget_usd: 25
standup_time: "08:00"
timezone: "<detected or UTC>"
```

**`.agent-config/budget.yaml`** — monthly_token_cap: 50000000, throttle at 80%, halt at 100%.

**`scripts/org.crontab`** — `[PROJECT_PATH]` → `$PWD`, time from default, timezone from detected.

**`.env.example`**
```
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_ALLOWED_CHAT_ID=your_chat_id_here
```

**`CLAUDE.md`** — update routing table to list only active agents, fill in project name.

Then run silently:
```bash
python3 codegrapher.py scan .
```

---

## Closing message

> You're all set. Your [N]-agent council is ready.
>
> **Next steps:**
> - Activate daily standups: `crontab scripts/org.crontab`
> - Add Telegram (optional): see [docs/telegram-setup.md](docs/telegram-setup.md)
>
> Just talk to me normally — I'll route everything from here.

---

## Rules

- One question per message. Maximum.
- Never ask about budget, timezone, standup time, or Telegram — those are defaults.
- If the user volunteers extra info ("I'm in Tel Aviv", "I want Telegram"), absorb it silently and use it.
- Keep every message short. This is a 60-second setup, not an interview.
