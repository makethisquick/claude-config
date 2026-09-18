---
name: client-launch
description: "Post-cutover launch pass for a studio WordPress/Elementor client site: cutover hygiene, core settings, Rank Math SEO, Fluent Forms with lead attribution and thank-you conversion pages, Google Search Console + GA4 (studio-owned), then verification. Use when a client's site has just moved to its real domain, when asked to 'launch', 'set up SEO/forms/analytics for <client>', or to re-verify a launched site. Reads and appends LEARNINGS.md on every run."
---

# client-launch — from "the domain is live" to "leads are tracked"

The site is built and sitting on its real domain. This skill makes it *launched*: indexable
and titled, collecting leads that arrive by email with click attribution, converting on a
thank-you page GA4 can count, and owned in Search Console and Analytics by the studio.

It is the codified version of what was done by hand for Eliminatis on 2026-09-14/15
(`~/projects/Eliminatis/build/BUILD-LOG.md` §16–§17). Every script is idempotent — re-running
updates in place — and every phase **verifies on the live page before reporting success**.

## Rules that do not bend

0. **Preflight first.** `00_preflight.py` must PASS before any phase runs. It checks the two permission
   rules the agent needs (`security find-generic-password -s wp-*`, `ads_env.sh`), and prints the exact
   one-liner Mike runs to add a missing one — the agent cannot edit its own permissions.
1. **Zero cross-client tolerance.** Everything is scoped by ONE `launch.json`. Never edit a
   script to point at a site; never run a phase against a config you have not just read.
2. **Read `LEARNINGS.md` before the first phase and append to it after the last.** Every run
   must leave the skill better than it found it (see *Self-improvement*).
3. **Verify by observation, not by inference.** A 200 from a write is not proof. The scripts
   fetch the live page and compare; if you add a step, add its check.
4. **Humans decide plugin conflicts.** Phase 1 *detects* other SEO/form plugins and stops.
   Never deactivate a plugin the config does not name.
5. **Human gates are printed, not skipped**: Rank Math's registration screen, the GA4 terms
   click, an ADC re-auth. The script exits 2 with the exact URL/command; you relay it to Mike
   and re-run when he says done.
6. **Test data is tagged and deleted.** Test submissions use the `test.marker` prefix and are
   removed in the same phase. Lead notifications go only to `leads.recipients` — the studio
   address by default; the client's address is added only when Mike says so.

## Inputs

```
~/projects/<Client>/launch.json        ← the only input; see templates/launch.example.json
~/.claude/skills/client-launch/.venv   ← python3 -m venv .venv && .venv/bin/pip install requests google-auth
Keychain: wp-<slug>                    ← the WP application password (wp-mcp-onboard puts it there)
ADC (phase 6 only)                     ← studio Google account, scopes: webmasters, siteverification, analytics.edit
```

Drafting `launch.json` for a new client is part of the skill: run `scripts/00_draft_config.py
<site_url> <wp_user> <slug>` to enumerate the published pages into a config skeleton, then fill
the brand facts, per-page titles/descriptions (§6.2/§6.3 patterns: 50–60 / 150–160 chars, phone
in every description, **no unverified claims** — no "licensed" unless the licence is confirmed,
no "free inspection" unless it is offered), the form spec per language, and the thank-you copy.

## Phases — run in order, each from the skill dir

```bash
V=~/.claude/skills/client-launch/.venv/bin/python; S=~/.claude/skills/client-launch/scripts; C=~/projects/<Client>/launch.json
python3 $S/00_preflight.py $C          # ALWAYS FIRST. Permission rules, venvs, gcloud, ADC scopes, dev token, Keychain, config completeness. Exit 1 = print the fixes to Mike, stop
$V $S/01_cutover_check.py $C     # exit 1 = blockers listed in launch-runs/RUNLOG.md; fix.* flags enable the safe fixes
$V $S/02_core_settings.py $C     # title, tagline, timezone, front page, site icon
$V $S/03_rankmath.py $C          # exit 2 = human gate (Skip Now) → relay, re-run. Verifies title/description/canonical/og on every page + sitemap
$V $S/04_fluentforms.py $C       # forms, notifications, honeypot, attribution fields + site-wide script, embed, END-TO-END PROOF, cleanup
$V $S/05_thankyou.py $C          # thank-you pages (noindex) with generate_lead; redirect target for phase 4 (run 5 then re-run 4 if the URL was not known)
$V $S/06_google.py $C --dry-run  # then without --dry-run. exit 2 = human gate (GA ToS / ADC scopes)
```

Order note: phase 4 needs `thank_you_url` per language. If the thank-you pages do not exist
yet, run 05 first, copy the URLs into `forms.languages.<lang>.thank_you_url`, then run 04.

What each phase proves (all recorded in `launch-runs/RUNLOG.md` next to the config):

