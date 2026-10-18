# Cache warmer

Walks each configured site's sitemap on a schedule so its page cache never goes
cold. Runs as a GitHub Action (`.github/workflows/cache-warmer.yml`), every 30
minutes.

## Why

On 2026-10-17 we traced a "every page takes 3-5 seconds" complaint on Eliminatis
and found the build was not at fault. Measured:

| | Serenite | Eliminatis |
|---|---|---|
| `admin-ajax.php?action=heartbeat` (WP core only - no page cache, no theme templates, no Elementor) | 0.24 / 0.24 / 0.25s | 0.89 / 0.90 / 0.81s |
| Cold page render | 0.17-0.28s | 1.43-2.27s |
| **Warm cache HIT** | **0.076-0.085s** | **0.089-0.176s** |
| Homepage weight | 136 Elementor elements, 432KB | 82 elements, 168KB |

The heartbeat row is the decisive one: identical trivial work, nothing cached
anywhere in the path, consistently ~3.5x slower. That is raw PHP execution speed,
i.e. the hosting tier - Eliminatis sits on WPMU's **Quantum** plan. Eliminatis is
the *leaner* site and matches Serenite exactly once warm.

So the entire user-visible gap is the cost of hitting a **cold** page. Eliminatis'
cache lifetime is locked at 1 hour by the hosting plan (raising it returns
*"update-static-cache action is not allowed in Quantum plan"*) and only the
homepage is preloaded. Every other page therefore goes cold hourly and whoever
arrives next eats 2-5s. On a low-traffic site that is frequently a paid ad click -
the visitor we can least afford to make wait, and one whose landing-page
experience feeds Ad Rank.

Warming the sitemap puts essentially every real visitor on the ~0.09s path and
closes the gap **without upgrading hosting**. First real run found **23 of 26
pages cold**, several over 5 seconds.

## Usage

```bash
python3 tools/cache-warmer/warm.py              # all enabled sites
python3 tools/cache-warmer/warm.py --verbose    # print every URL
python3 tools/cache-warmer/warm.py --site eliminatis
```

Standard library only - no install step, which is why CI needs no dependency cache.

## Adding a client

Append to `sites.json`. Nothing else changes:

```json
{ "name": "someclient", "sitemap": "https://example.com/sitemap_index.xml",
  "enabled": true, "reason": "why this site needs warming" }
```

Only ever put **public URLs** in this file. No credentials, no admin paths.

## Things worth knowing

- **It sends a browser User-Agent and matches `Accept-Language` to each URL's own
  language.** These sites redirect by browser language, so requesting a `/es/` page
  with an English header bounces to the English twin - you would warm one page
  twice and leave its translation cold.
- **A `MISS` in the output is the warmer doing its job**, not a failure: it means
  that page *was* cold and a real visitor would have paid for it. `HIT` means it was
  still warm. Both are success; only non-200s are errors.
- **It exits non-zero if a site is unreachable or its sitemap moved**, so the run
  goes red rather than failing silently.
- **Don't measure cache behaviour while saving plugin settings.** Every settings
  save flushes the whole page cache. An earlier diagnosis of "cache evicts after
  ~3.5 minutes" was an artefact of exactly that and was wrong - a clean probe gave
  13 consecutive HITs over 6.5 minutes.
- **Cache-busting query strings (`?cb=123`) force a bypass** -
  `x-cache-bypass-reason: Arguments found` - so any timing taken with a random
  query param measures the cold path, not what visitors get. Real ad parameters
  (`gclid`, `fbclid`, `utm_*`) *are* correctly ignored for the cache key.
- **Logged-in WordPress sessions always get `x-cache: BYPASS`.** Test site speed in
  a private window or you are measuring a path no visitor takes.

## Maintenance

GitHub disables scheduled workflows after **60 days without repo activity**. This
repo is committed to regularly, so it is unlikely - but if the warmer goes quiet,
check that first in the Actions tab and re-enable.
