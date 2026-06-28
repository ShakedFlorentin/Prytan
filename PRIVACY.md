# Privacy Policy

## The short version

Prytan collects **nothing**. It runs entirely on your machine. No data leaves your computer except the prompts you send to Claude Code (which go to Anthropic's API, under your own API key).

## What Prytan does and does not do

| What | Does Prytan do it? |
|---|---|
| Send telemetry to a remote server | ❌ No |
| Store data in the cloud | ❌ No |
| Phone home on install, update, or run | ❌ No |
| Share your code or agent output with third parties | ❌ No |
| Require an account or registration | ❌ No |

## What stays local

All Prytan data lives in your project directory:

| Path | What's stored |
|---|---|
| `codegrapher_out/graph.json` | Local knowledge graph of your codebase |
| `.agent-logs/` | Decision ledger, skill store, violation log |
| `.agent-inbox/` | Agent handoffs and pending decisions |
| `.agent-config/spend.jsonl` | Running token spend log |
| `.env` | Telegram bot token (gitignored, never sent anywhere by Prytan) |

## Anthropic API

When Claude Code runs an agent, your prompt is sent to Anthropic's API under **your own API key**. Prytan has no visibility into this traffic. Anthropic's own privacy policy governs that data: https://www.anthropic.com/privacy

## Telegram (optional)

If you enable the Telegram bot, messages you send to your bot are processed by Telegram's servers before reaching your machine. Prytan does not log Telegram message content beyond what Claude Code produces in `.agent-logs/`. Your bot token is stored only in `.env` (gitignored).

## Changes

This policy applies to Prytan as open-source software. If you fork or modify Prytan, your deployment's privacy characteristics may differ.
