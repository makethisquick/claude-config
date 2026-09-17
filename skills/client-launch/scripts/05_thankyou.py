"""Phase 5 — thank-you pages (the lead conversion signal). Clones the form page's chrome per the studio build
convention (top-level containers with css ids elm-bilingual*/elm-enhance*/elm-header*/elm-hero*/elm-sec-black-footer*),
rewrites the hero copy, appends the generate_lead event, sets noindex, and points the form redirect at it.
If the site was NOT built with the studio conventions, set thank_you.mode = "existing" and give page_id per language."""
import sys, json, copy, secrets, re, requests
from wp import *
cfg = load(sys.argv[1]); wp = WP(cfg); lines = []; T = cfg["thank_you"]
KEEP = tuple(T.get("keep_prefixes", ["elm-bilingual", "elm-enhance", "elm-header", "elm-hero", "elm-sec-black-footer"]))
def newids(e):
    e["id"] = secrets.token_hex(4)[:7]
    for k in e.get("elements", []): newids(k)
def settext(w, key, text): w["settings"][key]["value"]["content"]["value"] = text
def lead_event(lang):
    return {"id": secrets.token_hex(4)[:7], "elType": "widget", "widgetType": "html", "elements": [], "settings": {"html":
      "<script data-elm-lead=\"1\">(function(){try{var p={event:'generate_lead',lead_source:'website_form',form_language:'" + lang + "',page_path:location.pathname};"
      "window.dataLayer=window.dataLayer||[];window.dataLayer.push(p);if(typeof window.gtag==='function'){window.gtag('event','generate_lead',{lead_source:'website_form',form_language:'" + lang + "'});}}catch(e){}})();</script>"}}
for lang, t in T["languages"].items():
    if T.get("mode") == "existing":
        pid = t["page_id"]; link = wp.get(f"/wp/v2/pages/{pid}", _fields="link")["link"]
    else:
        src = json.loads(wp.page_data(t["clone_from_page_id"])); out = []
        for e in src:
            k = cid(e)
            if not k.startswith(KEEP): continue
            e = copy.deepcopy(e); newids(e)
            if k.startswith("elm-bilingual"):
                h = e["elements"][0]["settings"]["html"]
                h = re.sub(r'SELF="[^"]*"', f'SELF="{t["path"]}"', h); h = re.sub(r'\bEN="[^"]*"', f'EN="{T["languages"]["en"]["path"]}"', h)
                if "es" in T["languages"]: h = re.sub(r'\bES="[^"]*"', f'ES="{T["languages"]["es"]["path"]}"', h)
                e["elements"][0]["settings"]["html"] = h
            if k.startswith("elm-enhance"): e["elements"].append(lead_event(lang))
            if k.startswith("elm-header"):
                for w in e["elements"]:
                    if w.get("widgetType") == "html" and "elm-logo" not in str(w["settings"].get("_element_id", "")):
                        for a, bb in t.get("header_replacements", {}).items(): w["settings"]["html"] = w["settings"]["html"].replace(a, bb)
            if k.startswith("elm-hero"):
                kids = e["elements"]
                for w in kids:
                    c = cid(w)
                    if c.startswith("elm-eyebrow"): settext(w, "paragraph", t["eyebrow"])
                    elif c.startswith("elm-h1"): settext(w, "title", t["h1"])
                    elif c.startswith("elm-lede"): settext(w, "paragraph", t["lede"])
                    elif c.startswith("elm-ctarow"):
                        primary = w["elements"][0]; back = copy.deepcopy(primary); newids(back); settext(back, "text", t["back_label"])
                        back["settings"]["link"]["value"]["destination"]["value"] = t["home_path"]; back["settings"]["_cssid"]["value"] = "elm-btn-secondary-tyhome"
                        w["elements"] = [primary, back]
            out.append(e)
        ex = [p for p in wp.get("/wp/v2/pages", slug=t["slug"], status="any") if p["parent"] == t.get("parent", 0)]
        payload = {"title": t["title"], "slug": t["slug"], "status": "publish", "template": "elementor_canvas", "parent": t.get("parent", 0),
                   "meta": {"_elementor_data": dumps(out), "_elementor_edit_mode": "builder", "_elementor_template_type": "wp-page"}}
        r = wp.post(f"/wp/v2/pages/{ex[0]['id']}", payload) if ex else wp.post("/wp/v2/pages", payload); pid = r["id"]; link = r["link"]
    requests.post(wp.site + "/wp-json/rankmath/v1/updateMeta", auth=wp.auth, json={"objectID": pid, "objectType": "post", "meta": {"rank_math_title": t["seo_title"], "rank_math_description": t.get("seo_description", ""), "rank_math_robots": ["noindex", "nofollow"]}})
    t["_page_id"] = pid; t["_url"] = link; lines.append(f"{lang}: thank-you page {pid} {link} (noindex)")
wp.clear_cache()
# verify: noindex + lead event present + not in sitemap
for lang, t in T["languages"].items():
    h = requests.get(t["_url"], params={"cb": "v", "nolang": 1}).text
    lines.append(f"{lang}: robots={'noindex' in h} lead_event={'data-elm-lead' in h} h1={'<h1' in h}")
sm = requests.get(wp.site + "/page-sitemap.xml").text; lines.append(f"thank-you URLs in sitemap: {any(t['_url'] in sm for t in T['languages'].values())} (want False)")
json.dump({l: {"id": t["_page_id"], "url": t["_url"]} for l, t in T["languages"].items()}, open(cfg["_path"].replace("launch.json", "launch-runs/thankyou_ids.json"), "w"))
report(cfg, "05 thank-you pages", lines)
