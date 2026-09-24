# Privacy Policy

## The short version

Prytan collects **nothing**. It runs entirely on your machine. No data leaves your
computer except the prompts Claude Code sends to Anthropic's API under your own account.

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
| `memory/` | Shared facts the org has recorded |
| `.inbox/`, `.handoffs/`, `.proposals/` | Agent coordination messages |
| `.logs/` | Per-agent run logs, token usage, and `conversations.jsonl` (saved turns: capped at 500 chars each, secrets redacted, gitignored) |
| `.agent-runtime/` | Generated permission files and the embedding cache (gitignored) |
| `config.yaml`, `.env` | Your configuration and optional Telegram credentials (gitignored) |

## Anthropic API

When Claude Code runs an agent, the prompt is sent to Anthropic's API under your own
account. Prytan has no visibility into this traffic. Anthropic's privacy policy governs
that data: https://www.anthropic.com/privacy

## Local embeddings (optional)

If you enable semantic recall, memory text and prompts are sent to the Ollama server you
configure (by default `http://localhost:11434`, on your own machine). Prytan never sends
them anywhere else.

## Telegram (optional)

If you enable the Telegram bot, messages you exchange with your bot pass through
Telegram's servers. Your bot token stays in your local environment.

## Changes

This policy applies to Prytan as open-source software. If you fork or modify Prytan, your
deployment's privacy characteristics may differ.
