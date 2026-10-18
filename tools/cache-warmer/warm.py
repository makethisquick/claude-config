#!/usr/bin/env python3
"""Keep client page caches warm so real visitors never pay for a cold render.

Why this exists: on a slow hosting tier the gap between a cached and an uncached
page is the whole user experience. Eliminatis serves a warm page in ~0.09s and a
cold one in 1.4-2.3s - the site build is fine, the server just executes PHP about
3.5x slower than our other sites. Its cache TTL is locked at 1 hour by the hosting
plan and only the homepage is preloaded, so every other page goes cold every hour
and whoever arrives next pays the 2s. On a low-traffic site that is frequently a
paid ad click, which is exactly the visitor we can least afford to make wait.

Walking the sitemap on a schedule puts essentially every real visitor on the warm
path, which closes the gap without upgrading anything.

Standard library only, so CI needs no install step.
"""

import argparse
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

# A bot-looking request can be served differently (or blocked by the WAF), and we
# want to warm the exact cache entry a human would hit - so we present as a browser.
BASE_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-transform",
}

TIMEOUT = 45
CTX = ssl.create_default_context()


def fetch(url, lang="en-US,en;q=0.9", method="GET"):
    """Return (status, x-cache, seconds, bytes). Never raises for HTTP errors."""
    headers = dict(BASE_HEADERS, **{"Accept-Language": lang})
    req = urllib.request.Request(url, headers=headers, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as r:
            body = r.read()
            return r.status, (r.headers.get("x-cache") or "-"), time.perf_counter() - t0, len(body)
    except urllib.error.HTTPError as e:
        return e.code, (e.headers.get("x-cache") if e.headers else "-") or "-", time.perf_counter() - t0, 0
    except Exception as e:                                    # DNS, TLS, timeout
        return f"ERR:{type(e).__name__}", "-", time.perf_counter() - t0, 0


def locs(xml_bytes):
    return re.findall(rb"<loc>\s*([^<\s]+)\s*</loc>", xml_bytes)


def sitemap_urls(sitemap_url):
    """Expand a sitemap (or sitemap index) into the page URLs it points at."""
    req = urllib.request.Request(sitemap_url, headers=BASE_HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as r:
        root = r.read()

    found = [u.decode() for u in locs(root)]
    # A sitemap index points at more sitemaps; a page sitemap points at pages.
    children = [u for u in found if u.endswith(".xml")]
    if not children:
        return found

    urls = []
    for child in children:
        try:
            req = urllib.request.Request(child, headers=BASE_HEADERS)
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as r:
                urls.extend(u.decode() for u in locs(r.read()))
        except Exception as e:
            print(f"    ! could not read sub-sitemap {child}: {e}", file=sys.stderr)
    return urls


def lang_for(url):
    """Match Accept-Language to the URL's own language.

    These sites redirect by browser language, so asking for a /es/ page with an
    English header bounces us to the English twin - we would warm one page twice
    and leave its translation cold.
    """
    return "es-ES,es;q=0.9" if "/es/" in urlparse(url).path else "en-US,en;q=0.9"


def warm_site(site, delay, verbose):
    name = site["name"]
    print(f"\n=== {name}  ({site['sitemap']})")
    try:
        urls = sorted(set(sitemap_urls(site["sitemap"])))
    except Exception as e:
        print(f"    FAILED to read sitemap: {e}", file=sys.stderr)
        return {"name": name, "ok": False, "error": f"sitemap unreadable: {e}"}

    if not urls:
        print("    FAILED: sitemap contained no URLs", file=sys.stderr)
        return {"name": name, "ok": False, "error": "sitemap empty"}

    hits = misses = other = bad = 0
    slowest = []
    for url in urls:
        status, xcache, secs, size = fetch(url, lang=lang_for(url))
        state = (xcache or "-").upper()
        if status != 200:
            bad += 1
        elif state == "HIT":
            hits += 1
        elif state in ("MISS", "UPDATING", "EXPIRED"):
            misses += 1
        else:
            other += 1
        slowest.append((secs, url, state, status))
        if verbose or status != 200:
            print(f"    {str(status):>6}  {state:<8} {secs:5.2f}s  {size//1024:>4}KB  {url}")
        time.sleep(delay)

    slowest.sort(reverse=True)
    print(f"    {len(urls)} URLs | warm(HIT) {hits} | refreshed {misses} | other {other} | errors {bad}")
    if slowest and not verbose:
        print("    slowest:")
        for secs, url, state, status in slowest[:3]:
            print(f"      {secs:5.2f}s  {state:<8} {status}  {url}")

    # A page that was already HIT needed no warming; the ones we just refreshed are
    # precisely the cold pages a visitor would otherwise have hit. Both are success.
    return {"name": name, "ok": bad == 0, "urls": len(urls), "hits": hits,
            "refreshed": misses, "errors": bad}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(Path(__file__).with_name("sites.json")))
    ap.add_argument("--site", help="warm only this site name")
    ap.add_argument("--delay", type=float, default=0.4,
                    help="seconds between requests (default 0.4; these are small "
                         "shared servers, there is no hurry)")
    ap.add_argument("--verbose", action="store_true", help="print every URL")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    sites = [s for s in cfg["sites"] if s.get("enabled", True)]
    if args.site:
        sites = [s for s in sites if s["name"] == args.site]
    if not sites:
        print("No enabled sites matched.", file=sys.stderr)
        return 2

    started = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    print(f"cache warmer — {started}")

    results = [warm_site(s, args.delay, args.verbose) for s in sites]

    failed = [r for r in results if not r["ok"]]
    print("\n" + "-" * 60)
    for r in results:
        if r["ok"]:
            print(f"  OK    {r['name']}: {r['urls']} URLs, {r['refreshed']} refreshed, {r['hits']} already warm")
        else:
            print(f"  FAIL  {r['name']}: {r.get('error', str(r.get('errors')) + ' URL errors')}")

    # Exit non-zero so the scheduler surfaces a site that has gone down or whose
    # sitemap moved - a warmer that quietly stops working is worse than none.
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
