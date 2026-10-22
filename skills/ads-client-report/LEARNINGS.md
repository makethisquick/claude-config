# ads-client-report — learnings

Append after every run. Mechanism and judgement only: never a client's figures,
account ids, search terms or lead details — this file is studio-wide.

## 2026-10-14 — first version, built from the Eliminatis report the client liked
- **`require('docx')` resolves from the SCRIPT's directory, not the cwd.** Installing
  the package in an output folder does nothing. `docx` now ships installed in the
  skill directory and `build_docx.js` resolves skill-dir → cwd → plain require.
- **matplotlib is not installed system-wide on this machine.** Use
  `~/.claude/skills/client-launch/.venv/bin/python` for `charts.py`.
- **No LibreOffice and no pandoc here**, so a .docx cannot be rendered to images.
  `verify.py` checks structure, images and language; say plainly that layout is
  unverified and ask the user to open it once. Claiming a visual check you did not
  do is the kind of thing that costs trust permanently.
- **Split the script from the prose.** The builder owns Word mechanics; a narrative
  JSON carries the words. Numbers always come from the data blob, so a chart can
  never disagree with the table beside it.
- **Bar labels collide at zero.** When a value is near zero the percentage and the
  count land on top of each other — stack them above the axis instead.
- **Counting leads is the credibility risk.** Google-hosted "Local actions"
  (Directions, Website visits, Menu views) inflate `all_conversions` enormously —
  one account showed 25 "conversions" that were 3 real leads and 22 map taps. Count
  only actions with `include_in_conversions_metric = true`, and report Search,
  Display and Local Services separately so none flatters another.
- **Three windows beat one number.** A single month cannot show direction, and
  direction is the thing a client actually wants to know.

## 2026-10-15 — two faults found by the studio owner reviewing the first run
- **A `null` in the config silently removed a whole section.** The first Serenite
  report shipped with no visitor-behaviour section because `ga4_property` was null —
  I had written null rather than looking the id up, and the report still *looked*
  complete, which is the dangerous kind of wrong. `pull_data.py` now prints a loud
  warning and records `ga4_missing_reason`; `find_ga4.py` lists and verifies
  properties so the id is never guessed. Verify with `--verify <id> --domain <site>`
  that the stream's URI actually matches the client's website — an account can own
  several properties and only one is collecting.
- **Local Services leads are charged whether or not they are leads.** A client was
  billed $65 for a lead that was a **23-second phone call**, never disputed, three
  weeks old, against a ~30-day credit window. `pull_data.py` now joins
  `local_services_lead` to `local_services_lead_conversation` and returns
  `lsa_dispute_candidates` — charged, under 60 seconds, undisputed — with the lead's
  age so the closing window is obvious. Raise these with the studio, not in the
  client report: disputing happens in the Local Services interface, owner-side.
- **General rule both faults share: absence is not evidence of absence.** A missing
  section and an undisputed charge both look like "nothing to report". Make the
  tooling say *why* something is missing rather than quietly omitting it.

## 2026-10-15 — first run on a Smart Campaign account shared directly (not under the MCC)
- **`pull_data.py` forced the manager id as login-customer-id**, which fails for an
  account a client shares with the studio login directly. `mcc_customer_id` is now
  optional; null means "direct access, send no login-customer-id".
- **Smart Campaigns break the `include_in_conversions_metric` rule.** Google-hosted
  "Local actions - Directions" and "Clicks to call" land in `metrics.conversions`
  even when that flag is false — one account showed 1,143 "conversions" that were 4
  confirmed calls, 32 call taps and 1,107 direction requests. Config now takes
  `lead_actions` (recount leads from exactly these action names) and
  `secondary_actions` (reported as their own rows, never blended). Always look at
  `segments.conversion_action_name` before trusting the leads number.
- **For a walk-in venue, direction requests are the main signal**, not leads. Lead
  with them, call them interest not visits, and recommend an offline count at the
  door — it is the only way to get a cost per visitor.
- **Paused campaigns were inflating the planned budget** (their budgets were summed).
  Only ENABLED campaigns count now.
- **`ga4_property: false` still printed the missing-GA4 warning.** False now means
  "deliberately none" and is recorded as the reason; null still warns loudly.
- **The spend chart's labels collided with the budget line** whenever spend sat near
  budget (the usual case). Budget label now sits in the headroom, values mid-bar.
- **Smart Campaigns expose no ad-group metrics and no keyword_view**, so the per-lead
  table comes back empty. Use `smart_campaign_search_term_view` for a
  "what people searched" table instead.
- **Check the website itself**: one fetch showed no Google tag, an untappable phone
  number and a broken form shortcode — three concrete improvements the Ads data
  alone would never reveal.

## 2026-10-17 — a joining bug that silently fabricated a fact
- **Enrich a lead from its OWN ad group, never from the campaign.** `pull_data.py`
  filled in device and hour with a campaign-level query, so when two leads landed on
  the same day they both inherited the first segment row — one lead was reported at
  02:00 when it actually came in at 17:00. The output looked entirely plausible,
  which is what made it dangerous: a client report would have stated a confident,
  invented fact. Scope every enrichment query to the same ad group as the lead, and
  escape quotes in the ad-group name. Caught only because a hand-check from an
  earlier session disagreed — worth re-deriving one number by hand per report.

## Always cross-check GA4 `generate_lead` against the Ads conversion count

On Eliminatis (2026-10-21) Google Ads reported **3** leads in 30 days and an apparent
11-day dry spell. GA4 reported **10** lead events over the same window, 6 of them from
`cpc`. The ads were fine; the *measurement* was broken, and a report built on the Ads
number alone would have told the client their advertising had stopped working.

**Root cause, worth memorising because it is silent and common:** the site loaded
gtag for the GA4 property only —

```js
gtag('config','G-L99HVQ31R9',{anonymize_ip:true});          // GA4 — configured
gtag('event','conversion',{send_to:'AW-.../label', ...});    // Ads — never configured
```

With no `gtag('config','AW-...')` the Ads destination is never initialised, so the
`conversion` event has nowhere to go while `generate_lead` reaches GA4 from the same
handler. It can appear to work intermittently (gtag sometimes auto-loads the
destination), which is worse than failing outright — it produces a partial count that
looks plausible.

**Do this on every report before writing a word:**
1. Pull GA4 event counts for the lead event and compare the total and the per-date
   series against the Ads conversion series.
2. If GA4 > Ads, split GA4 by `sessionMedium`. Only `cpc` rows should ever appear in
   Ads — direct/organic leads are correctly absent and are not evidence of a fault.
3. A divergence that *starts on a specific date* points at a site change on that date.
   Check what was deployed. Here it coincided exactly with a caching/JS-delay change.
4. Fetch the live page and grep for `gtag('config'` — confirm an `AW-` destination is
   configured, not just referenced in `send_to`.

**Report the true number with the caveat**, not the platform's number. Leading with
"Google says 3, your site says 10, here is why" is more credible than either figure
alone, and it is the difference between a client believing the campaign failed and
understanding it is working.

**Also learned:** when every lead is a phone tap and the form conversion has *never*
fired, say so explicitly. It is a finding, not an omission — it tells the client where
the next fix belongs.
