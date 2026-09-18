# client-launch — learnings (append-only, newest last; read ALL of it before a run)

## 2026-09-15 — eliminatis (the run this skill was distilled from, done by hand)
- The Elementor `<main>` wrapper script silently moved the HEADER to the bottom of every page for four weeks
  because a later script container was inserted ahead of it. A launch pass must measure header position
  (`getBoundingClientRect().top` ≈ 0) on at least one page per language — not assume it.
- WordPress does NOT old-slug-redirect hierarchical pages. Any slug/parent change needs an explicit 301
  (Rank Math redirections) or the URLs the client already saw will 404.
- Rank Math refuses to boot (no REST namespace, no head output) until its registration screen is dismissed
  in wp-admin. `rank_math_registration_skip` is set only by a nonce-protected admin form. Human gate; exit 2.
- Rank Math settings REST: `updateSettings` merges (send only changed keys); `updateMeta` needs
  `objectType: "post"`; `saveModule` for modules; redirections via `updateSettings type=redirections`.
- Fluent Forms REST inserts a duplicate settings row when `meta_id` is omitted and reads the FIRST row —
  the default confirmation kept winning until rows were collapsed. Always pass `meta_id` to update,
  `DELETE …?meta_id=` to remove. The blank template seeds a disabled notification row.
- Fluent Forms `phone` element is Pro-only; `input_text` with `type: tel` is the free equivalent.
- WPMU DEV's domain tool rewrites the DB on cutover (0 old-host refs left) but NOT the MCP registration
  or the build sources — re-register the server and sed the scripts.
- WPMU DEV hosting relays mail from `noreply@yourwpsite.email`; test messages reached the Gmail inbox
  (not spam) with no SMTP plugin. Still: confirm arrival in the inbox, every client.
- A same-page form confirmation gives GA4 nothing to count. Redirect to a noindex thank-you page that
  pushes `generate_lead` (dataLayer + gtag guard). Spec'd as the studio default here.
- Chrome-extension `resize_window` resizes the user's real window; measure mobile with a same-origin
  iframe of the target width instead (`__sweep` pattern), and keep each JS call under ~40s.
- The auto-mode classifier blocks editing `~/.claude/settings.json` and reading Keychain until the user
  adds `Bash(security find-generic-password -s wp-*:*)` themselves (python one-liner; jq is not installed).
- Per-page `og:image:alt` falls back to the page title unless the attachment has alt text — set it.
- `og:locale` is site-wide in Rank Math; Spanish pages say en_US until Polylang exists.

## 2026-09-16 — eliminatis (first scripted run, v0.1, against the already-launched site)
- All phases 01–05 reproduced the hand-built state with zero drift: 16 heads verified, both forms pass the
  full accept/reject matrix, test entries deleted. The scripts are the product now.
- Phase order: 05 (thank-you) must run before 04 (forms) on a fresh client, because 04 needs
  `thank_you_url`. Documented in SKILL.md; consider making 04 call 05 automatically.
- Rank Math `updateSettings type=redirections` is idempotent: `DB::update_iff` matches existing rows by
  serialized sources, so re-runs update rather than duplicate. No dedupe needed in 03.
- 06 correctly exits 2 when ADC lacks `webmasters`/`siteverification`/`analytics.edit`. Re-auth touches the
  SAME ADC the Serenite Ads MCP servers use: add the scopes on the SereniteIntelligence consent screen
  (Data Access), keep it "In production", re-auth FIRST, then /mcp reconnect the Ads servers.
- Ads draft (07, not written): input is the client's existing research folder + spec §6.5 keyword map —
  never re-research (Mike, 2026-09-16).
- 03's per-page verify compares `<title>` after unescaping `&amp;` — Rank Math entity-encodes titles; the
  first hand-run flagged two false mismatches for exactly this.
- 06: GSC sitemap PUT returns 403 "insufficient permission" for ~20s after META verification succeeds
  (ownership propagation). Script now retries 6×10s and reports honestly instead of printing "submitted"
  over an error line. Verified: permissionLevel=siteOwner, sitemap pending.
- 06 Google Auth prerequisites, now automated in the skill: enable `searchconsole.googleapis.com`,
  `siteverification.googleapis.com`, `analyticsadmin.googleapis.com` with `gcloud services enable`
  (NOT `webmasters.googleapis.com` — that service id does not exist); add the three scopes on the
  consent screen via "Manually add scopes" (Chrome extension can do it), Update, then SAVE the Data
  Access page; ADC re-auth: `--no-launch-browser` is rejected with `--client-id-file`, so run the normal
  flow with `BROWSER=/usr/bin/true`, grep the consent URL from stdout, open it in the extension's own tab
  (redirect to localhost:8085 works from any tab). Human steps that remain: passkey/2FA prompts, the
  consent "Allow", the GA4 ToS click.
- 2026-09-16 (Mike): a launch is not complete without the client's **Google Ads account**. GSC + GA4 were
  created and Ads was missed. Phase 07 now exists: 07a account under the MCC (live write → human runs it),
  07b prose draft → Google Doc for CLIENT APPROVAL before anything is built, 07c build (paused) only after
  approval + payment method. Never build campaigns from a draft the client has not seen.
- The auto-mode classifier blocks Google Ads account creation from the Bash tool even with confirm-style
  safeguards; read-only GAQL probes pass. Wrap live Ads writes in a script Mike runs with `!`.
- Drive: the client's shared folder is owned by the client — publish drafts into Mike's own Drive and let
  him share; `create_file` with `text/markdown` converts cleanly (bullets, headings, bold).
