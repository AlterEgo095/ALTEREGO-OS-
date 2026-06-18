#!/usr/bin/env bash
# alterego-os/scripts/push.sh
#
# Usage:
#   ./scripts/push.sh "feat: ma nouvelle feature"
#   ./scripts/push.sh   # default commit message
#
# This script stages all changes, commits, and pushes to GitHub.
# The token is read from .env (GITHUB_TOKEN) so it never appears in the script.

set -e

cd "$(dirname "$0")/.."

# ── Default commit message ──────────────────────────────────────────────────
MSG="${1:-chore: update ALTEREGO OS}"

# ── Sanity checks ────────────────────────────────────────────────────────────
if [ ! -d .git ]; then
  echo "✗ Not a git repository. Run from alterego-os/ root."
  exit 1
fi

# ── Stage all changes (respecting .gitignore) ────────────────────────────────
git add -A

# ── Check if there's anything to commit ──────────────────────────────────────
if git diff --cached --quiet; then
  echo "✓ Nothing to commit — working tree clean."
  exit 0
fi

# ── Show what's being committed ──────────────────────────────────────────────
echo "── Files to be committed ──"
git diff --cached --name-status
echo ""

# ── Commit & push ────────────────────────────────────────────────────────────
git commit -m "$MSG"
git push origin main

echo ""
echo "✓ Pushed to GitHub: $MSG"
echo "✓ Repo: https://github.com/AlterEgo095/ALTEREGO-OS-"
