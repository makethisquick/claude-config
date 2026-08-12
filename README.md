# claude-config

Portable Claude Code setup: custom skills + MCP servers, shared between the Mac and
the Windows desktop. One repo, two bootstrap scripts, secrets kept out of git.

```
skills/                     custom skills, copied into ~/.claude/skills
servers/manifest.json       MCP server definitions, one posix + one windows variant each
servers/google-ads-write/   source of the local write-capable Google Ads MCP server
settings/settings.shared.json   the machine-independent slice of ~/.claude/settings.json
secrets/credentials.json    live credentials - GITIGNORED, moved by hand
bin/                        launcher scripts for the two Google Ads servers (.sh + .ps1)
bootstrap/                  bootstrap.sh (mac/linux), bootstrap.ps1 (windows), export.sh
```

## Setting up the Windows desktop

1. Install the prerequisites: [Claude Code](https://claude.com/claude-code),
   Node.js LTS, Python 3.11+, `pipx`, and the `gcloud` CLI.
2. Clone this repo to `%USERPROFILE%\projects\claude-config`.
3. Move `secrets/credentials.json` across **by hand** — password manager, encrypted
   drive, anything but git or email. It holds the WordPress app-password logins.
4. Fill in `googleAds.GOOGLE_ADS_DEVELOPER_TOKEN`. On the Mac it lives in the
   Keychain, not in any file; read it with:
   ```
   security find-generic-password -a claude -s google-ads-dev-token -w
   ```
5. Run it:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File bootstrap\bootstrap.ps1
   ```
   Add `-WhatIfOnly` first if you want to see the plan without writing anything.
6. Do the manual steps it prints — the `gcloud` login is the important one.
7. `claude mcp list` to confirm, then `/mcp` inside Claude Code to authenticate Box.

## Keeping the two machines in sync

Whichever machine you changed something on:

```bash
./bootstrap/export.sh          # skills + credentials -> repo
git add -A && git commit -m "..." && git push
```

On the other machine: `git pull`, then re-run bootstrap. Both scripts are idempotent
and back up `~/.claude.json` and `~/.claude/settings.json` with a timestamp first.

Adding a new MCP server is the one manual step: edit `servers/manifest.json` and
write **both** the `posix` and `windows` variants, so the next bootstrap on either
machine picks it up.

## What is and isn't portable

| Piece | Portable? |
| --- | --- |
| Skills (`google-ads-campaign`, `serenite-daily-ads-report`) | Yes — plain markdown + JSON |
| `box-remote-mcp` | Yes — remote HTTP; needs a one-time OAuth per machine |
| `serenite`, `elementor`, `emada1`, `makethisquick`, `lipglossluxe` | Yes — `npx mcp-remote`; Windows needs the `cmd /c` wrapper, which the manifest already has |
| `serenite-ads` | Needs porting — was a bash script reading the macOS Keychain |
| `serenite-ads-write` | Needs porting — plus a local Python venv, which is **never** synced; each machine builds its own |
| Credentials | Never in git |

Two things deliberately did not come across from the Mac's `settings.json`:

- `env.PATH` — it hardcodes `/opt/homebrew`, which is meaningless on Windows.
- The Keychain dependency in the Google Ads launchers. The Windows `.ps1` versions
  read the token from the `GOOGLE_ADS_DEVELOPER_TOKEN` environment variable or from
  `secrets/credentials.json` instead. The `.sh` versions still prefer the Keychain
  and fall back the same way, so the Mac's behaviour is unchanged.

## Gotchas

- **`google-ads-write` exists nowhere else.** It's a hand-written package that was
  only in `~/projects/mcp/google-ads-write` on the Mac, with no git history and no
  remote. `servers/google-ads-write/` is now its home; the old copy is still there
  but is no longer the one the MCP config points at after a bootstrap.
- **Virtualenvs don't move.** `.venv` is gitignored on purpose — bootstrap rebuilds
  it per machine.
- **The Windows desktop needs its own gcloud ADC.** Google Ads access is per-machine
  OAuth; nothing in this repo can carry it over.
- **`serenite-ads-write` writes to a live ad account.** Its dry-run/confirm gate is
  in the server itself, so it behaves identically on both machines.
