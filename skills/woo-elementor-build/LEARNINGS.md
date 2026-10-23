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
