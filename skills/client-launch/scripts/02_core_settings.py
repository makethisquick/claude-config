"""Phase 2 — WordPress core settings + site icon + front page. Idempotent."""
import sys, json, requests
from wp import *
cfg = load(sys.argv[1]); wp = WP(cfg); b = cfg["brand"]; lines = []
payload = {"title": b["site_title"], "description": b["tagline"], "timezone": b.get("timezone", "America/New_York")}
front = cfg.get("front_page_id")
if front: payload.update({"show_on_front": "page", "page_on_front": front})
icon = cfg.get("assets", {}).get("site_icon_id")
if icon: payload["site_icon"] = icon
r = wp.post("/wp/v2/settings", payload)
lines.append(f"title={r['title']!r} tagline={r['description']!r} tz={r['timezone']} front={r['show_on_front']}/{r['page_on_front']} icon={r['site_icon']}")
h = requests.get(wp.site + "/", params={"cb": "x"}).text
lines.append(f"root <title>: {h.split('<title>')[1].split('</title>')[0] if '<title>' in h else '?'}; favicon tag present: {'rel=\"icon\"' in h}")
report(cfg, "02 core settings", lines)
