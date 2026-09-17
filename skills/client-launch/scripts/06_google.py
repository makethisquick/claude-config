"""Phase 6 — Google onboarding, STUDIO-OWNED: Search Console (URL-prefix property, META verification through
Rank Math, sitemap submitted) + GA4 (account → property → web stream → generate_lead key event → gtag injected
site-wide). Uses Application Default Credentials from the studio Google account. Ads draft is 07_ads.py.
Run with --dry-run first. Every human step is printed, never assumed."""
import sys, json, re, time, requests, os
from wp import *
try:
    import google.auth, google.auth.transport.requests
except ImportError:
    print("pip install google-auth in the skill venv first"); sys.exit(2)
cfg = load(sys.argv[1]); dry = "--dry-run" in sys.argv; wp = WP(cfg); G = cfg["google"]; b = cfg["brand"]; lines = []
SCOPES = ["https://www.googleapis.com/auth/webmasters", "https://www.googleapis.com/auth/siteverification", "https://www.googleapis.com/auth/analytics.edit"]
creds, _ = google.auth.default(scopes=SCOPES); creds.refresh(google.auth.transport.requests.Request())
S = requests.Session(); S.headers["Authorization"] = "Bearer " + creds.token
def call(method, url, **kw):
    r = S.request(method, url, **kw)
    if r.status_code >= 400: lines.append(f"ERR {method} {url.split('googleapis.com')[-1][:70]} {r.status_code} {r.text[:200]}"); return None
    return r.json() if r.text else {}
site_url = wp.site + "/"

# --- scope sanity: a 403 with "insufficient" means the ADC login lacks these scopes → human re-auth
t = call("GET", "https://www.googleapis.com/webmasters/v3/sites")
if t is None:
    report(cfg, "06 google", lines + ["HUMAN STEP: ADC lacks the Search Console / Analytics scopes. Add `webmasters`, `siteverification`, `analytics.edit` on the consent screen (Data Access) and re-run:",
        "  gcloud auth application-default login --client-id-file=$HOME/.config/gcloud/ads_oauth_client.json --scopes=https://www.googleapis.com/auth/adwords,https://www.googleapis.com/auth/cloud-platform," + ",".join(SCOPES)]); sys.exit(2)
owned = [s["siteUrl"] for s in t.get("siteEntry", [])]; lines.append(f"GSC properties visible to the studio account: {len(owned)}")

# --- Search Console: property + META verification via Rank Math + sitemap
if dry: lines.append(f"[dry] would add GSC property {site_url}, verify via Rank Math google_verify meta, submit {site_url}sitemap_index.xml")
else:
    if site_url not in owned: call("PUT", f"https://www.googleapis.com/webmasters/v3/sites/{requests.utils.quote(site_url, safe='')}")
    tok = call("POST", "https://www.googleapis.com/siteVerification/v1/token", json={"site": {"identifier": site_url, "type": "SITE"}, "verificationMethod": "META"})
    if tok:
        content = re.search(r'content="([^"]+)"', tok["token"]).group(1)
        requests.post(wp.site + "/wp-json/rankmath/v1/updateSettings", auth=wp.auth, json={"type": "general", "settings": {"google_verify": content}, "fieldTypes": {}, "updated": ["google_verify"]})
        wp.clear_cache(); time.sleep(3)
        live = content in requests.get(site_url, params={"cb": "gsc"}).text; lines.append(f"verification meta tag live: {live}")
        v = call("POST", "https://www.googleapis.com/siteVerification/v1/webResource?verificationMethod=META", json={"site": {"identifier": site_url, "type": "SITE"}})
        lines.append("GSC verified: " + ("yes" if v else "NO — check the meta tag and re-run"))
    sm = f"{site_url}sitemap_index.xml"; ok = None
    for attempt in range(6):   # ownership propagates a few seconds after verification; the first PUT 403s
        r = S.put(f"https://www.googleapis.com/webmasters/v3/sites/{requests.utils.quote(site_url, safe='')}/sitemaps/{requests.utils.quote(sm, safe='')}")
        if r.status_code < 400: ok = True; break
        time.sleep(10)
    lines.append(f"sitemap submitted: {sm}" if ok else f"SITEMAP NOT SUBMITTED ({r.status_code}) — re-run the phase in a minute")
    for owner in G.get("extra_owners", []):   # the client, added later as an owner of the GSC property
        call("POST", "https://www.googleapis.com/siteVerification/v1/webResource/" + requests.utils.quote(site_url, safe=''), json={"owners": [owner]})

