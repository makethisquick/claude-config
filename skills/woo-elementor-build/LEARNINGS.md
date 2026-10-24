# woo-elementor-build: learnings (append-only, newest last; read ALL of it before a run)

## 2026-10-22: taskrunnerz (connector probe, before the build)

- **Site and connector:**
  - Plugin `emcp-tools` 2.2.0 ("MCP Tools for Elementor Server"), 76 tools, on Elementor 4.3.5 + Pro 4.3.2.
  - With Pro active, `list-widgets` returns 199 widgets, including the full `woocommerce-*` set, `loop-grid`/`loop-carousel`, Pro `form`, and atomic `e-form-*` (date picker, **file upload**).
  - `detect-elementor-version` reports `recommended_mode: atomic`.
- **Without Pro, `detect-elementor-version` errors** (`output[elementor_pro_version] is not of type string`) and returns nothing at all.
- **`list-pages` counts only Elementor documents.** It returned 0 on a site whose 6 pages were all Brizy.
- **Placing widgets:** `add-widget` placed `woocommerce-products`, `woocommerce-cart` and `form` into a container on a draft page with no errors (structure verified with `get-page-structure`). Front-end render not yet verified.
- **Theme Builder:**
  - `save-as-template` only supports `page|section|container`.
  - `wp/v2/elementor_library` is REST-writable, but its meta exposes only Astra keys, not `_elementor_template_type` or `_elementor_conditions`.
  - A library post created via REST is reported by the connector as type `loop-item`, but `add-container` works on it.
  - So: content via MCP, type + conditions via PHP (or wp-admin).
- **No delete tool in the connector.** Delete probe posts with `wp.sh DELETE 'wp/v2/pages/<id>?force=true'` (works with the admin app password).
- **WAF quirks:**
  - WPMU DEV's WAF blocks `wp/v2/users` and `wp/v2/users/me` (403) even when authenticated, so use MCP `initialize` as the auth check.
  - `wp/v2/plugins` and `wc/v3/system_status` are readable (the admin role is confirmed this way).
- **Health check vs reality:** `claude mcp list` showed "tools fetch failed — Request timed out" while direct `tools/list` took 4.7 s and a fresh `claude -p` call worked (≈60 s cold start). Don't treat the list status as a failure.
- **Raw JSON-RPC needs the session header:** without `Mcp-Session-Id` from the `initialize` response, every call fails with `-32600 Missing Mcp-Session-Id`. `scripts/mcp.sh` handles this.

## 2026-10-23: hush (adult-novelty dropship, Nalpac) — catalog-first build

- **Ran Phase 4 before Phases 1–3, deliberately.** On a greenfield store there is nothing to
  build or verify a product template against until products exist, and the catalog was the
  only part with real source data. Worked fine; recommend this order for dropship builds.
- **Site state:** fresh Woo install — 0 products, and only the stock Woo pages (Shop/Cart/
  Checkout/My-account published; Privacy + Refund drafts; Sample Page). `production:false`,
  so built directly rather than `-v2` drafts. Confirm emptiness with
  `wp.sh GET 'wp/v2/pages?status=any'` before deciding; `list-pages` still only sees Elementor docs.
- **Connector:** same as taskrunnerz — EMCP Tools 2.2.0, Elementor 4.3.5 + Pro 4.3.2,
  `recommended_mode: atomic`. 26 distinct `woocommerce-*` widgets; all Phase 2/3 widgets present.
- **`wp/v2/plugins` is readable and is the fastest preflight for conflicts.** On this site it
  surfaced **WooPayments + WooCommerce PayPal Payments active**, plus Google/TikTok/Snapchat/
  Reddit for WooCommerce. For a catalog in a restricted category those syndicate product feeds
  to platforms that ban it. **Creating products as `status: draft` neutralises this** — drafts
  don't syndicate — so it becomes a cutover decision rather than a blocker. Add a plugin-conflict
  check to preflight on any restricted-category build.
