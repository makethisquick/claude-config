"""Draft a launch.json skeleton from a live site: enumerates published pages so titles/descriptions can be filled.
Usage: 00_draft_config.py <site_url> <wp_user> <slug> > ~/projects/<Client>/launch.json"""
import sys, json, subprocess, requests
site, user, slug = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
pw = subprocess.check_output(["security", "find-generic-password", "-s", "wp-" + slug, "-w"]).decode().strip()
pages = requests.get(site + "/wp-json/wp/v2/pages", auth=(user, pw), params={"per_page": 100, "status": "publish", "_fields": "id,slug,link,parent,title"}).json()
tpl = json.load(open(__file__.replace("scripts/00_draft_config.py", "templates/launch.example.json")))
tpl.update({"slug": slug, "site_url": site, "wp_user": user, "keychain_service": "wp-" + slug})
tpl["seo"]["pages"] = [{"id": p["id"], "url": p["link"], "path": p["link"].replace(site, ""), "title": "", "description": ""} for p in pages]
print(json.dumps(tpl, indent=1, ensure_ascii=False))