# --- GA4: one account per client (transferable), property, web stream, key event, gtag site-wide
GA = "https://analyticsadmin.googleapis.com/v1beta"
acct = G.get("ga4_account")   # "accounts/123" once it exists
if not acct:
    accts = call("GET", GA + "/accounts") or {}; match = [a for a in accts.get("accounts", []) if a["displayName"] == G["ga4_account_name"]]
    if match: acct = match[0]["name"]
if not acct:
    if dry: lines.append(f"[dry] would provision GA4 account {G['ga4_account_name']!r} (needs one human ToS click)")
    else:
        tk = call("POST", GA + "/accounts:provisionAccountTicket", json={"account": {"displayName": G["ga4_account_name"], "regionCode": "US"}, "redirectUri": "https://analytics.google.com/"})
        if tk: report(cfg, "06 google", lines + [f"HUMAN STEP: accept the Google Analytics terms for the new account, then re-run: https://analytics.google.com/analytics/web/?provisioningSignup=false#/termsofservice/{tk['accountTicketId']}"]); sys.exit(2)
prop = G.get("ga4_property")
if acct and not prop and not dry:
    props = call("GET", GA + "/properties", params={"filter": f"parent:{acct}"}) or {}
    m = [p for p in props.get("properties", []) if p["displayName"] == b["site_title"]]
    prop = m[0]["name"] if m else call("POST", GA + "/properties", json={"parent": acct, "displayName": b["site_title"], "timeZone": b.get("timezone", "America/New_York"), "currencyCode": "USD", "industryCategory": G.get("industry", "OTHER")})["name"]
    streams = call("GET", GA + f"/{prop}/dataStreams") or {}; ws = [s for s in streams.get("dataStreams", []) if s["type"] == "WEB_DATA_STREAM"]
    stream = ws[0] if ws else call("POST", GA + f"/{prop}/dataStreams", json={"type": "WEB_DATA_STREAM", "displayName": wp.site.replace("https://", ""), "webStreamData": {"defaultUri": wp.site}})
    mid = stream["webStreamData"]["measurementId"]
    kes = call("GET", GA + f"/{prop}/keyEvents") or {}
    if not any(k["eventName"] == "generate_lead" for k in kes.get("keyEvents", [])): call("POST", GA + f"/{prop}/keyEvents", json={"eventName": "generate_lead", "countingMethod": "ONCE_PER_EVENT"})
    lines.append(f"GA4 {prop} stream {stream['name'].split('/')[-1]} measurementId {mid}; key event generate_lead")
    # gtag site-wide, same html-widget pattern as attribution; guarded so a re-run does not double-install
    snippet = ("<script data-elm-ga4=\"1\" async src=\"https://www.googletagmanager.com/gtag/js?id=" + mid + "\"></script><script data-elm-ga4c=\"1\">window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','" + mid + "',{anonymize_ip:true});</script>")
    n = 0
    for pg in wp.pages():
        els = json.loads(wp.page_data(pg["id"]) or "[]")
        if not els or "data-elm-ga4" in dumps(els): continue
        els.insert(0, {"id": f"g{pg['id']:06x}"[:7], "elType": "e-flexbox", "isInner": False, "settings": {"classes": {"$$type": "classes", "value": []}, "tag": {"$$type": "string", "value": "div"}, "_cssid": {"$$type": "string", "value": f"elm-ga4-{pg['id']}"}},
                        "elements": [{"id": f"h{pg['id']:06x}"[:7], "elType": "widget", "widgetType": "html", "elements": [], "settings": {"html": snippet}}], "styles": {}, "interactions": [], "editor_settings": [], "version": "4.2.2"})
        wp.set_page_data(pg["id"], dumps(els)); n += 1
    wp.clear_cache(); lines.append(f"gtag injected on {n} pages")
    for user in G.get("extra_owners", []):
        call("POST", GA + f"/{acct}/accessBindings", json={"user": user, "roles": ["predefinedRoles/admin"]})
    G.update({"ga4_account": acct, "ga4_property": prop, "ga4_measurement_id": mid}); json.dump(cfg, open(cfg["_path"], "w"), indent=1, ensure_ascii=False)
report(cfg, "06 google" + (" (dry run)" if dry else ""), lines)
