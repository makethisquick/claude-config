#!/bin/bash
# Direct JSON-RPC call to ONE client's Elementor MCP server, scoped by a build.json.
# Usage: mcp.sh <build.json> <tool-without-prefix> '<json-arguments>'
# build.json: {"slug":"taskrunnerz","host":"taskrunnerz.com","wp_user":"makethisquick","production":true}
# Keychain service is always wp-<slug>. One config = one site: never edit this script to point anywhere.
set -euo pipefail
CFG="$1"; TOOL="elementor-mcp-$2"; ARGS="${3:-{\}}"
read -r SLUG HOST USER < <(python3 -I -c 'import json,sys;c=json.load(open(sys.argv[1]));print(c["slug"],c["host"],c["wp_user"])' "$CFG")
U="https://$HOST/wp-json/mcp/elementor-mcp-server"
PW=$(security find-generic-password -a claude -s "wp-$SLUG" -w | tr -d ' ')
AUTH=$(printf '%s:%s' "$USER" "$PW" | base64 | tr -d '\n')
H=(-H "Authorization: Basic $AUTH" -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream")
SID=$(curl -s -m 30 -D - -o /dev/null -X POST "${H[@]}" -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"woo-elementor-build","version":"1"}}}' "$U" | grep -i '^mcp-session-id' | awk '{print $2}' | tr -d '\r')
[ -n "$SID" ] || { echo "ERROR: no Mcp-Session-Id from $HOST (auth or plugin problem)"; exit 1; }
BODY=$(python3 -I -c 'import json,sys;print(json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":sys.argv[1],"arguments":json.loads(sys.argv[2])}}))' "$TOOL" "$ARGS")
curl -s -m 180 -X POST "${H[@]}" -H "Mcp-Session-Id: $SID" -d "$BODY" "$U" | python3 -I -c 'import json,sys
d=json.load(sys.stdin); r=d.get("result")
if r is None: print("ERROR", json.dumps(d.get("error"))); sys.exit(1)
sc=r.get("structuredContent")
print(json.dumps(sc if sc is not None else [c.get("text") for c in r.get("content",[])], indent=1)); sys.exit(1 if r.get("isError") else 0)'
