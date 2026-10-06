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
- **The Ads API cannot close/cancel a customer account (proven 2026-09-18).** `mutate_customer` with `status=CANCELED` returns success and changes nothing — `Customer.status` is read-only and silently dropped from the update mask. `validate_only` passes for the same reason, so it is NOT evidence. Cancellation is UI-only (Admin → Account status), and for LSA-bearing accounts it is the LSA UI. Don't create test accounts expecting to delete them.
- **"Setup in progress" in the Ads account picker is only the Ads-wizard state — the account can still carry a live Local Services campaign.** 980-034-2988 looked like an empty stray and held a SERVING/ELIGIBLE weight-loss LSA campaign with billing PENDING. Before treating any account as disposable: GAQL `SELECT campaign.id, campaign.advertising_channel_type FROM campaign` with login-customer-id = the account itself, and never finish its signup wizard (attaching a payments profile would let a dormant LSA campaign start spending).
- **`billing_setup.status = APPROVED` + campaigns ELIGIBLE does NOT mean the account serves (Eliminatis, 2026-09-18→20).** The account sat 3 days at 0 impressions / IS 0.0 / no keyword bid estimates while every API status was green. Cause: Google Payments' post-signup *"Verify your payment information to complete your Google Ads signup"* banner, visible only in the UI, actionable only by the payments-profile owner (the client). Rule: 24h after enabling, if impressions == 0 on every campaign, stop trusting API statuses and read the account's Campaigns page for a top banner; the tell-tale is `search_impression_share == 0.0` (not 0.0999) and `position_estimates` empty on all keywords. Then email the client — the T+7 first-report clock restarts from verification, not from enable.
- **"Verify your payment information to complete your Google Ads signup" = Google Payments identity/business verification of the client's payments profile (module `identityverificationview`), not a card problem.** Only a *payments user* on that profile can complete it — an Ads admin cannot, and a new client profile typically has exactly one user (the client). Tell the client up front, in the payment-method email, that Google may ask them to verify identity/business (ID, EIN/formation doc) and that ads do not serve until it passes (1–3 business days after upload). Also: never read a Google Ads banner state within seconds of navigation — wait for a full render or re-check before reporting "cleared".
- **Week-1 negatives are not optional, and the launch list is always too polite.** Eliminatis launched with `diy`/`do it yourself`/`how to`/`how do i` and still spent 71% of week-1 click budget on DIY intent, because real searches say *"get rid of"*, *"best way"*, *"what kills"*, *"killer"*, *"homemade"*, *"at home"* — none of which the launch list caught. Seed every new account with those phrasings at campaign level. **And a non-English campaign needs negatives in its own language** — the Spanish campaign shipped with zero Spanish negatives and burned on `veneno`, `remedio casero`, `como eliminar`, plus insecticide brand names (`sniper`, `plop`). Add the client's not-offered pests too (`ardillas`/`squirrel`). Also add out-of-area city negatives when a neighbouring metro outranks the service area (`nyc`).
- **Before blaming conversion tracking for zero leads, price the traffic.** Zero from 75 clicks looks alarming (0.4% likely at a 7% CVR) until you subtract DIY terms — ~18 commercial clicks, where zero is ~27% likely and unremarkable. Verify the tag (curl the thank-you page for the AW send_to) *and* bucket the search terms before drawing a conclusion; reporting "tracking is broken" when it is a traffic problem sends the next session down the wrong path.
- **Any standalone ops script must source `GOOGLE_ADS_DEVELOPER_TOKEN` from the Keychain itself** (`security find-generic-password -a claude -s google-ads-dev-token -w`) — `get_client()` raises without it and only the MCP launcher sets it. A script handed to the user to run with `!` will fail on the first try otherwise.
- **A service site's phone number IS the conversion — track taps at launch, not in week 2.** Eliminatis launched with thank-you-page conversion tracking only, while the site's primary CTA was 7 `tel:` links; for a week, any ad click that turned into a phone call was invisible to Ads AND GA4, and "0 leads" read as failure when it was partly unmeasured. Ship phone-tap tracking with every client site: create a WEBPAGE / PHONE_CALL_LEAD / ONE_PER_CLICK conversion action, then inject a delegated `document.addEventListener('click', … closest('a[href^="tel:"]'))` handler into the site-wide enhance widget (`templates/telclick.example.py`). A delegated capture listener covers header, hero, sticky mobile bar and footer without touching their markup, and dedupes per page view. Verify by firing a synthetic tap and confirming `googleadservices.com/pagead/conversion/<id>/?…&label=<label>` returns 200 **carrying `gclaw=<gclid>`** — that parameter is what proves the call attributes back to the ad click.
- **Ad-side call taps: read `segments.click_type = CALLS` and `metrics.phone_calls`, not the `campaign_asset` CALL row.** Asset-level "clicks" count clicks on the *ad* while that asset was showing, so a call asset can report clicks with zero actual taps. Also check `customer.call_reporting_setting.call_reporting_enabled` before trusting a zero — if reporting is off, zero means nothing.
- **Google Ads does NOT normalise Spanish accents in negative keywords (proven on Eliminatis 2026-10-02).** The campaign negative `que es bueno para` did not block the search `qué es bueno para ahuyentar a los ratones` — it served and took a paid click days after the negative went live. **Add both the accented and unaccented form of every Spanish negative** (`cómo eliminar` + `como eliminar`, `qué sirve para` + `que sirve para`). Do not assume the documented accent-folding behaviour applies to negatives.
- **The three gaps a first negatives pass always leaves:** (1) the bare verb — `kill` slipped past `what kills`; (2) the other language's twin of a term you only blocked once — English `remedies` was missed because the Spanish `remedio` was added; (3) singular vs plural — `product` slipped past `products`. Generate every negative in both numbers and both site languages, and block the bare verb, not just the question form.
- **After a successful waste purge the budget gate closes for the OPPOSITE reason — say so explicitly.** Eliminatis week 1: budget-lost 51% > rank-lost 40% (money was the constraint, but 71% waste forbade a raise). Week 2 after negatives: budget-lost 8.5%, rank-lost 81.8%, spend $13.74/day against a $16.50 budget. The account cannot spend what it has, so a raise is pointless; the lever moves to ad rank (quality score, ad strength, landing-page relevance). Report which of the three conditions failed and *why it changed*, or the client hears "no" twice and assumes nothing happened.
- **To tell a real conversion from your own test: check `segments.device` and whether it attributes to an ad group.** A synthetic tap fired with a fake gclid cannot attribute to a campaign or ad group, so an ad-group-attributed conversion is real traffic. Cross-check the device against the one you tested on. Never report a lead to a client without this check if you fired a test the same day.
- **A `tel:` tap is intent, not a confirmed conversation.** It opens the dialer; it cannot prove the call connected or was answered. Report it to the client as "someone tapped your number to call" and ask them to confirm against their own phone log — never as a booked job.
- **Negatives are a setup-time asset, not a weekly chore — Eliminatis paid ~$100 to learn a list that was always predictable.** Week 1 ran at 71% wasted spend on a 35-term hand-written list; three reactive passes later the account carries 102 EN / 79 ES. The shared library (`templates/negatives/`) plus `scripts/07d_seed_negatives.py` now applies ~171 EN / ~109 ES at phase 7d, BEFORE a campaign is enabled. Run it between 07c (build) and go-live, every client, every time. The generator encodes the three facts that make hand-written lists fail: no close-variant matching (inflections emitted explicitly), no Spanish accent folding (both twins emitted), and singular≠plural.
- **Vet a shared negative library for false positives against the CLIENT's actual buyers.** The first draft of the studio base list would have blocked `school`, `class`, `rent`, `rental` and `for sale` — but schools and institutions are real buyers (Eliminatis sells government/institutional work) and landlords with rental property are prime customers. Wildlife terms are client-dependent too: many pest firms do sell squirrel and raccoon work. Anything that depends on what the client sells belongs in `launch.json`, never in the shared library.
- **Do the lead-goal arithmetic BEFORE launch, and let it decide where the work goes.** Eliminatis wanted 10 leads per fortnight on ~$500/mo. That is 105 clicks at a $2.21 CPC, so it requires a **9.5% click→lead rate**. The account delivered the clicks (122 per fortnight — goal-adequate from week one) and converted **0.76%**. Four rounds of negatives, two ad-group rebuilds, snippets and device modifiers all improved *traffic quality* — they lower cost per click and protect budget, but **they cannot manufacture a lead**. Every lead is created after the click. At launch, compute `required_CR = leads_goal / (budget / expected_CPC)`; if the site cannot plausibly reach it (home services typically convert 5–15%), the honest first task is the site and the offer, not the keyword list. Put the number in the client-approval doc so the target is agreed, not assumed.
- **Traffic work and conversion work fail differently, and the metrics say which you have.** Low CTR, high rank-lost, junk search terms, high CPC = a *traffic* problem, fixed with negatives/copy/structure. Adequate clicks with near-zero conversions = a *conversion* problem, fixed with page speed, offer, proof, CTA placement and call handling. Diagnose which one you have before choosing the work — spending four rounds on negatives while conversion sits at a tenth of normal is optimising the wrong end of the funnel.
- **Ship GA4 *read* access with the launch, not just write.** ADC minted with `analytics.edit` could create the property but could NOT call the Analytics Data API (`insufficient authentication scopes` — needs `analytics.readonly`). Result: fifteen days of paid traffic with no visibility into what any visitor did after the click — no bounce rate, no scroll, no path to the form. Add `analytics.readonly` to the ADC scope set in phase 00 preflight and assert a test `runReport` succeeds, or the post-click half of every report is guesswork.
- **GA4's absence of an event is evidence. Check for `scroll`, `form_start` and `form_submit` before blaming traffic.** Eliminatis: 208 ad-driven page views produced **zero `scroll` events** (GA4 fires it at 90% depth) and **zero form interactions**, with enhanced measurement confirmed ON for both. That is not a traffic-quality problem — it says visitors arrive, never reach the bottom of the page, and never touch the form. The forms had been live four days at 62–65% page depth: present, and unreachable in practice. Pull these three events at every report; an empty result localises the failure to the page in one query.
- **Put the conversion point where the traffic actually stops.** The one page that converted (`/services/rodent-control/`, 25s engaged per view, 31% engagement) differs from the worst (6.5s and 0.7s per view) by having an inline symptom-triggered CTA high in the body and an opening line answering the searcher's actual question — not by template, length or speed, which were identical (98KB, ~1,430 words, same CTA positions). Long-form service pages are fine for SEO and wrong for paid mobile traffic unless a conversion point sits above the fold.
