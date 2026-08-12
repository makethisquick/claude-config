#!/usr/bin/env bash
# Launch the official Google Ads MCP server (googleads/google-ads-mcp) over stdio.
#
# Portable rewrite of ~/projects/mcp/google-ads-mcp.sh: paths are relative to this
# repo instead of hardcoded to /Users/mike, and the developer token falls back to
# secrets/credentials.json on machines without a macOS Keychain.
#
# Usage (from servers/manifest.json):
#   <repo>/bin/google-ads-mcp.sh <gcp-project-id> [login-customer-id]

set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: $(basename "$0") <gcp-project-id> [login-customer-id]" >&2
  exit 64
fi

PROJECT_ID="$1"
LOGIN_CID="${2:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- developer token: env > Keychain (macOS) > credentials.json -------------
DEV_TOKEN="${GOOGLE_ADS_DEVELOPER_TOKEN:-}"

if [ -z "$DEV_TOKEN" ] && command -v security >/dev/null 2>&1; then
  DEV_TOKEN="$(security find-generic-password -a claude -s google-ads-dev-token -w 2>/dev/null || true)"
fi

if [ -z "$DEV_TOKEN" ] && [ -f "$ROOT/secrets/credentials.json" ]; then
  DEV_TOKEN="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('googleAds',{}).get('GOOGLE_ADS_DEVELOPER_TOKEN',''))" "$ROOT/secrets/credentials.json" 2>/dev/null || true)"
fi

if [ -z "$DEV_TOKEN" ]; then
  cat >&2 <<EOF
No Google Ads developer token. Provide one of:
  - export GOOGLE_ADS_DEVELOPER_TOKEN=...
  - macOS Keychain: security add-generic-password -a claude -s google-ads-dev-token -w '<token>'
  - googleAds.GOOGLE_ADS_DEVELOPER_TOKEN in $ROOT/secrets/credentials.json
The token is in Google Ads > Tools > Setup > API Center on the manager (MCC) account.
EOF
  exit 1
fi

# --- Application Default Credentials ---------------------------------------
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

# Google Ads shows customer IDs as 123-456-7890; the API wants them bare.
if [ -n "$LOGIN_CID" ]; then
  export GOOGLE_ADS_LOGIN_CUSTOMER_ID="${LOGIN_CID//-/}"
fi

if [ -x "$HOME/.local/bin/google-ads-mcp" ]; then
  exec "$HOME/.local/bin/google-ads-mcp"
fi

exec pipx run --spec git+https://github.com/googleads/google-ads-mcp.git google-ads-mcp
