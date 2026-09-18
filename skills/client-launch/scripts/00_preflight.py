"""Phase 0 — preflight. Verifies everything the skill needs from the MACHINE (not the client) and prints the exact
fix for anything missing. Run first, every time. Exit 1 if a blocker remains."""
import os, sys, json, subprocess, shutil
HOME = os.path.expanduser("~"); ok = True
def fail(msg, fix=None):
    global ok; ok = False; print("MISSING:", msg); 
    if fix: print("   fix →", fix)
# 1. permission rules the agent needs (the auto-mode classifier blocks these without an allow rule)
NEEDED = ["Bash(security find-generic-password -s wp-*:*)", "Bash(~/.claude/skills/client-launch/scripts/ads_env.sh:*)"]
try:
    allow = json.load(open(f"{HOME}/.claude/settings.json")).get("permissions", {}).get("allow", [])
    for rule in NEEDED:
        if rule not in allow:
            fail(f"permission rule {rule}", "! python3 -c \"import json,os;p=os.path.expanduser('~/.claude/settings.json');d=json.load(open(p));d.setdefault('permissions',{}).setdefault('allow',[]).append('" + rule + "');json.dump(d,open(p,'w'),indent=2);print('done')\"  (Mike runs this — the agent cannot edit its own permissions)")
        else: print("ok  rule:", rule)
except Exception as e: fail(f"could not read ~/.claude/settings.json ({e})")
# 2. tooling
for path, fix in [(f"{HOME}/.claude/skills/client-launch/.venv/bin/python", "python3 -m venv ~/.claude/skills/client-launch/.venv && ~/.claude/skills/client-launch/.venv/bin/pip install requests google-auth"),
                  ("/Users/mike/projects/mcp/google-ads-write/.venv/bin/python", "see ~/projects/mcp/google-ads-write/README.md")]:
    print("ok  ", path) if os.path.exists(path) else fail(path, fix)
for tool in ("gcloud", "curl", "cwebp"):
    print("ok  ", tool) if shutil.which(tool) else fail(f"{tool} on PATH")
# 3. Google: ADC present with the five scopes; Ads developer token in the Keychain
try:
    tok = subprocess.check_output(["gcloud", "auth", "application-default", "print-access-token"], stderr=subprocess.DEVNULL).decode().strip()
    import urllib.request; info = json.load(urllib.request.urlopen("https://oauth2.googleapis.com/tokeninfo?access_token=" + tok))
    have = set(info.get("scope", "").split()); need = {"https://www.googleapis.com/auth/" + s for s in ("adwords", "cloud-platform", "webmasters", "siteverification", "analytics.edit")}
    missing = need - have
    print("ok   ADC scopes") if not missing else fail(f"ADC scopes {sorted(s.split('/')[-1] for s in missing)}", "see SKILL.md → Google one-time prerequisites (re-auth command)")
except Exception as e: fail(f"ADC not usable ({str(e)[:80]})", "gcloud auth application-default login … (SKILL.md)")
try:
    subprocess.check_output(["security", "find-generic-password", "-a", "claude", "-s", "google-ads-dev-token", "-w"], stderr=subprocess.DEVNULL); print("ok   Ads developer token in Keychain")
except Exception: fail("Keychain entry google-ads-dev-token (account claude)", "security add-generic-password -a claude -s google-ads-dev-token -w '<token>'")
# 3b. Ads API access level: CreateCustomerClient with validate_only — proves the dev token is Basic+ without creating anything
try:
    out = subprocess.run([f"{HOME}/.claude/skills/client-launch/scripts/ads_env.sh", "07_ads_account.py", "--selftest"], capture_output=True, text=True, timeout=90)
    print(out.stdout.strip()) if out.returncode == 0 else fail("Ads API CreateCustomerClient self-test: " + (out.stdout + out.stderr).strip()[-300:])
except Exception as e: fail(f"Ads self-test could not run ({str(e)[:80]})")
# 4. the client config, if given
if len(sys.argv) > 1:
    cfg = json.load(open(sys.argv[1])); slug = cfg["slug"]
    try: subprocess.check_output(["security", "find-generic-password", "-s", cfg.get("keychain_service", "wp-" + slug), "-w"], stderr=subprocess.DEVNULL); print("ok   Keychain wp-" + slug)
    except Exception: fail(f"Keychain entry wp-{slug}", "run the wp-mcp-onboard skill for this client first")
    missing = [p["id"] for p in cfg["seo"]["pages"] if not p.get("title") or not p.get("description")]
    print("ok   every page has title+description") if not missing else fail(f"seo.pages without title/description: {missing}")
print("\nPREFLIGHT", "PASS" if ok else "FAIL — fix the items above, then re-run"); sys.exit(0 if ok else 1)
