#!/usr/bin/env bash
# One-time setup on a new machine. Both deps have bitten us; this makes them explicit.
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
echo "installing docx into the skill dir (require resolves from the script, not the cwd)…"
( cd "$SKILL" && npm install docx --silent )
VENV="$HOME/.claude/skills/client-launch/.venv"
if [ -x "$VENV/bin/python" ]; then
  echo "installing matplotlib into the client-launch venv…"
  "$VENV/bin/pip" install matplotlib --quiet
else
  echo "WARNING: $VENV not found — charts.py needs a python with matplotlib."
fi
echo "done. verify with:  python3 $SKILL/scripts/verify.py <some.docx>"
