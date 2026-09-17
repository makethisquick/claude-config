---
name: wp-mcp-onboard
description: "Connect a client's WordPress/Elementor site to Claude Code as an MCP server, credentials in the macOS Keychain. Use when onboarding a new client site, wiring up a WP MCP connector, or when given a WordPress URL + username + application password and asked to hook it up. Verifies auth and the MCP endpoint before registering anything."
---

# Onboard a WordPress site as an MCP server

Takes a client's site from "here are the credentials" to a connected `mcp__<client>__*`
tool namespace. Every WP site in the studio is wired the same way — one Keychain entry,
one user-scoped stdio server, one line in the register.

## What you need before starting

| Input | Where it comes from | Example |
|---|---|---|
| Site host | The hosting panel | `eliminatis1.tempurl.host` |
| WP username | The admin user on that site | `euser109925` |
| Application password | WP Admin → Users → Profile → Application Passwords | `xxxx xxxx xxxx xxxx xxxx xxxx` (24 chars in 6 groups) |

A **regular login password will not work** — it must be an application password. The user
needs `edit_pages` plus Elementor rights. Application passwords are displayed with spaces;
store them exactly as shown, `wp-mcp.sh` strips them at launch.

Pick a **client slug** — lowercase, no punctuation, matching the client not the hostname
(`eliminatis`, not `eliminatis1`). It becomes both the Keychain service (`wp-<slug>`) and
the MCP server name (`<slug>`), which is what the tool namespace ends up called.

---

## Step 1 — Verify the credentials before anything else

Do this first. If auth is wrong, every later step fails in a way that looks like an MCP
problem and isn't.

```bash
AUTH=$(printf '%s:%s' '<username>' '<password-no-spaces>' | base64 | tr -d '\n')
curl -s -w "\nHTTP %{http_code}\n" -H "Authorization: Basic $AUTH" \
  https://<host>/wp-json/wp/v2/users/me
```

Expect `HTTP 200` and a JSON user object with an `id`.

- **`401`** — the password or username is wrong, or the host strips the `Authorization`
  header. Stop and resolve it; do not proceed to the Keychain.
- **`403`** — *not necessarily auth.* Some hosts' WAFs block `/wp-json/wp/v2/users/me`
  outright even with valid credentials (the NatureHeals host does exactly this). Don't
  read it as a failed login. Skip to step 2 — a successful MCP `initialize` proves the
  credentials independently, and that's the check that actually matters.

## Step 2 — Probe the MCP endpoint

Confirms the Elementor MCP plugin is actually installed and active on that site.

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST \
  -H "Authorization: Basic $AUTH" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' \
  https://<host>/wp-json/mcp/elementor-mcp-server
```

Expect a JSON-RPC result naming `MCP Tools for Elementor Server` and a version. A `404`
means the plugin isn't installed or activated — that's a site-side fix, not a config fix.
A `401` here **is** a real auth failure; unlike step 1 there's no WAF ambiguity.

This handshake is the authoritative go/no-go. If it succeeds, the site is ready.

## Step 3 — Store the password in the Keychain

Credentials live in exactly one place. Never put a password in `~/.claude.json`, a shell
profile, or a file in the repo.

```bash
security add-generic-password -a claude -s wp-<slug> -w '<password with spaces>' -U
security find-generic-password -a claude -s wp-<slug> -w >/dev/null && echo "readback OK"
```

`-U` updates an existing entry instead of erroring — safe for re-onboarding a site whose
password was rotated.

## Step 4 — Register the server

User scope, so the site is available from any directory. `wp-mcp.sh` takes exactly three
arguments: Keychain service, WP username, MCP endpoint URL.

```bash
claude mcp add <slug> --scope user \
  -- /Users/mike/projects/mcp/wp-mcp.sh wp-<slug> <username> \
     https://<host>/wp-json/mcp/elementor-mcp-server
```

## Step 5 — Confirm it connects

```bash
claude mcp list 2>&1 | grep <slug>
```

Expect `✔ Connected`. If it says otherwise, the fault is in the arguments — steps 1 and 2
already proved the site and credentials are fine.

**The `mcp__<slug>__*` tools do not appear in the session that registered them.** Claude
Code loads MCP servers at process start, so the registering session can't see them —
`ToolSearch` will come up empty. That is expected, not a failed onboarding.

You do **not** have to stop and wait, though. See step 7 — a fresh process has the tools
immediately, and that's the whole basis of the automated build path.

## Step 6 — Record it

Add a row to the site register in `/Users/mike/projects/mcp/README.md` — server name,
client, endpoint, and the Keychain service. That table is the only inventory of which
sites are wired; a connector missing from it will be forgotten.

Take a quick inventory of what's on the site so the next agent isn't guessing:

```bash
curl -s -H "Authorization: Basic $AUTH" \
  'https://<host>/wp-json/wp/v2/pages?per_page=20&status=any&_fields=id,slug,title,status'
```

A fresh install shows only `Sample Page`, `Privacy Policy`, and maybe an `Elementor #N`
draft. Note that in the register — "blank install" vs "existing site" changes whether the
next phase is a build or a migration.

## Step 7 — Build immediately, no restart

This is the part that makes onboarding continuous with building. The startup-only server
loading is a *process* limit, not an account or config limit: **a new `claude -p` process
picks up the just-registered server on its first call.** Verified on Eliminatis minutes
after registration.

Use `wp-build.sh`, which chains headless steps against one resumable session:

```bash
S=~/projects/<Client>/.build-session
/Users/mike/projects/mcp/wp-build.sh <slug> "$S" "Create a page 'Home'. Report its page id."
/Users/mike/projects/mcp/wp-build.sh <slug> "$S" "On that page, add the hero container."
```

Step 2 remembers step 1 — the script stores the `session_id` and passes `--resume`, so
page ids, decisions, and design tokens carry across calls without being re-stated. Delete
the state file to start a clean build.

**It passes `--allowedTools mcp__<slug>`, which is a real isolation boundary.** Tested: a
session scoped to `eliminatis` attempting `mcp__rojas__*` is refused by the harness with a
permissions error, before the model's judgement enters into it. Always scope to the one
client. Never widen it to `mcp__*` for convenience.

Two constraints worth knowing before leaning on this:

- **Headless means no prompts.** Anything not in the allowlist is denied outright rather
  than asked about. Grant exactly the servers a step needs.
- **Long buildouts are many small steps, not one giant prompt.** Each call is a fresh
  agent turn; keep instructions concrete and verify the result between steps.

If you'd rather build interactively with native tools, `claude -c` restarts and continues
the current conversation, so the restart costs context but not your place. That's a
preference, not a requirement.

---

## Rules that are not optional

**Cross-client isolation is absolute.** Before any write against a WP MCP server, confirm
the tool namespace matches the client you're working on. `mcp__rojas__*` must never touch
Nature Heals content and vice versa. Validate the target on every write, not once per
session.

**Watch which hosts are production.** Most studio sites are `*.tempurl.host` staging. At
least one (`serenite`) points at a live customer-facing domain where writes hit the real
site. If the endpoint isn't a `tempurl.host`, flag it in the register and treat every write
as a production change.

**Don't reuse another site's credential.** One Keychain service per site, named for the
client. Sharing an entry across two sites means rotating one breaks the other silently.
