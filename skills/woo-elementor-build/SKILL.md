---
name: woo-elementor-build
description: "Build a WooCommerce services store's pages through a client's Elementor MCP connector: design tokens in the kit, Theme Builder header/footer/product/archive templates, shop/cart/checkout/my-account pages with Elementor Pro Woo widgets, catalog from a products.json via the Woo REST API, revert-safe -v2 drafts and a single cutover. Use when asked to build or rebuild a client's store or service pages with Elementor, 'build the store', 'build pages via MCP/emcp', or to add Woo pages to an Elementor site. Requires the site already onboarded with wp-mcp-onboard. Reads and appends LEARNINGS.md every run."
---

# woo-elementor-build: from "connector works" to "store pages built, ready to cut over"

Sits on top of `wp-mcp-onboard`, which handles credentials and connector registration. This skill doesn't touch credentials. It ends where `client-launch` begins: it gets the site built and cut over, and `client-launch` does SEO/forms/analytics hardening after that.

First run: **TaskRunnerz**, 2026-10-22. Spec: `~/projects/specs/taskrunnerz-services-store/spec.md`.

## Rules that do not bend

0. **Read `LEARNINGS.md` in full before doing anything, and append to it before you stop.**
1. **One `build.json` per client, kept at `~/projects/<Client>/build/build.json`:**
   ```json
   {"slug":"taskrunnerz","host":"taskrunnerz.com","wp_user":"makethisquick","production":true}
   ```
   - Every call goes through `scripts/mcp.sh <build.json> …` or `scripts/wp.sh <build.json> …`.
   - Never point a script at a site by editing it.
   - Before every write, say which client you're writing to (zero cross-client tolerance).
2. **Production sites are built as drafts, never in place.**
   - New pages get a `-v2` slug.
   - Theme templates get no display conditions until cutover.
   - Products stay `draft` until cutover.
   - Never edit a live page's content.
   - Revert must stay a slug swap until 14 days after cutover.
3. **Kit writes REPLACE, they don't merge.** Read `get-global-settings` first. Then write `update-page-settings` with custom_css plus every kit setting in ONE call, then `update-global-colors`, then `update-global-typography`. Never send a bare kit-settings call.
4. **Verify by observation.** A `success: true` isn't proof. Re-read with `get-page-structure`, and curl the front end with `?cb=<random>` after Elementor → Tools → Clear Files & Data.
5. **Mobile first.** Set `_mobile` / `_tablet` values explicitly on every container and typography you touch. Never rely on desktop values inheriting down. Check at 360px.
6. **Catalog is data, not clicks.** Products come from `products.json` through `wc/v3` with an idempotent apply: re-running on an unchanged file makes 0 changes. Never hand-create products through the UI or MCP.

## Phase 0: preflight (read-only)

1. Is `mcp__<slug>__*` connected, or does `scripts/mcp.sh build.json detect-elementor-version '{}'` answer? If not, run `wp-mcp-onboard` first.
2. `detect-elementor-version` must show `elementor_pro_version`. **Without Pro the tool crashes.** That means stop: Pro is needed for the Woo widgets and Theme Builder.
3. `list-widgets` must include `woocommerce-products`, `woocommerce-cart`, `woocommerce-checkout-page`, `woocommerce-my-account` and the `woocommerce-product-*` set.
4. Inventory the existing pages with `wp.sh GET 'wp/v2/pages?status=any'`. **`list-pages` only counts Elementor pages**, so it's useless on Brizy or Gutenberg sites. Record which IDs are live.
5. Read the kit with `get-global-settings`. Save a copy to `build/kit-before.json`.

## Phase 1: design system

- Tokens (colours, type scale, spacing, radius) come from the client's design spec. Use the `client-site-spec` skill if none exists.
- Write them per Rule 3. Prefix custom colour IDs (`tr-primary`, not `primary`); system IDs are not writable.
- Re-read and diff against `kit-before.json`.

## Phase 2: Theme Builder templates

Template type and display conditions **cannot be set through the connector or REST.** `save-as-template` only makes page/section/container, and REST exposes no `_elementor_template_type` or `_elementor_conditions` meta. A post created via REST defaults to `loop-item`. So:

1. Create the template post and set its type with the site's PHP helper. On TaskRunnerz that's a Code Snippets snippet / mu-plugin endpoint (see LEARNINGS). If no helper exists yet, a human creates the empty template in wp-admin → Templates → Theme Builder and gives you the ID.
2. Build its content through MCP with that `post_id`. `add-container` and `add-widget` work on library posts.
3. Conditions are applied **only at cutover**, by the same PHP helper or in wp-admin.

Templates: header, footer, single product (`woocommerce-product-images`, `-title`, `-price`, `-short-description`, `-add-to-cart`, `-content`, `-related`), product archive (`woocommerce-archive-products`, `woocommerce-archive-description`).

## Phase 3: pages (all `-v2` drafts)

- `create-page` ignores `slug` and `parent`, so fix both with `wp.sh POST wp/v2/pages/<id> '{"slug":"home-v2"}'` immediately.
- `add-flexbox` ignores `background_color` and `padding`. Use `add-container` with settings, or follow with `update-container`.
- Store pages:
  - Cart = `woocommerce-cart`.
  - Checkout = `woocommerce-checkout-page`.
  - Account = `woocommerce-my-account`.
  - Category grids = `woocommerce-products` with `query_post_type`/category settings (check `get-widget-schema` each time; schemas differ by version).
- Galleries: `image-carousel` or `loop-carousel`. Load the first image eagerly and the rest lazily.
- After each page: `get-page-structure`, then a cache-busted front-end check.

## Phase 4: catalog

`products.json` → `wc/v3/products` (+ `/variations`). The apply script:
- matches by SKU;
- creates missing products;
- updates changed fields only;
- never deletes.

Products are `status: draft` until cutover.

## Phase 5: cutover (only when the spec's launch gates are met; never on your own initiative)

1. Publish templates and set their conditions.
2. Publish products.
3. Swap slugs: old page → `<slug>-old` and draft; v2 → real slug.
4. Set the front page.
5. Add 301s.
6. Clear Files & Data, and purge the host cache.
7. Run the spec's checks.

Revert is the same steps reversed. Rehearse revert on one page before the real cutover.

## Self-improvement

Append dated entries to `LEARNINGS.md` covering: connector behaviour that differed from its schema, widget settings keys that worked, anything that needed a human, and timings. Newest last.
