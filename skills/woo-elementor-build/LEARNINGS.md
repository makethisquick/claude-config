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
