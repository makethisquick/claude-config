#!/usr/bin/env bash
# Run a client-launch Ads phase with the Google Ads developer token from the Keychain and the shared ADC.
# usage: ads_env.sh <script.py> <launch.json> [args]
set -euo pipefail
SCRIPT="$1"; shift
export GOOGLE_ADS_DEVELOPER_TOKEN="$(security find-generic-password -a claude -s google-ads-dev-token -w)"
export GOOGLE_APPLICATION_CREDENTIALS="${GOOGLE_APPLICATION_CREDENTIALS:-$HOME/.config/gcloud/application_default_credentials.json}"
export GOOGLE_CLOUD_PROJECT=sereniteintelligence
exec /Users/mike/projects/mcp/google-ads-write/.venv/bin/python "$(dirname "$0")/$SCRIPT" "$@"
