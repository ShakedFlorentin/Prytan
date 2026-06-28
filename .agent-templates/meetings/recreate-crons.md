# Recreate Crons After Reinstall

**Purpose:** Instructions for restoring all scheduled cron jobs after a fresh
system install, migration, or when `crontab -l` returns nothing.

---

## Step 1 — Verify the crontab file

```bash
cat scripts/org.crontab
```

Confirm `[PROJECT_PATH]` placeholders have been replaced with the actual
absolute path to this project. If not, replace them:

```bash
# Example — replace the placeholder with actual path
sed -i 's|\[PROJECT_PATH\]|/home/user/my-project|g' scripts/org.crontab
```

## Step 2 — Check your timezone

The crontab uses the system timezone. Verify:

```bash
timedatectl        # Linux
systemsetup -gettimezone  # macOS
```

If you need a specific timezone, prepend `TZ=America/New_York` (or your zone)
to the crontab file.

## Step 3 — Install the crontab

```bash
crontab scripts/org.crontab
```

Verify:

```bash
crontab -l
```

## Step 4 — Test one job manually

```bash
cd /path/to/project && python3 scripts/cost_governor.py
```

Expected output: `PROCEED` (if under budget) or `HALT` (if over budget).

## Step 5 — Check logs after first run

```bash
tail -f .agent-logs/cron.log
```

---

## Cron jobs in this project

| Schedule | Job |
|----------|-----|
| Daily standup | Weekdays at configured time |
| Weekly sprint planning | Monday (or configured day) at configured time |
| Monthly milestone | 1st of month at configured time |

All schedules are in `scripts/org.crontab`. To change times, edit that file
and re-install with `crontab scripts/org.crontab`.

---

## Troubleshooting

**Cron runs but Claude Code isn't found:**
```bash
which claude      # find the path
# Add to crontab: PATH=/usr/local/bin:/usr/bin:/bin (already included)
```

**No output in .agent-logs/cron.log:**
- Check that the log directory exists: `mkdir -p .agent-logs`
- Check cron daemon is running: `sudo service cron status` (Linux) or `launchctl list | grep cron` (macOS)

**cost_governor.py exits with HALT:**
- Check `.agent-config/spend.jsonl` for this month's spend
- Raise `monthly_budget_usd` in `.agent-config/budget.yaml` if needed
