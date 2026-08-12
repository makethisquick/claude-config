#!/usr/bin/env bash
# Pull this machine's live Claude config back INTO the repo (the reverse of bootstrap.sh).
#
#   ./bootstrap/export.sh
#
# Run this on whichever machine you just changed something on, then commit and push.
# Copies ~/.claude/skills/* into skills/ and refreshes the *_MCP_BASIC values in
# secrets/credentials.json (gitignored). It does NOT touch servers/manifest.json —
# new MCP servers are added there by hand, so both OS variants stay in sync.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== Skills"
mkdir -p "$ROOT/skills"
for d in "$HOME"/.claude/skills/*/; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  rm -rf "${ROOT:?}/skills/$name"
  cp -R "$d" "$ROOT/skills/"
  echo "   exported $name"
done

echo "== Credentials (gitignored)"
ROOT="$ROOT" python3 - <<'PY'
import json, os, stat

root = os.environ['ROOT']
p    = f'{root}/secrets/credentials.json'

try:
    with open(os.path.expanduser('~/.claude/settings.json')) as f:
        live = json.load(f).get('env', {})
except (FileNotFoundError, json.JSONDecodeError):
    live = {}

env = {k: v for k, v in live.items() if k.endswith('_MCP_BASIC')}

try:
    with open(p) as f: cur = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    cur = {'_comment': 'GITIGNORED: contains live credentials.',
           'env': {}, 'googleAds': {'GOOGLE_ADS_DEVELOPER_TOKEN': ''}}

cur.setdefault('env', {}).update(env)
cur.setdefault('googleAds', {}).setdefault('GOOGLE_ADS_DEVELOPER_TOKEN', '')

with open(p, 'w') as f: json.dump(cur, f, indent=2)
os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
print(f'   refreshed {len(env)} credentials in secrets/credentials.json')
PY

echo
echo "Now: git -C $ROOT add -A && git -C $ROOT commit && git -C $ROOT push"
echo "(secrets/credentials.json is gitignored - move it by hand, it is not pushed)"