| Phase | Proof |
|---|---|
| 01 | WP url = live domain; no `x-robots-tag: noindex`; zero old-host strings in any `_elementor_data`; defaults gone; plugin conflicts surfaced |
| 02 | root `<title>` carries the site title; favicon tags present |
| 03 | every page's `<title>`, meta description, canonical and `og:image` match the config byte-for-byte; `sitemap_index.xml` 200 |
| 04 | per language: real submit accepted (302 to thank-you), honeypot → 422, missing consent → 423, blank required → 423, bad email → 423; test entries deleted; entries remaining reported |
| 05 | thank-you page `noindex`, `data-elm-lead` present, not in the sitemap |
| 06 | GSC property verified + sitemap submitted; GA4 property/stream/measurement id, `generate_lead` key event, gtag on every page |

Then the **human proof** the scripts cannot do: check the studio inbox for the test emails
(Gmail MCP: `subject:` the test marker) — delivery through the host's relay is only known
when a message actually arrives.

## What the scripts assume about the site (studio build conventions)

- Elementor atomic build with `css_id` conventions from `build_page.py`: top-level containers
  `elm-bilingual-*`, `elm-enhance-*`, `elm-header-*`, `elm-hero-*`, `elm-sec-black-footer-*`.
  Phase 5 clones those to make a thank-you page. For a site without them, set
  `thank_you.mode = "existing"` and point at pages made another way.
- `_elementor_data` is exposed as REST page meta (the emcp-tools connector registers it).
  Without it, phases 4–6's page edits need the Elementor MCP tools instead.
- Kit CSS carries the `.elm-ff` form styles and `.elm-legal` rules (see Eliminatis
  `build/theme/kit-custom-css.css`); copy those blocks into a new client's kit.

## Fluent Forms — the studio default form

