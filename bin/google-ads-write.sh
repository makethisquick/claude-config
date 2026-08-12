#!/usr/bin/env bash
# Launch the Google Ads WRITE MCP server (servers/google-ads-write) over stdio.
#
# ⚠️  This server can change live advertising accounts. Every mutating tool
#     defaults to a dry run (validate_only) and requires confirm=true to write.
#
# Portable rewrite of ~/projects/mcp/google-ads-write.sh. The venv is not synced —
# bootstrap.sh creates it locally from the synced source.
#
# Usage (from servers/manifest.json):
#   <repo>/bin/google-ads-write.sh <gcp-project-id> [login-customer-id]

set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: $(basename "$0") <gcp-project-id> [login-customer-id]" >&2
  exit 64
fi

PROJECT_ID="$1"
LOGIN_CID="${2:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SERVER_DIR="$ROOT/servers/google-ads-write"
PYTHON="$SERVER_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  cat >&2 <<EOF
Server venv missing at $PYTHON
Rebuild with:
  python3 -m venv "$SERVER_DIR/.venv" && "$PYTHON" -m pip install -e "$SERVER_DIR"
EOF
  exit 1
fi

DEV_TOKEN="${GOOGLE_ADS_DEVELOPER_TOKEN:-}"

if [ -z "$DEV_TOKEN" ] && command -v security >/dev/null 2>&1; then
  DEV_TOKEN="$(security find-generic-password -a claude -s google-ads-dev-token -w 2>/dev/null || true)"
fi

if [ -z "$DEV_TOKEN" ] && [ -f "$ROOT/secrets/credentials.json" ]; then
  DEV_TOKEN="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('googleAds',{}).get('GOOGLE_ADS_DEVELOPER_TOKEN',''))" "$ROOT/secrets/credentials.json" 2>/dev/null || true)"
fi

if [ -z "$DEV_TOKEN" ]; then
  echo "No Google Ads developer token. See google-ads-mcp.sh for the three places it can come from." >&2
  exit 1
fi

ADC_PATH="${GOOGLE_APPLICATION_CREDENTIALS:-$HOME/.config/gcloud/application_default_credentials.json}"
if [ ! -f "$ADC_PATH" ]; then
  cat >&2 <<EOF
No Application Default Credentials at: $ADC_PATH
Create them with:
  gcloud auth application-default login \\
    --scopes https://www.googleapis.com/auth/adwords,https://www.googleapis.com/auth/cloud-platform
EOF
  exit 1
fi

export GOOGLE_ADS_DEVELOPER_TOKEN="$DEV_TOKEN"
export GOOGLE_APPLICATION_CREDENTIALS="$ADC_PATH"
export GOOGLE_PROJECT_ID="$PROJECT_ID"
export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"

if [ -n "$LOGIN_CID" ]; then
  export GOOGLE_ADS_LOGIN_CUSTOMER_ID="${LOGIN_CID//-/}"
fi

exec "$PYTHON" -m gads_write.server
