#!/usr/bin/env bash
# Prytan installer — checks prerequisites and clones the repo.
# The actual setup happens inside Claude Code via /init.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ShakedFlorentin/Prytan/main/install.sh | bash
#   — or —
#   git clone https://github.com/ShakedFlorentin/Prytan.git && cd Prytan && ./install.sh

set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
CYAN="\033[0;36m"
RESET="\033[0m"

ok()   { echo -e "  ${GREEN}✓${RESET}  $1"; }
warn() { echo -e "  ${YELLOW}!${RESET}  $1"; }
fail() { echo -e "  ${RED}✗${RESET}  $1"; exit 1; }
step() { echo -e "\n${BOLD}$1${RESET}"; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║           Prytan — AI Council Setup              ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════════╝${RESET}"
echo ""

# ── Step 1: Prerequisites ─────────────────────────────────────────────────────

step "Checking prerequisites..."

# Python 3.10+
if ! command -v python3 &>/dev/null; then
  fail "Python 3.10+ is required → https://python.org"
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MIN=$(python3 -c "import sys; print(int(sys.version_info.major==3 and sys.version_info.minor>=10))")
[ "$PY_MIN" = "1" ] || fail "Python 3.10+ required (found $PY_VER) → https://python.org"
ok "Python $PY_VER"

# Claude Code
if ! command -v claude &>/dev/null; then
  warn "Claude Code not found. Install it first:"
  echo ""
  echo -e "      ${CYAN}npm install -g @anthropic/claude-code${RESET}"
  echo ""
  echo "  Then re-run this script."
  exit 1
fi
ok "Claude Code $(claude --version 2>/dev/null | head -1 | awk '{print $NF}')"

# Git
command -v git &>/dev/null || fail "Git is required → https://git-scm.com"
ok "Git"

# ── Step 2: Clone ─────────────────────────────────────────────────────────────

step "Setting up Prytan..."

if [ -f "codegrapher.py" ] && [ -d ".claude/agents" ]; then
  ok "Already inside a Prytan directory"
  PRYTAN_DIR="$(pwd)"
else
  PRYTAN_DIR="${1:-$HOME/Prytan}"
  if [ -d "$PRYTAN_DIR" ]; then
    warn "Directory already exists at $PRYTAN_DIR — skipping clone"
  else
    echo -e "  Cloning into ${CYAN}$PRYTAN_DIR${RESET} ..."
    git clone https://github.com/ShakedFlorentin/Prytan.git "$PRYTAN_DIR" --quiet
    ok "Cloned to $PRYTAN_DIR"
  fi
  cd "$PRYTAN_DIR"
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║                  Ready!                          ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  One more step — open Claude Code and run the setup wizard:"
echo ""
echo -e "      ${CYAN}cd $PRYTAN_DIR${RESET}"
echo -e "      ${CYAN}claude${RESET}"
echo ""
echo -e "  Then inside Claude Code, type:"
echo ""
echo -e "      ${BOLD}/init${RESET}"
echo ""
echo -e "  The wizard will ask you ~7 questions and set everything up."
echo ""