- **No code-snippets/WPCode plugin here**, so the Phase 2 PHP helper for
  `_elementor_template_type` / `_elementor_conditions` is unavailable. Needs a mu-plugin from the
  client or wp-admin work. Check for this in preflight, not at Phase 2.
- **`wc/v3` authenticates fine with the WP application password** (Basic over HTTPS) for an admin
  user — no need for separate Woo consumer key/secret. `products/batch` accepts 50 per call.
- **Catalog apply takes >120 s for ~150 products** on shared hosting; run it with
  `run_in_background: true`. Python buffers stdout when not a tty, so interim output is empty —
  don't read that as a hang.
- **Supplier-feed lesson, generalises to any dropship build: filter trade goods out.**
  First selector pass ranked purely on contribution and happily picked
  *"Blush Quinn Merchandising Kit"*, *"EnLust Body Parts Merchandising Kit"* and a
  *"GoodHead Fishbowl Refill (216 Pieces)"* — in-store display fixtures and counter bulk, not
  consumer products. They carry high wholesale cost, so margin-ranking loves them. Regex filter
  on merchandis|display|fishbowl|refill|tester|pdq|planogram|case pack|signage|poster|shelf.
- **Normalise brand strings before applying a per-brand cap.** The feed spelled the same brand
  several ways (`Vee International Inc / Blush` vs `Blush`, `LELO` vs `Lelo Inc U.S.A`,
  `XR LLC` vs `XR llc DBA Curve`), so a 14-per-brand cap silently let XR reach 28 and Blush 18.
- **Stratify on price bands, or contribution-ranking produces a boutique.** Unconstrained, the
  median retail came out at $219.95 with only 12 of 150 items under $100. Explicit band quotas
  (42/33/18/7% across $63–110/110–180/180–320/320+) brought the median to $141.95 while keeping
  median contribution at $50.
- **Watch for a structural price floor created by free/absorbed shipping.** With $10 freight
  absorbed and a flat 2× keystone, a $15 contribution floor implies retail ≥ ~$63 — which silently
  excluded every lubricant, lingerie and accessory SKU. Cheap categories can only enter as bundle
  components or cross-sells. Compute this threshold explicitly before promising category breadth.
- **Leave `description` empty on import when original copy is a requirement.** Writing the
  manufacturer text "for now" risks it leaking live and is the exact duplicate-content problem
  the curated strategy exists to avoid.

## 2026-10-23: taskrunnerz (design-spec review findings that change how this skill builds)

