#!/bin/bash
# Authenticated WP REST call for ONE client, scoped by build.json. Usage: wp.sh <build.json> METHOD <path> [json-body]
set -euo pipefail
CFG="$1"; M="$2"; P="$3"
read -r SLUG HOST USER < <(python3 -I -c 'import json,sys;c=json.load(open(sys.argv[1]));print(c["slug"],c["host"],c["wp_user"])' "$CFG")
PW=$(security find-generic-password -a claude -s "wp-$SLUG" -w | tr -d ' ')
AUTH=$(printf '%s:%s' "$USER" "$PW" | base64 | tr -d '\n')
if [ $# -ge 4 ]; then curl -s -m 60 -X "$M" -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" -d "$4" "https://$HOST/wp-json/$P"
else curl -s -m 60 -X "$M" -H "Authorization: Basic $AUTH" "https://$HOST/wp-json/$P"; fi
