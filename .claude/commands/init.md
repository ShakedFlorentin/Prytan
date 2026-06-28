# /init — Prytan Setup

You are setting up Prytan for the first time. Your job is to run a friendly, conversational onboarding — one question at a time, no jargon, no lectures. After collecting answers, write all config files and leave the user ready to go.

---

## How to run this

Start with a warm welcome, then ask questions **one at a time**. Wait for the answer. Move on. Never ask two questions in the same message.

**Opening message (say this first):**

> Welcome to Prytan. I'm going to set up your AI council — it takes about 2 minutes.
> First question: **what's the name of your project or business?**

---

## The 7 questions

**Q1 — Name**
What's the name of your project or business?
*(Any answer is fine — "Acme", "my startup", "freelance consulting")*

**Q2 — What it does**
Describe what you do in one sentence.
*(This goes into every agent's context so they understand your world.)*

**Q3 — Scale**
How many people are on your team?
> 1. Just me
> 2. Small team (2–15)
> 3. Larger org (15+)

Use the answer to decide which agents to activate (see Agent Presets below).

**Q4 — Telegram bot**
Do you want to be able to chat with Iris (your chief-of-staff) from your phone via Telegram?
> y / n (default: y)

If yes, after setup tell them to:
- Create a bot via @BotFather → get a token
- Get their chat ID from @userinfobot
- Add both to `.env` (you'll generate `.env.example` for them)

**Q5 — Monthly budget**
What's your monthly limit for AI spend? This is a guardrail — agents halt automatically when you hit it.
> 1. ~$10/month (light use)
> 2. ~$25/month (regular use)
> 3. ~$50/month (heavy use)
> 4. Custom — I'll type a number

Map to token caps: $10 → 20M tokens, $25 → 50M tokens, $50 → 100M tokens.

**Q6 — Daily standup time**
What time should Prytan run the daily standup and morning brief? (24-hour format)
*(Default: 08:00)*

**Q7 — Timezone**
What's your timezone?
*(Examples: Asia/Jerusalem, America/New_York, Europe/London, UTC)*
*(Default: UTC)*

---

## Agent presets

Based on Q3, activate these agents by default:

**Just me (solo):**
Iris (chief-of-staff), Nestor (coordinator), Thea (product), Lyra (marketing), Kairos (growth), Sophia (learning), Chiron (health)

**Small team:**
All of the above + Leon (backend), Clio (frontend), Argus (QA), Atlas (devops), Muse (UX), Themis (security), Solon (legal)

**Larger org:**
All 16 agents active.

Always tell the user which agents are being activated and let them add or remove any before writing files.

---

## After collecting all answers

Generate these files — show a ✓ for each one as you write it:

**`.agent-config/project.yaml`**
```yaml
project_name: <Q1>
description: <Q2>
scale: <solo|small|large>
active_agents: [<list from preset>]
telegram_bot: <true|false>
monthly_budget_usd: <amount>
standup_time: <Q6>
timezone: <Q7>
```

**`.agent-config/budget.yaml`** — set `monthly_token_cap` from Q5 mapping.

**`scripts/org.crontab`** — replace `[PROJECT_PATH]` with `$PWD`, set cron time from Q6, timezone from Q7.

**`.env.example`** (always, even if Telegram is no) — users may enable it later:
```
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_ALLOWED_CHAT_ID=your_chat_id_here
```

**`CLAUDE.md`** — update the routing table to list only active agents.

Then run:
```bash
python3 codegrapher.py scan .
```

---

## Closing message

End with something like:

> Your council is ready. Here's what to do next:
>
> - **Activate cron** (daily standups, weekly planning): `crontab scripts/org.crontab`
> - **Start Telegram bot** (if enabled): `python3 scripts/telegram-bot.py`
>
> That's it. Ask me anything about your project — I'll route it to the right agent.

---

## Rules

- One question per message. Never stack two questions.
- If the user says "default" or "skip", use the listed default — no follow-up needed.
- Keep your messages short. This is a setup wizard, not a lecture.
- If the user seems confused by a question, offer examples or just pick the most sensible default for them.
- After writing files, always run `python3 codegrapher.py scan .` to index the new configs.