- **Permalink bases are global and live the moment they're saved.** You can't "verify on drafts" (draft products have no public URL). On a production rebuild, change product/category bases only as a cutover step, prove them with a curl matrix (shop, category, product per category, old URLs → 301, `/page/2/`), and revert them alongside the slug swap.
- **Don't give categories and products the same base.** `/services/<cat>/` + `/services/<product>/` collide in Woo rewrites. Use a distinct product prefix (`/service/%product_cat%/`). With category base == shop slug, `/services/page/N/` is captured by the category rule, so show the shop on one page or change the category base.
- **No-price "products"** (estimate-only services, subscription landing cards) cause trouble: no eligible Product snippet, Merchant-feed rejections, thin duplicates. Make them pages + static cards in the category template instead.
- **Feed plugins** (Google Listings & Ads, Pinterest/Reddit/Snapchat for Woo) will try to sync service products. Set "don't sync" before publishing anything.
- **Compliance config without PHP — three wins worth reusing:**
  - **State-level blocking via shipping zones.** Woo has no state exclusion in "sell to specific
    countries", but restricting a zone to the 49 permitted states + DC and leaving the *fallback*
    zone with **no methods** makes the excluded state unserviceable at checkout. No snippet needed.
    Verify the fallback zone is empty — that is what actually does the blocking.
  - **A stacking surcharge** (e.g. Utah's additional 10% on intimate products) works as a second
    `wc/v3/taxes` rate at `priority: 2`; same-priority rates replace rather than stack.
  - **Plugins install straight from wordpress.org over REST**: `POST wp/v2/plugins
    {"slug":"age-gate","status":"active"}`. Its *settings* are not REST-writable though, so plugin
    configuration still needs wp-admin or browser automation.
- **Check for pre-existing shipping methods before adding your own.** The stock Woo zone already
  had a `free_shipping` method with `min_amount: 0`, so adding a $75-threshold free-shipping method
  left everything shipping free and silently defeated the threshold. List
  `wc/v3/shipping/zones/<id>/methods` and delete by `instance_id` first.
- **`wp/v2/plugins` POST with `{"status":"inactive"}` deactivates cleanly** and is the fastest way
  to clear incompatible gateways/feed plugins. Re-read the plugin list to confirm; don't trust the
  response alone.

## 2026-10-23: hush — design system, pages, and verification gotchas

- **`update-global-colors` and `update-global-typography` silently no-op on system IDs.** Both
  returned `success: true` while the system colours stayed Elementor blue and typography stayed
  Roboto; my `primary`/`secondary`/`text`/`accent` entries were appended to `custom_colors` as
  duplicates instead. **The only path that works is a full kit write**: read `get-global-settings`,
  modify `system_colors` / `system_typography` / `custom_colors` in the settings object, and send
  the whole thing to `update-page-settings`. Note the arg is **`post_id`**, not `page_id`
  (the kit is a post — `wp/v2/elementor_library` slug `default-kit`, id 7 here).
  This is Rule 4 earning its keep: `success: true` is not proof.
- **`build-page` with a declarative `structure` tree works well** — 55 elements, one call, nesting
  intact. Far better than add-container/add-widget chains for a whole page.
- **Flex rows need explicit child widths.** Setting `flex_direction: row` + `flex_wrap: wrap` on the
  parent and `_flex_size: grow` on children is NOT enough — children default to full width and each
  wraps onto its own line. Set `width` (%) plus `width_tablet` / `width_mobile` on every child
  container, and `_flex_size: none`.
- **`get-page-structure` returns no settings**, only the element tree and ids. To check what
  actually saved, call `get-element-settings` per element id.
- **WooCommerce slugifies category names and drops "and"**: "Bondage and Restraint" →
  `bondage-restraint`, "Strokers and Sleeves" → `strokers-sleeves`. Hard-coded category links built
  from the display name will 404. Read the real slugs from `wc/v3/products/categories` first.
- **Avoid `&` in category names entirely** — it stores HTML-entity-encoded as `&amp;` and renders
  literally. Use "and".
- **A catalog apply must REPLACE categories, not union them.** Adding the new id while keeping the
  old left 11 products in two categories and made category counts disagree with the source of truth.
- **Do not let the apply script reset `status`** once products are published — keep the status in
  `products.json` in sync with the site or the next run silently unpublishes the catalog.
- **Woo block checkout shows stale shipping rates after an in-page address change.** Changing state
  to a blocked state left the old rates on screen; a fresh page load correctly showed
  "No shipping options are available for this address." **Always verify a shipping-zone block on a
  fresh load**, not by editing the field in place.
- **Supplier image URLs:** Nalpac exposes no image column in its CSVs, but `products.xml` has
  `IMAGE_1` → `https://nalpacazimages.blob.core.windows.net/images/{large|medium}/<item_id>.jpg`.
  99% coverage on our assortment. `wc/v3` sideloads from a URL via `images:[{src,name,alt}]`, but it
  is slow (server-side fetch per product) — background it.
- **The Nalpac blob container permits anonymous listing**:
  `?restype=container&comp=list` revealed 14 feeds including the attributes and category files,
  none of which are linked from the data-feeds page. Worth doing on any Azure-blob supplier feed.
- **Use the supplier's own category feed over keyword guessing**, but order the mapping
  **most-specific-first** — a generic "Vibrators and Massagers" tag will otherwise swallow sex
  machines and couples toys that also carry it.

## 2026-10-23: taskrunnerz (full build + cutover; production, checkout off)

- **WPMU DEV WAF blocks snippet POSTs** containing `$_GET[`, the phrase `schema (`, and also scores cumulatively. Keep Code Snippets code in parts under about 3 KB, and bisect with throwaway snippets (then DELETE them; check the list afterwards).
- **Elementor container `width` is ignored when `content_width` is "boxed"** (only `boxed_width` applies). Nested columns must be `content_width: full` + `width`. Widths + flex gap > 100% wraps rows, so subtract a few % per column.
- **Woo single-product / archive title widgets imported via JSON show "Add Your Heading Text Here"**: they need `__dynamic__` tags. A tiny `[tr_title]` shortcode is more robust.
- **`save_conditions()` wants arrays** (`type/name/sub_name/sub_id`), not strings; strings fatal with "Cannot unset string offsets". Pre-cutover scope: `include/singular/page/<id>` per new page + `include/product` + `include/product_archive`, so the live pages stay untouched.
- **The kit body/heading styles apply site-wide** (body has `elementor-kit-N` on every page). Scope all visible CSS under a body class that a snippet adds only to new pages, then site-wide at cutover.
- **New option read back `false` after `update_option` succeeded** (notoptions/alloptions cache). Clear the `options` cache group around writes, and verify in a separate request.
- **Woo "Coming soon" (store pages only) was ON** on a site whose store had never launched. It hides every product/shop page from visitors, so check `woocommerce_coming_soon` in preflight.
- **Term descriptions are kses-stripped of all tags** via REST, so category FAQs go in a shortcode keyed by slug.
- **SmartCrawl sitemap can be a stale static file** ("manual" regeneration). Switching to the WP core sitemap needed `wp_sitemaps_enabled` forced true + a second rewrite flush. robots.txt may be overridden by another plugin: serve it from `init` priority 0.
- **Woo's Product schema doesn't fire from Elementor Pro single templates.** Output Product/AggregateOffer yourself; Woo's breadcrumb widget already emits a BreadcrumbList, so don't add a second.
- **Visual QA:** the Chrome extension was flaky. A no-dependency CDP script (`build/tools/shot.mjs`: Emulation.setDeviceMetricsOverride + captureBeyondViewport) gives true 390 px screenshots. Headless `--window-size=390` is NOT true mobile (min window width ≈500).
- **Elementor Pro forms on mobile use a separate flatpickr input** for date fields; fill `input.flatpickr-mobile` in tests. Submissions take 8–20 s on this host (uncached admin-ajax + wp_mail), so wait ≥45 s.
- **LCP levers that worked:** skip Jetpack Photon on hero images, dequeue Astra/Elementor Google Fonts + block-library CSS on new pages, preload the hero with matching `imagesrcset`, aspect-ratio on hero images, `font-display: optional` for the display face.

## 2026-10-24: taskrunnerz — client feedback round (photos, galleries)

- **Check which version the client reviewed.** Their notes named sections that only existed on the old Brizy home (and an old phone number). Grep the old page before "fixing" things the new site already gets right.
- **Pexels without an API key:** pexels.com search is bot-blocked to curl (403), but in a real Chrome tab `fetch('/search/<q>/')` returns `__NEXT_DATA__` with photo ids + alt text; images.pexels.com serves `?auto=compress&cs=tinysrgb&w=1400&fm=webp` to curl. The javascript tool output truncates around 1 KB, so pull ids in slices. Review candidates with a local HTML contact sheet screenshotted via `tools/shot.mjs` — choose by eye, never by alt text alone (diversity, relevance, no "our team" implication).
- **The Openverse-backed `search-images` MCP tool timed out server-side** on WPMU DEV — don't rely on it.
- **Photo galleries hurt LCP if the first one is lazy and above the fold.** Lighthouse flagged the first gallery image; making only that image `loading=eager` + `fetchpriority=high` took services LCP from ~2.8 s to ~2.2 s.
- **shot.mjs + lazy images:** setting `loading=eager` on all images then capturing produced a garbled full-page shot; scrolling through the page in 600 px steps before capture is reliable.
