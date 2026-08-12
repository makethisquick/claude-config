#!/usr/bin/env bash
# Bootstrap this machine (macOS / Linux) from the claude-config repo.
#
#   ./bootstrap/bootstrap.sh [--projects-root DIR] [--skip-venv] [--dry-run]
#
# Idempotent: safe to re-run after pulling changes. Backs up ~/.claude.json and
# ~/.claude/settings.json before touching them. The Windows equivalent is bootstrap.ps1.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECTS_ROOT="$HOME/projects"
SKIP_VENV=0
DRY_RUN=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --projects-root) PROJECTS_ROOT="$2"; shift 2 ;;
    --skip-venv)     SKIP_VENV=1; shift ;;
    --dry-run)       DRY_RUN=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 64 ;;
  esac
done

STAMP="$(date +%Y%m%d-%H%M%S)"
step() { printf '\n== %s\n' "$1"; }
info() { printf '   %s\n' "$1"; }
warn() { printf '   ! %s\n' "$1" >&2; }

step 'Prerequisites'
for t in claude npx python3 pipx gcloud; do
  if command -v "$t" >/dev/null 2>&1; then info "$t found"; else warn "$t MISSING"; fi
done

step 'Skills'
if [ "$DRY_RUN" = 1 ]; then
  info "would copy: $(ls "$ROOT/skills" | tr '\n' ' ')"
else
  mkdir -p "$HOME/.claude/skills"
  for d in "$ROOT"/skills/*/; do
    rm -rf "$HOME/.claude/skills/$(basename "$d")"
    cp -R "$d" "$HOME/.claude/skills/"
    info "installed skill $(basename "$d")"
  done
fi

step 'settings.json + MCP servers'
ROOT="$ROOT" PROJECTS_ROOT="$PROJECTS_ROOT" STAMP="$STAMP" DRY_RUN="$DRY_RUN" python3 - <<'PY'
import json, os, shutil, sys

root  = os.environ['ROOT']
projs = os.environ['PROJECTS_ROOT']
stamp = os.environ['STAMP']
dry   = os.environ['DRY_RUN'] == '1'
home  = os.path.expanduser('~')

def load(p, default):
    try:
        with open(p) as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def strip(d):
    return {k: v for k, v in d.items() if k != '_comment'}

def save(p, obj):
    if dry:
        print(f'   would write {p}'); return
    if os.path.exists(p): shutil.copy2(p, f'{p}.bak-{stamp}')
    tmp = p + '.tmp'
    with open(tmp, 'w') as f: json.dump(obj, f, indent=2)
    os.replace(tmp, p)

# ---- settings.json -------------------------------------------------------
shared   = strip(load(f'{root}/settings/settings.shared.json', {}))
cred     = load(f'{root}/secrets/credentials.json', {})
cred_env = {k: v for k, v in cred.get('env', {}).items()}
if not cred_env:
    print('   ! no secrets/credentials.json - WordPress servers will 401', file=sys.stderr)

settings = load(f'{home}/.claude/settings.json', {})
env      = settings.get('env', {})
env.update(cred_env)
settings.update(shared)
settings['env'] = env
save(f'{home}/.claude/settings.json', settings)
print(f'   merged {len(shared)} shared keys and {len(cred_env)} credentials')

# ---- MCP servers ---------------------------------------------------------
manifest = load(f'{root}/servers/manifest.json', {})

def resolve(entry):
    d = entry['posix']
    out = {}
    for k, v in d.items():
        if isinstance(v, str):    out[k] = v.replace('__ROOT__', root)
        elif isinstance(v, list): out[k] = [x.replace('__ROOT__', root) for x in v]
        else:                     out[k] = v
    return out

cj = load(f'{home}/.claude.json', {})
cj.setdefault('mcpServers', {})
for name, entry in manifest.get('user', {}).items():
    cj['mcpServers'][name] = resolve(entry)
    print(f'   user scope: {name}')

cj.setdefault('projects', {})
for proj, servers in manifest.get('projects', {}).items():
    path = os.path.join(projs, proj)
    if not os.path.isdir(path):
        print(f'   ! project not on this machine, skipping: {path}', file=sys.stderr)
        continue
    node = cj['projects'].setdefault(path, {})
    node.setdefault('mcpServers', {})
    for name, entry in servers.items():
        node['mcpServers'][name] = resolve(entry)
        print(f'   {proj}: {name}')

save(f'{home}/.claude.json', cj)
PY

step 'google-ads-write venv'
SERVER_DIR="$ROOT/servers/google-ads-write"
if [ "$SKIP_VENV" = 1 ] || [ "$DRY_RUN" = 1 ]; then
  info 'skipped'
elif [ -x "$SERVER_DIR/.venv/bin/python" ]; then
  info 'venv already present'
else
  python3 -m venv "$SERVER_DIR/.venv"
  "$SERVER_DIR/.venv/bin/python" -m pip install --quiet --upgrade pip
  "$SERVER_DIR/.venv/bin/python" -m pip install --quiet -e "$SERVER_DIR"
  info 'venv built and gads_write installed'
fi

chmod +x "$ROOT"/bin/*.sh 2>/dev/null || true

step 'Remaining manual steps'
cat <<EOF
   1. gcloud auth application-default login \\
        --scopes https://www.googleapis.com/auth/adwords,https://www.googleapis.com/auth/cloud-platform
   2. Google Ads developer token: Keychain (macOS) or secrets/credentials.json
        security add-generic-password -a claude -s google-ads-dev-token -w '<token>'
   3. pipx install git+https://github.com/googleads/google-ads-mcp.git
   4. claude mcp list, then authenticate box-remote-mcp with /mcp inside Claude Code

Done. Backups: *.bak-$STAMP
EOF
