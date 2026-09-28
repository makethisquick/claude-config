"""Track taps on the site's phone numbers (2026-09-28).

Gap found in week 1: the site's primary CTA is `tel:` links (7 on the homepage alone) and nothing fired
on a tap, so a visitor who clicked an ad, landed, and phoned was invisible to Ads and GA4. This injects a
delegated click handler into the existing site-wide `elm-enhance` html widget on every published page —
same mechanism as attribution.py — firing the Ads conversion 'Phone call from website' plus a GA4
generate_lead. Idempotent: skips any page already carrying data-elm-tel.
"""
from wpapi import *
import json, sys

SEND_TO = "AW-18456609992/JSMzCPaT7YgdEMiJ5uBE"   # Ads action 'Phone call from website', created 2026-09-28

SCRIPT = r"""
<script data-elm-tel="1">
/* Phone-tap tracking (2026-09-28). The phone number IS the primary call-to-action on this site, so a tap
   is a lead. Delegated listener so it covers the header button, the hero CTA, the sticky mobile bar and
   the footer without touching their markup. Deduped per page view; Ads counts one per ad click. */
(function(){
  try{
    var SEND_TO='__SEND_TO__', fired={};
    document.addEventListener('click', function(e){
      var a = e.target && e.target.closest && e.target.closest('a[href^="tel:"]');
      if(!a) return;
      var num=(a.getAttribute('href')||'').replace(/[^0-9+]/g,'');
      if(fired[num]) return; fired[num]=1;
      var es = (document.documentElement.lang||'').toLowerCase().indexOf('es')===0 || location.pathname.indexOf('/es/')===0;
      if(typeof gtag==='function'){
        gtag('event','conversion',{send_to:SEND_TO, value:50, currency:'USD'});
        gtag('event','generate_lead',{lead_source:'website_phone', form_language: es?'es':'en'});
      }
      if(window.dataLayer) window.dataLayer.push({event:'phone_tap', lead_source:'website_phone', form_language: es?'es':'en'});
    }, true);
  }catch(e){}
})();
</script>""".replace("__SEND_TO__", SEND_TO)

def published_pages():
    out, page = {}, 1
    while True:
        rows = get("/wp/v2/pages", context="edit", status="publish", per_page=100, page=page, _fields="id,slug")
        if not rows: break
        for r in rows: out[r["id"]] = r["slug"]
        if len(rows) < 100: break
        page += 1
    return out

def inject(dry=True):
    pages = published_pages(); done=skip=nohost=0
    for pid, slug in sorted(pages.items()):
        els = json.loads(page_data(pid)); hit=[0]; already=[0]; host=[0]
        def walk(l):
            for e in l:
                s = e.get("settings", {})
                h = str(s.get("html", "")) if e.get("widgetType") == "html" else ""
                if h:
                    if "data-elm-tel" in h: already[0] += 1
                    if "data-elm-enhance" in h:
                        host[0] += 1
                        if "data-elm-tel" not in h:
                            s["html"] = s["html"] + SCRIPT; hit[0] += 1
                walk(e.get("elements", []))
        walk(els)
        if already[0]: print(f"  {pid:>3} {slug:<34} already tracked"); skip += 1; continue
        if not host[0]: print(f"  {pid:>3} {slug:<34} NO enhance widget — skipped"); nohost += 1; continue
        if hit[0]:
            if not dry: set_page_data(pid, json.dumps(els, ensure_ascii=False, separators=(",", ":")))
            print(f"  {pid:>3} {slug:<34} {'would inject' if dry else 'INJECTED'}"); done += 1
    print(f"\n{'DRY RUN — ' if dry else ''}injected {done}, already {skip}, no-host {nohost}, total pages {len(pages)}")
    if not dry and done: clear_elementor_cache()

if __name__ == "__main__":
    inject(dry="--go" not in sys.argv)
