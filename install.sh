#!/usr/bin/env bash
# Prytan installer
# Usage: ./install.sh
# Or:    curl -fsSL https://raw.githubusercontent.com/ShakedFlorentin/Prytan/main/install.sh | bash

set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

ok()   { echo -e "${GREEN}✓${RESET} $1"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $1"; }
fail() { echo -e "${RED}✗${RESET} $1"; exit 1; }
step() { echo -e "\n${BOLD}$1${RESET}"; }

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║            Prytan Installer              ║"
echo "║    YOUR AI COUNCIL FOR ANY BUSINESS      ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Prerequisites ──────────────────────────────────────────────────────────

step "1/4 — Checking prerequisites"

# Python 3.10+
if ! command -v python3 &>/dev/null; then
  fail "Python 3.10+ is required. Install from https://python.org"
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
  fail "Python 3.10+ required (found $PY_VERSION). Upgrade from https://python.org"
fi
ok "Python $PY_VERSION"

# Claude Code CLI
if ! command -v claude &>/dev/null; then
  warn "Claude Code CLI not found."
  echo "    Install it with: npm install -g @anthropic/claude-code"
  echo "    Then re-run this script."
  echo ""
  read -r -p "Continue anyway? (y/N) " CONTINUE
  if [[ "$CONTINUE" != "y" && "$CONTINUE" != "Y" ]]; then
    exit 0
  fi
else
  CLAUDE_VERSION=$(claude --version 2>/dev/null | head -1 || echo "unknown")
  ok "Claude Code ($CLAUDE_VERSION)"
fi

# Git
if ! command -v git &>/dev/null; then
  fail "Git is required. Install from https://git-scm.com"
fi
ok "Git $(git --version | awk '{print $3}')"

# ── 2. Clone (if running via curl) ───────────────────────────────────────────

step "2/4 — Setting up Prytan"

# If we're already inside a Prytan repo, skip cloning
if [ -f "codegrapher.py" ] && [ -d ".claude/agents" ]; then
  ok "Already inside a Prytan directory — skipping clone"
  PRYTAN_DIR="$(pwd)"
else
  PRYTAN_DIR="${1:-./Prytan}"
  if [ -d "$PRYTAN_DIR" ]; then
    warn "Directory $PRYTAN_DIR already exists — skipping clone"
  else
    echo "  Cloning Prytan into $PRYTAN_DIR ..."
    git clone https://github.com/ShakedFlorentin/Prytan.git "$PRYTAN_DIR"
    ok "Cloned to $PRYTAN_DIR"
  fi
  cd "$PRYTAN_DIR"
fi

# ── 3. Configure ─────────────────────────────────────────────────────────────

step "3/4 — Running setup wizard"
echo ""
echo "  The wizard asks ~10 questions and writes all config files."
echo "  Press Ctrl+C at any time to quit."
echo ""

python3 setup/configure.py

# ── 4. Build knowledge graph ──────────────────────────────────────────────────

step "4/4 — Building initial knowledge graph"

# Determine scan dir from daily-steps.yaml if it exists
SCAN_DIR="src"
if [ -f ".agent-config/daily-steps.yaml" ]; then
  YAML_DIR=$(grep -A1 "scan_dirs:" .agent-config/daily-steps.yaml | tail -1 | sed 's/.*- //' | tr -d ' ')
  if [ -n "$YAML_DIR" ] && [ -d "$YAML_DIR" ]; then
    SCAN_DIR="$YAML_DIR"
  fi
fi

if [ -d "$SCAN_DIR" ]; then
  echo "  Scanning $SCAN_DIR ..."
  python3 codegrapher.py scan "$SCAN_DIR"
  ok "Knowledge graph built"
else
  warn "Source directory '$SCAN_DIR' not found — run 'python3 codegrapher.py scan <your-src-dir>' manually"
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║              Setup complete!             ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Open Claude Code in this directory:"
echo "     ${BOLD}claude${RESET}"
echo ""
echo "  2. Run /init inside Claude Code to finish configuring your agents."
echo ""
echo "  3. Install the cron schedule (daily standups, weekly planning):"
echo "     ${BOLD}crontab scripts/org.crontab${RESET}"
echo ""
echo "  4. Optional — start the Telegram bot:"
echo "     ${BOLD}cp .env.example .env${RESET}  # add your token"
echo "     ${BOLD}python3 scripts/telegram-bot.py${RESET}"
echo ""
echo "  Docs: https://github.com/ShakedFlorentin/Prytan"
echo ""
