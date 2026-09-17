"""Phase 3 — Rank Math. Install → (human: dismiss the registration gate) → configure → per-page meta → redirects → verify.
Never deactivates another SEO plugin; 01_cutover_check surfaces that decision to a human."""
import sys, json, requests, re
from wp import *
cfg = load(sys.argv[1]); wp = WP(cfg); lines = []; seo = cfg["seo"]; b = cfg["brand"]
PLUGIN = "seo-by-rank-math/rank-math"

p = wp.plugin(PLUGIN)
if not p: p = wp.install_plugin("seo-by-rank-math", "active"); lines.append(f"installed Rank Math {p.get('version')}")
elif p["status"] != "active": wp.set_plugin(PLUGIN, "active"); lines.append("activated Rank Math")
ns = wp.get("/", cb="1")["namespaces"]
if not any("rankmath" in n for n in ns):
    report(cfg, "03 rank math", lines + [f"HUMAN STEP: Rank Math is gated on its registration screen. Open {wp.site}/wp-admin/admin.php?page=rank-math-registration and click 'Skip Now', then re-run this phase."]); sys.exit(2)

def rm(path, payload):
    r = requests.post(wp.site + "/wp-json/rankmath/v1" + path, auth=wp.auth, json=payload)
    if r.status_code >= 400: lines.append(f"ERR {path} {r.status_code} {r.text[:200]}")
    return r.json() if r.text else None

for module, state in seo.get("modules", {"rich-snippet": "off", "redirections": "on", "404-monitor": "on", "content-ai": "off", "ai-visibility": "off", "instant-indexing": "off", "sitemap": "on", "seo-analysis": "on", "link-counter": "on", "analytics": "on", "image-seo": "on"}).items():
    rm("/saveModule", {"module": module, "state": state})
lines.append("modules set (schema OFF unless seo.modules says otherwise — hand-authored JSON-LD is the studio default)")

og = cfg.get("assets", {}).get("og_image", {})
titles = {"title_separator": seo.get("separator", "|"), "capitalize_titles": "off",
          "knowledgegraph_type": "company", "knowledgegraph_name": b["site_title"], "website_name": b["site_title"], "website_alternate_name": b.get("short_name", b["site_title"]),
          "twitter_card_type": "summary_large_image", "disable_author_archives": "on", "disable_date_archives": "on", "noindex_search": "on", "noindex_archive_subpages": "on", "noindex_paginated_pages": "on",
          "pt_page_title": "%title% %sep% %sitename%", "pt_page_description": "", "pt_page_default_rich_snippet": "off", "pt_post_default_rich_snippet": "off",
          "pt_attachment_robots": ["noindex"], "pt_attachment_custom_robots": "on", "tax_category_robots": ["noindex"], "tax_category_custom_robots": "on",
          "pt_e-floating-buttons_robots": ["noindex"], "pt_e-floating-buttons_custom_robots": "on"}
if og.get("url"): titles.update({"open_graph_image": og["url"], "open_graph_image_id": str(og["id"])})
logo = cfg.get("assets", {}).get("logo_stacked", {})
if logo.get("url"): titles.update({"knowledgegraph_logo": logo["url"], "knowledgegraph_logo_id": str(logo["id"])})
home = next((pg for pg in seo["pages"] if pg["id"] == cfg.get("front_page_id")), None)
if home: titles.update({"homepage_title": home["title"], "homepage_description": home["description"]})
r = rm("/updateSettings", {"type": "titles", "settings": titles, "fieldTypes": {}, "updated": list(titles)}); lines.append("titles settings: " + ("ok" if isinstance(r, dict) and "settings" in r else str(r)[:120]))
sm = {"authors_sitemap": "off", "tax_category_sitemap": "off", "pt_post_sitemap": "on" if cfg.get("has_blog") else "off", "pt_e-floating-buttons_sitemap": "off", "pt_product_sitemap": "off", "pt_attachment_sitemap": "off", "html_sitemap": "off", "include_images": "on"}
r = rm("/updateSettings", {"type": "sitemap", "settings": sm, "fieldTypes": {}, "updated": list(sm)}); lines.append("sitemap settings: " + ("ok" if isinstance(r, dict) and "settings" in r else str(r)[:120]))
gen = {"breadcrumbs": "off", "attachment_redirect_urls": "on", "404_monitor_mode": "simple", "redirections_header_code": "301", "frontend_seo_score": "off", "analytics_stats": "off"}
r = rm("/updateSettings", {"type": "general", "settings": gen, "fieldTypes": {}, "updated": list(gen)}); lines.append("general settings: " + ("ok" if isinstance(r, dict) and "settings" in r else str(r)[:120]))

missing = []
for pg in seo["pages"]:
    if not pg.get("title") or not pg.get("description"): missing.append(pg["id"]); continue
    meta = {"rank_math_title": pg["title"], "rank_math_description": pg["description"], "rank_math_robots": pg.get("robots", ["index"]), "rank_math_twitter_use_facebook": "on"}
    img = pg.get("og_image") or og
    if img.get("url"): meta.update({"rank_math_facebook_image": img["url"], "rank_math_facebook_image_id": img["id"]})
    rm("/updateMeta", {"objectID": pg["id"], "objectType": "post", "meta": meta})
lines.append(f"per-page meta written for {len(seo['pages']) - len(missing)} pages; pages missing title/description: {missing or 'none'}")
for src, dst in seo.get("redirects", []):
    rm("/updateSettings", {"type": "redirections", "settings": {"sources": [{"pattern": src.strip("/"), "comparison": "exact", "ignore": ""}], "url_to": wp.site + dst, "header_code": "301", "status": "active"}})
lines.append(f"redirects: {len(seo.get('redirects', []))}")
wp.clear_cache()

# verify every page head
bad = []
for pg in seo["pages"]:
    if pg["id"] in missing: continue
    h = requests.get(pg["url"], params={"cb": "v"}).text
    t = re.search(r"<title>([^<]*)</title>", h); d = re.search(r'<meta name="description" content="([^"]*)"', h); c = re.search(r'<link rel="canonical" href="([^"]*)"', h); o = re.search(r'<meta property="og:image" content="([^"]*)"', h)
    ok = t and t.group(1).replace("&amp;", "&") == pg["title"] and d and d.group(1).replace("&amp;", "&") == pg["description"] and c and c.group(1) == pg["url"] and (o is not None)
    if not ok: bad.append((pg["url"], t and t.group(1), c and c.group(1)))
lines.append("head verified on all pages" if not bad else f"HEAD MISMATCH on {len(bad)}: {bad[:3]}")
smap = requests.get(wp.site + "/sitemap_index.xml"); lines.append(f"sitemap_index: {smap.status_code}")
report(cfg, "03 rank math", lines); sys.exit(1 if bad else 0)
