"""Phase 1 — cutover hygiene. Read-only except the explicit fixes it names. Exit non-zero if a blocker remains."""
import sys, re, json, requests
from wp import *
cfg = load(sys.argv[1]); wp = WP(cfg); lines = []; blockers = []
site = wp.site; old_hosts = cfg.get("old_hosts", [])

s = wp.get("/wp/v2/settings")
lines.append(f"url={s.get('url')} title={s.get('title')!r} tagline={s.get('description')!r} tz={s.get('timezone')!r} front={s.get('show_on_front')}/{s.get('page_on_front')} icon={s.get('site_icon')}")
if s.get("url", "").rstrip("/") != site: blockers.append(f"WordPress url is {s.get('url')} — change the primary domain in the host panel first")

# noindex must be lifted on the live domain
h = requests.get(site + "/", params={"cb": "launch"}); xr = h.headers.get("x-robots-tag", "")
robots = requests.get(site + "/robots.txt").text
lines.append(f"x-robots-tag={xr!r}; robots.txt disallow-all={'Disallow: /' in robots.replace('Disallow: /wp-admin/', '')}")
if "noindex" in xr: blockers.append("host still sends x-robots-tag: noindex on the live domain")

# old hostnames inside Elementor data / rendered HTML
pages = wp.pages(); stale = {}
for p in pages:
    d = wp.page_data(p["id"]) or ""
    for oh in old_hosts:
        if oh in d: stale.setdefault(p["id"], []).append(oh)
html_stale = [oh for oh in old_hosts if oh in h.text]
lines.append(f"pages={len(pages)}; pages with old host in _elementor_data={len(stale)}; old host in rendered home HTML={html_stale}")
if stale and cfg.get("fix", {}).get("replace_old_hosts"):
    for pid, hosts in stale.items():
        d = wp.page_data(pid)
        for oh in hosts: d = d.replace(oh, site.replace("https://", ""))
        wp.set_page_data(pid, d)
    lines.append(f"replaced old hosts in {len(stale)} pages"); wp.clear_cache()
elif stale: blockers.append(f"old hostnames remain in {len(stale)} pages (set fix.replace_old_hosts=true to rewrite)")

# WordPress defaults that should not be live
junk = [p for p in wp.get("/wp/v2/posts", per_page=20, status="any", _fields="id,slug,status") if p["slug"] == "hello-world"]
junk += [p for p in wp.pages(status="any") if p["slug"] in ("sample-page",) or (p["slug"] == "" and "Elementor #" in p["title"]["rendered"])]
lines.append(f"default content still present: {[(j['id'], j['slug'] or j['title']['rendered']) for j in junk]}")
if junk and cfg.get("fix", {}).get("delete_defaults"):
    for j in junk:
        kind = "posts" if j["slug"] == "hello-world" else "pages"
        code, _ = wp.delete(f"/wp/v2/{kind}/{j['id']}", force="true"); lines.append(f"deleted {kind}/{j['id']} -> {code}")

# other SEO / form plugins — DETECT, never deactivate (Mike, 2026-09-15)
KNOWN_SEO = {"wpmu-dev-seo": "SmartCrawl", "wordpress-seo": "Yoast", "seo-by-rank-math": "Rank Math", "all-in-one-seo-pack": "AIOSEO", "autodescription": "The SEO Framework"}
KNOWN_FORMS = {"forminator": "Forminator", "fluentform": "Fluent Forms", "contact-form-7": "CF7", "wpforms-lite": "WPForms", "gravityforms": "Gravity Forms", "ninja-forms": "Ninja Forms"}
active = [p["plugin"] for p in wp.plugins() if p["status"] == "active"]
seo = [KNOWN_SEO[k] for k in KNOWN_SEO if any(a.startswith(k + "/") for a in active)]
forms = [KNOWN_FORMS[k] for k in KNOWN_FORMS if any(a.startswith(k + "/") for a in active)]
lines.append(f"active SEO plugins: {seo or 'none'}; active form plugins: {forms or 'none'}")
if len(seo) > 1 or (seo and "Rank Math" not in seo): blockers.append(f"SEO plugin decision needed — active: {seo}. HUMAN DECIDES what stays; do not deactivate automatically")
if len(forms) > 1: lines.append(f"NOTE more than one form plugin active: {forms} — ask before deactivating any")

# pending / placeholder / agency-internal copy that must not face a client on a live site (learning 2026-09-17)
PEND = re.compile(r"pending|to be confirmed|verification in progress|not published|placeholder|not written yet|before this page goes live|to be supplied|pendiente de|por confirmar|verificaci[oó]n en curso|en preparaci[oó]n|in preparation", re.I)
pend = {}
for p in pages:
    d = wp.page_data(p["id"]) or ""
    for m in re.finditer(r'"value":"([^"]{20,400})"', d):
        t = m.group(1)
        if PEND.search(t): pend.setdefault(p["slug"] or "home", []).append(t[:80])
    for m in re.finditer(r'"html":"(.*?)","', d):
        t = re.sub(r"<[^>]+>", " ", m.group(1))
        if "<script" not in m.group(1) and PEND.search(t): pend.setdefault(p["slug"] or "home", []).append(re.sub(r"\\s+", " ", t)[:80])
lines.append(f"pending/placeholder copy on {len(pend)} pages" + (": " + "; ".join(f"{k} ({len(v)})" for k, v in list(pend.items())[:12]) if pend else ""))
if pend: lines.append("NOTE: these are client questions, not blockers — put them in the 'what we need from you' doc and apply answers with the answers_apply pattern (templates/)")
report(cfg, "01 cutover check", lines + ([f"BLOCKER: {b}" for b in blockers] or ["no blockers"]))
sys.exit(1 if blockers else 0)