`name · phone (tel, hint under input) · town/ZIP · what are you seeing (select) · email
(optional) · consent checkbox` + 13 hidden attribution fields. Per language, fully localized
including validation messages ("a Spanish page with an English validation error is worse than
no Spanish page"). Consent wording = TCPA when the business will call/text back: names the
seller, "not a condition of purchase", rates may apply, STOP to opt out, links to the privacy
policy. Confirmation = **redirect to the thank-you page**, never same-page.

REST gotchas learned the hard way (already handled in the script — do not "simplify" them):
`POST /settings/{id}` without `meta_id` INSERTS a duplicate row and Fluent Forms reads the
first one; the blank template seeds a disabled "Admin Notification Email" row; the honeypot
field is `item_{form_id}__fluent_sf` and must be submitted empty; `phone` element is Pro-only
(use `input_text` type tel).

## Google — one-time studio prerequisites (done 2026-09-16; repeat only if the project changes)

The studio GCP project is **QuickIntelligence** (ID `sereniteintelligence`, OAuth app
"MakeThisQuick-AdsAutomation"). One project for every client — never per client. What phase 6 needs
from it, and how each was done so it can be redone:

1. APIs: `gcloud services enable searchconsole.googleapis.com siteverification.googleapis.com analyticsadmin.googleapis.com --project sereniteintelligence`
2. Consent-screen scopes (Google Auth Platform → Data Access → *Add or remove scopes* → **Manually add
   scopes** box): `…/auth/webmasters, …/auth/siteverification, …/auth/analytics.edit` → *Add to table* →
   *Update* → **Save** on the Data Access page. Publishing status stays **In production**. The Chrome
   extension can drive this.
3. ADC re-auth (`--no-launch-browser` is rejected with `--client-id-file`): run the normal flow with the
   browser suppressed and open the printed URL in the extension's own tab — the localhost:8085 redirect
   works from any tab:
   `BROWSER=/usr/bin/true gcloud auth application-default login --client-id-file=$HOME/.config/gcloud/ads_oauth_client.json --scopes=…adwords,…cloud-platform,…webmasters,…siteverification,…analytics.edit > out.txt 2>&1 &` then `grep -o 'https://accounts.google.com[^[:space:]]*' out.txt`.
   **Human**: passkey/2FA prompts and the consent "Allow" (never enter a password on the user's behalf).
   Afterwards `/mcp` reconnect the Serenite Ads servers (they cache the old token).
4. Check: `curl "https://oauth2.googleapis.com/tokeninfo?access_token=$(gcloud auth application-default print-access-token)"` lists all five scopes.

## Google — ownership model (Mike, 2026-09-15)

Studio account owns everything; the client is added later as an owner/admin via
`google.extra_owners`. One **GA4 account per client** (transferable), URL-prefix GSC property
verified by META tag through Rank Math (no DNS step). Where to see it all:
Search Console property picker · analytics.google.com → Admin → account picker ·
ads.google.com MCC → Accounts.

## Self-improvement — mandatory on every run

1. **Before phase 1:** read `LEARNINGS.md` top to bottom. If an entry names a check the
   scripts do not yet make, add it before running.
2. **During:** any time a phase fails, a verify mismatches, or you do something by hand that
   the script should have done — fix the script (or the config template) *in this run*, not
   "later". The scripts are the product; the client site is the test.
3. **After the last phase:** append a dated entry to `LEARNINGS.md` with: client slug, what
   surprised you, what you changed in `scripts/` or `templates/`, what still needs a human.
   Add a one-line row to `CHANGELOG.md`. Then write the run summary into the client's
   `build/BUILD-LOG.md` and update the client's memory file.
4. **Contribute upward:** if a learning is not Fluent-Forms- or Rank-Math-specific but about
   the studio pipeline (a WPMU DEV behaviour, a Keychain/permission gotcha, an Elementor
   connector quirk), also update the relevant memory (`elementor-mcp-connector-quirks`,
   `wp-mcp-onboarding-automation`).

## Phase 7 — Google Ads (three gated steps; Mike, 2026-09-16)

The site being launched is not the end: the client also needs an **Ads account** (missed on the
first Eliminatis pass — that is the learning). Three scripts, three gates:

```bash
S=~/.claude/skills/client-launch/scripts; C=~/projects/<Client>/launch.json
$S/ads_env.sh 07_ads_account.py $C                 # creates the client account under the MCC (empty). LIVE WRITE → the classifier blocks it; Mike runs it with `!`
$S/../.venv/bin/python $S/07b_ads_draft.py $C ~/projects/<Client>/build/ads-draft-<date>.md   # renders the plan as prose; publish as a Google Doc (Drive MCP) in MIKE's Drive, never the client's folder
# 07c (campaign build, PAUSED) — NOT YET WRITTEN. Runs only after the client approves the doc AND a payment method is on the account.
```

- `ads` section of `launch.json` is the single source: locations, negatives, sitelinks, callouts,
  campaigns → ad groups → keywords (phrase), 10 headlines ≤30 chars, 3 descriptions ≤90. The
  draft and the eventual build read the same JSON, so the client approves exactly what ships.
- Copy obeys the same claim rules as the site: no "licensed", "free inspection", "24/7", "same day"
  unless verified. Keywords come from the client's research folder + spec §6.5 — never new research.
- **Account creation is automatic** (`CreateCustomerClient`) — the studio developer token reached **Basic**
  access on 2026-09-18. Preflight proves it every run with `07_ads_account.py --selftest` (validate_only:
  Google checks the request incl. token access level, creates nothing; there is no delete-account API, so
  this is the only residue-free test). If the token ever drops below Basic, 07a prints the MCC-UI fallback.
- **Payment method is a human step** (client's own payments profile; the studio never holds a card).
- MCC = MakeThisQuick LLC `1018945450`. Three stray "setup in progress" accounts (`7447397558`,
  `9800342988`, `1533588091`) exist outside it — never use them; they cannot be cancelled without
  finishing signup on a personal payments profile, so they are left alone.

## Phase 7 human steps that the API cannot do
- Add client users (Admin → Access and security) — user invitations via API are untested since Basic; try
  `CustomerUserAccessInvitationService` first and fall back to the UI.
- **Accept "Call and Messaging Ads Terms"** for the new account (banner in the MCC) — an owner click, and
  call assets may not serve until it is done. Surface it the moment campaigns are built.
- **Business Profile link: only ever a per-client business group.** The Data manager dialog offers the
  whole GBP *account* (all clients' listings) — never submit that. Split listings into business groups
  in Business Profile Manager first.
- Payment method: the client, in their own payments profile. Email template in Eliminatis BUILD-LOG §18.3.

## Phase 9 — the client-answers round (after the "what we need from you" doc comes back)
Answers arrive as prose annotations. Apply them mechanically: every pending panel in a studio build
carries an `elm-pending-*` css id, so an answer maps to an id → text swap + id rename, and a removal is
an id delete (`templates/answers_apply.example.py`). Missing pages behind links ("tiles are not
clickable") get built by cloning the template page with agent-written copy
(`templates/service-page-brief.example.md` + `templates/svc_build.example.py`). A flipped claim (free
inspections) fans out to buttons, meta, JSON-LD, form copy, ads copy AND the negative list — grep the
whole launch.json. Then re-run 03 and 04, and regenerate the Ads draft (read the previous doc's
annotations first; v-numbers, trash the old one).

## Verification the scripts cannot do (do it by hand every launch)
- Header at the top on at least one page per language (`getBoundingClientRect().top` ≈ 0) — a
  JS-inserted `<main>` once pushed the whole header to the bottom for four weeks.
- Mobile at 320/360/390 via a same-origin iframe sweep (never resize the user's Chrome window).
- Test emails actually in the inbox; a real-browser form submit once captcha is on.

## Phase 8 — after go-live: the weekly report (Mike, 2026-09-17)

Once campaigns are ENABLED (never before), a **weekly Google Ads analysis for the client** as a
digestible Google Doc in Mike's Drive (report-format rule): what ran, what it cost, which searches
produced leads (join Ads click data with the form entries' gclid/UTM fields), what we changed, what
we recommend for the budget. Same engine as `serenite-daily-ads-report`, pointed at
`ads.customer_id`, weekly cadence. **Commercial rule: the first report is free "just so they see
it"; from the second on it is part of paid monthly maintenance** — say so in the first one's cover
note. Not written as a script yet (08); build it from the Serenite skill when the first client goes live.

## Known limits (go in the report, not silently)

hreflang stays client-side without Polylang; `og:locale` is site-wide in Rank Math; Elementor
performance toggles, self-hosted fonts and ACF are wp-admin/file work; the Ads draft campaign
(07) is not written yet — it needs a client Ads account under the MCC and its own MCP server.
