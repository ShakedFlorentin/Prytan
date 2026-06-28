# /init — Prytan Setup Wizard

You are helping a developer wire Prytan to their project for the first time. Walk through these questions **one by one**, waiting for the answer before moving to the next. After collecting all answers, generate the configuration files.

---

## Questions to ask

**Q1 — Project name**
> "What is your project called?" (e.g. `AcmePlatform`, `MyStartup`)

**Q2 — Project description**
> "Describe your project in 1–2 sentences. Agents will use this as context for every decision they make."

**Q3 — Primary language / stack**
> "What's the main language and framework? (e.g. Python + FastAPI, TypeScript + Next.js, Go + gRPC). This controls which files codegrapher indexes."

**Q4 — Pods / teams**
> "How many teams (pods) do you want? Give them names and 1-sentence descriptions.
> Example: `eng: backend + frontend devs`, `growth: marketing + outreach`, `ops: infra + security`
> Or just press Enter for a single 'main' pod."

**Q5 — Chief-of-staff agent**
> "What should your human-facing agent (the one connected to Telegram) be called? This agent answers your questions, routes tasks, and runs the leadership board.
> Default: `coord` — just press Enter to use that."

**Q6 — Work week**
> "What days does your team work?
>   1. Mon–Fri (international)
>   2. Sun–Thu (Israeli)
>   3. Custom (you'll specify)
> Enter 1, 2, or 3."

**Q7 — Daily standup time**
> "What local time should the daily standup cron run? (24-hour, e.g. `08:00`)
> Default: `08:00`"

**Q8 — Timezone**
> "What timezone? (e.g. `Asia/Jerusalem`, `America/New_York`, `UTC`)
> Default: `UTC`"

**Q9 — Telegram bot**
> "Do you want the Telegram bot so you can chat with your chief-of-staff from your phone?
>   y / n (default: y)"

**Q10 — Token budget**
> "Monthly token cap for all cron agents combined (in millions of tokens).
>   Soft throttle kicks in at 80%, hard stop at 100%.
>   Default: `50` (= 50M tokens)"

---

## After collecting answers

1. **Scan the codebase** — run `python3 codegrapher.py scan .` to build the knowledge graph.

2. **Write `.agent-config/project.yaml`** with all answers:
```yaml
project_name: <Q1>
description: <Q2>
stack: <Q3>
pods:
  - name: <pod1-name>
    description: <pod1-desc>
  # ...
chief_of_staff: <Q5>
work_week: <Q6>
standup_time: <Q7>
timezone: <Q8>
telegram_bot: <Q9>
monthly_token_cap_m: <Q10>
```

3. **Update `CLAUDE.md`** — replace `[PROJECT_NAME]` with the real name, fill in the agent routing table based on pods.

4. **Generate `.claude/agents/<chief-of-staff>.md`** from the template in `.claude/agents/chief-of-staff.md`.

5. **Generate per-pod agent files** in `.claude/agents/` — one facilitator per pod.

6. **Generate `scripts/org.crontab`** — replace `[PROJECT_PATH]` with `$PWD`, set the correct day-of-week pattern and time.

7. **Update `.agent-config/budget.yaml`** — set `monthly_token_cap` from Q10.

8. **If Telegram bot (Q9=y):** print setup instructions:
   - Create bot via @BotFather
   - Get chat ID
   - Create `~/.prytan.env` with `TELEGRAM_BOT_TOKEN` and `ALLOWED_CHAT_ID`
   - Run `python3 scripts/telegram-bot.py`

9. **Show a summary** of what was generated and next steps:
   - `crontab scripts/org.crontab` to activate meetings
   - `python3 scripts/telegram-bot.py &` if bot enabled
   - "Your agent org is ready. Ask me anything about your project."

---

## Important rules
- Never skip a question — each drives a different config file
- If the user says "skip" or "default" for any question, use the listed default
- After generating files, run `python3 codegrapher.py scan .` to re-index (so agents can find the new configs)
- Keep responses concise — ask one question at a time, don't lecture
