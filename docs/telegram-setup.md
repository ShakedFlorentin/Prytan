# Telegram Bot Setup

Prytan's Telegram bot lets you chat with Iris — your chief-of-staff — from your phone. Send a goal, check status, get your morning brief, or kick off an autonomous work loop, all from Telegram.

This guide takes about 5 minutes.

---

## Step 1 — Create your bot via BotFather

1. Open Telegram and search for **@BotFather** (the official blue-checkmark bot).
2. Send `/newbot`
3. BotFather will ask for a **name** — this is the display name people see. Example: `Prytan Council`
4. Then it asks for a **username** — must end in `bot`. Example: `prytan_myproject_bot`
5. BotFather replies with your **bot token**. It looks like:

   ```
   <your-bot-id>:<your-bot-token>
   ```

   Copy it — you'll need it in Step 3.

> **Keep your token private.** Anyone with it can control your bot.

---

## Step 2 — Get your chat ID

Your chat ID tells the bot which Telegram account is allowed to send it commands. Without this, anyone who messages your bot could control your agents.

**Option A — @userinfobot (easiest)**

1. Open Telegram and search for **@userinfobot**
2. Send it `/start`
3. It replies with your info including `Id: 123456789` — that number is your chat ID.

**Option B — via the Telegram API**

1. Send any message to your newly created bot (so it has a pending update)
2. Open this URL in your browser (replace `YOUR_TOKEN`):
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
3. Find `"chat":{"id":123456789,...}` — that number is your chat ID.

---

## Step 3 — Configure your `.env`

In your Prytan project directory:

```bash
cp .env.example .env
```

Open `.env` and fill in both values:

```env
TELEGRAM_BOT_TOKEN=<your-bot-id>:<your-bot-token>
TELEGRAM_ALLOWED_CHAT_ID=123456789
```

> `.env` is gitignored — it will never be committed.

---

## Step 4 — Start the bot

```bash
python3 scripts/telegram-bot.py
```

You should see:

```
Prytan bot started. Listening for messages from chat 123456789...
```

Send `/start` to your bot in Telegram. Iris will introduce herself.

**To keep it running in the background:**

```bash
# Option A — simple background process
nohup python3 scripts/telegram-bot.py &> .agent-logs/telegram.log &

# Option B — as a systemd service (Linux, recommended for servers)
# See docs/telegram-systemd.md
```

---

## Available commands

Once the bot is running, send these from Telegram:

| Command | What it does |
|---|---|
| `/start` | Introduction + help |
| `/status` | Session and budget status |
| `/brief` | Today's morning brief |
| `/standup` | Run the org standup now |
| `/goal <text>` | Set a persistent goal for the agents |
| `/loop` | Start autonomous work toward the current goal |
| `/reset` | Clear the current session |

---

## Troubleshooting

**Bot doesn't respond**
- Check that `TELEGRAM_BOT_TOKEN` is correct (no extra spaces)
- Make sure you messaged the right bot (the one you created, not @BotFather)
- Check `.agent-logs/telegram.log` for errors

**"Unauthorized chat ID" error**
- The `TELEGRAM_ALLOWED_CHAT_ID` in `.env` doesn't match your actual chat ID
- Re-run Step 2 to confirm your ID and update `.env`

**Bot responds but agents don't run**
- Make sure Claude Code is installed: `claude --version`
- Check that your Anthropic API key is set: `echo $ANTHROPIC_API_KEY`

---

## Security notes

- The bot only responds to messages from `TELEGRAM_ALLOWED_CHAT_ID` — all other senders are silently ignored.
- Your bot token should never be committed to git. Double-check with `git status` — `.env` should always appear as untracked or in `.gitignore`.
- If your token is ever exposed, revoke it immediately via @BotFather (`/revoke`) and generate a new one.