- 2026-09-16: `CustomerService.CreateCustomerClient` fails with `DEVELOPER_TOKEN_NOT_APPROVED` — the studio
  token is **Explorer** access. Reads and writes on EXISTING accounts (Serenite campaigns, assets) work at
  Explorer; creating accounts needs **Basic**. 07a now detects it, exits 2, and prints: create the account in
  the MCC UI (1 min) + apply for Basic access in the API Center (once). Re-running 07a finds the account by
  name and records the id. The agent never creates accounts through the UI itself (prohibited action).
- GoogleAdsClient.load_from_dict needs client_id/secret/refresh_token; the studio keeps only ADC, so every
  Ads script must go through `gads_write.client.get_client()` (ADC + dev token from env) — 07a fixed.

## 2026-09-17 — eliminatis, the client-answers round (the "A. learn" the skill was missing)
- A launch produces a QUESTIONS DOC; the answers come back as prose. The cheapest way to apply them is a
  keyed edit script (`answers_apply.py` pattern): every pending panel carries an `elm-pending-*` css id, so
  an answer maps to an id → text swap + id rename, and removals are id deletes. Keep the pending-id
  convention in every build; it is what makes the answers round mechanical.
- "Tiles are not clickable" was a symptom: there were no pages behind them. Before wiring links, check the
  target exists. Five service pages × 2 languages were written by five Sonnet agents in parallel against a
  shared brief + the live reference page dumped to JSON (`svc/BRIEF.md`), then assembled by cloning the
  template page and swapping text by css id (`svc_build.py`). ~12 minutes wall clock, zero copy conflicts.
- Whole-card click: never wrap a container in <a>; stretch the single title link's ::after over the card.
- A client saying "the licence is for the LLC" does not make an individual-format certification number a
  business licence. Publish the fact you can verify (holder + number + "certified applicator"), keep the
  business-licence question open, keep "licensed" out of ads.
- Client-facing copy must never contain agency-internal notes ("to be confirmed before this page goes live
  on the client's own domain") — sweep for them before cutover. Pattern list in the sweep: pending, to be
  confirmed, verification in progress, not written yet, placeholder + their Spanish equivalents.
- When answers flip a claim (free inspections), the change fans out to: buttons, fork links, meta
  descriptions, JSON-LD, form copy, ads headlines/callouts/sitelinks, AND the negative-keyword list ("free"
  was a negative). Grep the whole launch.json, not just the pages.
- Fluent Forms test cleanup only deletes marker-tagged entries — a real lead arrived mid-run and survived.
  Report real entries to Mike; never bulk-delete.
- Drive docs cannot be edited: publish v2, trash v1, tell Mike which link is current.
- Fluent Forms {all_data} omits EMPTY fields in the notification email, so attribution looks 'missing' on organic leads. The lead email must list the attribution fields explicitly (04 now appends the block). Blank gclid/utm on a lead = organic/direct, not a failure.
- Mike annotates the DRAFT DOC itself. Before regenerating a draft, READ the previous version (Drive read_file_content works on trashed files) and fold the notes into launch.json; never regenerate from the config alone. The generator must read every client decision from config (budget note, schedule, same_day, management_note) so notes are not lost between versions.
- GBP→Ads linking in the Data manager is ACCOUNT-level: if the studio Google account holds several clients' listings, the dialog offers only 'account (N locations)' and would share every client's listing with one client's Ads account. Never submit that. Fix = a Business Profile *business group* per client (or client-owned listing), which shows up as its own selectable account. Add to phase 07 human steps.
- 07c: Google Ads policy PROHIBITS phone numbers in headlines/descriptions (PHONE_NUMBER_IN_AD_TEXT →
  RSA disapproved at creation). Phone goes in the call asset only. The build script now strips/validates
  and reconciles RSAs against config (removes a stale RSA, creates the new one) so re-runs converge.
- 07c: python lib takes validate_only inside a Mutate*Request object, not as a kwarg. Campaign validate_only
  with a temp budget id always fails "not found" — validate budget + conversion action separately.
- 07c: `campaign_asset` GAQL needs campaign.resource_name in SELECT when filtering by it.
- Explorer access also blocks CustomerUserAccessInvitationService — add client users in the Ads UI.
- Client may already have been added as Admin by the account creator — check Access & security before inviting.
- Captcha (2026-09-17): Fluent Forms reCAPTCHA v3 = paste keys in Global Settings → Security (human; the secret is
  a credential), then ONE global switch `misc.autoload_captcha=true, captcha_type=recaptcha` applies it to every
  form — no per-form field. Proof is two-sided: scripted submit → 422 "reCaptcha verification failed"; real
  browser submit → thank-you page. The pre-captcha scripted "accept" proof no longer applies once captcha is on.
  `_fluentform_reCaptcha_details` is false until the keys VALIDATE ("Your reCAPTCHA is valid") — a paste without
  validation leaves it empty.

## 2026-09-18 — Google Ads API Basic access (studio-level, one-time)
- Access levels moved out of the Ads UI API Center into Cloud Console: `console.cloud.google.com/google/ads-apis/overview?project=<id>`.
- Basic requires **Brand Verification** on the OAuth app (Google Auth Platform → Branding). The verifier fetches the *privacy policy URL* in the Branding form and rejects "does not have sufficient content" if it's the homepage or a generic template with no mention of the app / Google user data.
- Fix that worked first time: point the form at the real policy page, add a "Google account data and connected services" section (what APIs are read, purpose, no sale/no AI training/no cross-client sharing, retention, Limited Use statement, revoke link), click View issues → "I have fixed the issues" → Proceed. Verification returned instantly; then **Publish branding** (7-day expiry if you don't), then Apply for access on the Ads API page.
- Stray "Setup in progress" Ads accounts can't be cancelled without finishing signup, which attaches a payments profile + accepts Ads terms. Leave them; they can't spend.
