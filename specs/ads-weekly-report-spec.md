# Google Ads weekly client report — studio skill spec

*MakeThisQuick · v2 · 2026-09-20 · author: Claude, for Mike's review. v2 incorporates a five-reviewer pass (Ads API engineer, paid-media analyst, systems engineer, client-communications, privacy/compliance); every change is traceable to a finding in §10.*

## 1. The problem this fixes

The studio's Google Ads reporting knowledge lives in a skill called `serenite-daily-ads-report`, backed by MCP servers called `serenite-ads` and `serenite-ads-write`. None of that is Serenite-specific. The servers take the studio GCP project as their only argument and reach every account under the MakeThisQuick manager account (MCC `101-894-5450`) with one credential; the skill's logic — pacing maths, impression-share diagnosis, search-term bucketing, junk-placement detection, the "don't judge conversion rate on a short window" rules — applies to any account. Only the constants (customer id, timezone, the one biddable conversion, the policy quirks) are Serenite's.

The naming has already caused real confusion: the Eliminatis weekly report was described as running on "Serenite's engine", and the cross-client isolation rule (never let one client's tooling touch another's data) is harder to keep when the tooling carries a client's name. This spec defines the replacement: one studio skill, **`ads-weekly-report`**, that runs against any client the studio has onboarded, and — after the new skill is proven — a rename of the two MCP servers to **`studio-ads`** / **`studio-ads-write`**.

## 2. Where it sits in the pipeline

```
wp-mcp-onboard  →  client-launch (00–07)  →  ads-weekly-report (this)
  site + MCP         SEO, forms, attribution,    T+1 health check
  connector          GA4/GSC, Ads account,       weekly client Google Doc
                     draft → approval → build    per-client actions ledger
```

The report never runs before `client-launch` phase 7c has enabled campaigns — there is nothing to report on and the first-report-is-free clock has not started. Everything the report needs to know about a client is already in that client's `launch.json`; this skill adds one `report` block to that file and reads nothing else.

## 3. Principles (non-negotiable)

1. **Read-only.** The report never mutates an account. Recommendations go into the client's actions ledger and are applied only after Mike says go, through the write server's dry-run → confirm flow, in a separate step.
2. **One client per run, addressed by config.** The customer id, timezone, currency, campaigns, forms and Drive folder all come from `launch.json`. No client identifiers in code, skill text, server names or script names. **No default lexicons or rulings ship with the skill** — a copied `launch.json` carrying another client's `never_negative` list is exactly the leak this prevents; empty required lists fail preflight.
3. **Zero cross-client contact, enforced by a live check, not a string match.** Every run starts with the isolation guard (§4.3 step 0): a `customer_client` query under the MCC proving the config's `customer_id` is an enabled, non-hidden, non-manager child, plus `customer.descriptive_name` containing `brand.short_name`, plus the Drive folder's name containing it. Any failure aborts before the first data pull. **Each client's run is a fresh Python interpreter** — the `google-ads` client factory caches `login_customer_id` for the life of the process.
4. **Client-facing output is a Google Doc in prose** (Mike's report-format rule). Every Ads term is glossed in plain language the first time it appears and repeated in a glossary table. Numbers live in an appendix. A local `.md` + `.json` is always written first — the durable record and the diff source.
5. **First report free, then maintenance.** The first Doc closes with one line saying so; from the second on it is part of paid monthly maintenance. Enforced by `report.reports_sent`, incremented only on a successful Doc creation.
6. **Say what the sample supports.** One week supports conclusions about traffic composition and auction position; it does not support cost-per-lead rankings between ad groups. Under ~100 qualified clicks the *internal* `.md` states the probability of zero conversions rather than implying failure; above it, the rate can be judged. Lifetime figures sit beside the window. In the client Doc the same fact is written in plain words ("normal for the first two weeks") — §3.7 governs the Doc, this principle governs the analysis.
7. **Never in a client Doc:** customer/MCC/campaign/ad-group/conversion ids, GAQL, "gclid", "Fluent Forms", `launch.json`, agent names or "Claude", any other client, the word *waste* (write "searches that cost money and brought nobody"), cost-per-lead comparisons between ad groups under ~10 leads each ("too early to say which service is cheapest"), Google policy status codes, probability language ("29% likely" → "normal for the first two weeks"), the ledger itself.
8. **`LEARNINGS.md` is studio-wide and carries process lessons only** — mechanism, API behaviour, script bugs, config-shape fixes, in the style of §5. Never a client name tied to account data, a customer id, a search term, a keyword, a lead's name/phone/email, or any figure from a specific account. A lesson needing an example is written generically ("a healthcare client's form lacked gclid").

## 4. Architecture

### 4.1 Credentials, reach and execution
- Identity: the studio's Application Default Credentials (OAuth app **MakeThisQuick-AdsAutomation**, GCP project display name **QuickIntelligence**, consent screen *In production* so tokens do not expire every 7 days). **Known residual of the naming rule:** the project's immutable *ID* is `sereniteintelligence` — GCP project IDs cannot be renamed, only the display name (done). The ID appears nowhere a client sees; replacing it means a new project, new OAuth client, re-doing brand verification and Basic access, and re-issuing ADC on every machine. Treated as a separate, deferred migration — §7.7, decision §8.7.
- Authority: the studio developer token (macOS Keychain `google-ads-dev-token`), at **Basic** access (15,000 operations/day on production accounts).
- Scope: `login-customer-id` = the MCC. Every client account created through `client-launch` 07a is a child of the MCC; Serenite (`216-927-2958`) is already a child. One credential, every client.
- **Execution:** the scheduled report calls the `google-ads` Python library directly (`gads_write.client.get_client()`), never through an MCP session — a scheduled job must not depend on a connected session (the 09-16 "reconnect before the report" ritual is the failure this removes). `get_client()` raises without `GOOGLE_ADS_DEVELOPER_TOKEN` in the environment, so **every invocation goes through the Keychain-sourcing wrapper** (`ads_env.sh` or its twin in this skill). The two MCP servers stay for interactive work.
- **Scheduling:** a `launchd` agent on Mike's Mac (`~/Library/LaunchAgents`, `StartCalendarInterval`, one entry per client), each invoking the wrapper with that client's `launch.json`. Keychain and ADC are local-only, so no cloud scheduler can run this; a Claude Code session-only cron dies with the session. Keychain items used by the wrapper must be set to *Always Allow* for the launcher binary so a non-interactive job never blocks on a prompt nobody sees. A run missed because the Mac was asleep is caught by the next morning's `--health`.

### 4.2 Config contract — additions to `launch.json`
```json
"report": {
  "cadence": "weekly",
  "weekday": "mon",
  "window_days": 7,
  "reports_sent": 0,
  "drive_folder_id": "<client folder in Mike's Drive>",
  "drive_folder_name": "<must contain brand.short_name>",
  "client_first_name": "Joan",
  "reader_language": "en",
  "campaign_languages": ["en", "es"],
  "healthcare": false,
  "lead_join": { "forms": [3, 4], "gclid_field": "gclid", "utm_fields": ["utm_campaign", "utm_adgroup", "utm_term", "lang"] },
  "biddable_conversions": ["<conversion_action_id>"],
  "services": { "offered": ["…"], "offered_not_advertised": ["…"], "not_offered": ["…"] },
  "waste_terms": ["…"],
  "never_negative": ["…"],
  "withdrawn_recommendations": [ { "change": "…", "date": "YYYY-MM-DD", "reason": "…" } ],
  "decisions": [ { "rule": "…", "date": "YYYY-MM-DD", "by": "Mike" } ],
  "policy_notes": "…",
  "lsa": { "enabled": false },
  "display": { "enabled": false }
}
```
- `services` replaces a flat good/bad word list: a term matching `offered_not_advertised` is *marginal* — never a negative, never a keyword; a term matching `not_offered` is a negative candidate; `waste_terms` covers generic junk (jobs, DIY, products). All three lists plus `never_negative` are required; the skill ships none.
- `withdrawn_recommendations` and `decisions` are how a settled ruling survives a new session — the engine refuses to re-propose anything listed.
- `ads.customer_id`, `ads.mcc_customer_id`, `ads.time_zone`, `ads.campaigns[]`, `thank_you`, `forms`, and `brand` are already there from `client-launch`. Preflight validates every field above.

### 4.3 The engine — `08_weekly_report.py`
One script, flags `--health` (T+1, terminal only, never counts as a report), `--md` (local files only), `--doc` (also publish the Google Doc), `--force` (re-run an existing window; appends "(re-run)" to file and Doc title).

**Guards**

0. **Isolation and idempotency guard.** With `customer_id = MCC`, `login-customer-id = MCC`: `SELECT customer_client.client_customer, customer_client.level, customer_client.status, customer_client.manager, customer_client.hidden FROM customer_client WHERE customer_client.level = 1`. Reject unless the config id appears with `status = ENABLED`, `hidden = false`, `manager = false`. Then `customer.descriptive_name` must contain `brand.short_name`; the Drive folder's name (metadata read) must contain it. Then: if `reports/ads-weekly-<window_end>.md` already exists, exit unless `--force` — Drive content cannot be patched, so a duplicate Doc is the failure to prevent.

**Data**

1. **Dates.** Resolve *today* in the client's timezone; explicit `BETWEEN` ranges. `LAST_7_DAYS` excludes today and hides a campaign that started today. **Impression-share queries end at today − 2** — Google restates fresh IS by whole points; act only on 48-hour-settled data. `change_event` is hard-capped at the trailing 30 days regardless of the WHERE clause and needs an explicit `LIMIT`.
2. **Serving guard.** If every campaign has zero impressions for the window: query `customer.status`, `billing_setup.status`, `account_budget.status` and report their literal values; corroborate with `search_impression_share == 0.0` exactly — Google reports any true non-zero share under 10% as `0.0999`, never `0.0`, so a naive `< 0.1` conflates "suppressed" with "never entered an auction" — and with empty `ad_group_criterion.position_estimates` on every keyword. Then write the *not serving* note, listing the UI-only causes the API cannot see (the post-signup payment-verification banner, policy holds) as the human checks — the Eliminatis 09-18→20 case, where every API status was green.
3. **Pulls (read-only GAQL, ~15–20 operations):** campaign × day (cost, impressions, clicks, conversions, `primary_status` + reasons); ad group; **search terms** from `search_term_view` — clicked *and* zero-click terms (the zero-click set is the larger sample of what keywords actually match), forked to `campaign_search_term_view` if a Performance Max campaign ever exists; impression share incl. rank-lost and budget-lost (settled window); **keyword health from `ad_group_criterion`** (`quality_info.quality_score`, `system_serving_status` for `RARELY_SERVED`, `position_estimates`, approval) joined to metrics for zero-impression keywords — `keyword_view` carries none of these fields; ad policy (`approval_status`, `review_status`, per-asset `policy_summary_info` on `APPROVED_LIMITED`); conversions **by action in their own query** (segments cannot mix with cost metrics), distinguishing `conversions` (biddable) from `all_conversions`, which includes Business Profile taps (Directions/Website) that are not leads; Display placements + device only if `display.enabled`; LSA campaign and leads only if `lsa.enabled`.
4. **Lead join.** Pull Fluent Forms entries for the window (`fluentform/v1`, forms from config), read the hidden attribution fields written by `client-launch` 04 (gclid, UTM set, landing page, language). Corroborate against Ads' own click record via `click_view` — one calendar day per query, trailing 90 days only — using `segments.keyword.info.text`, campaign and ad group, before naming the source in the Doc. **Keyword-level is the finest guaranteed granularity**; Google withholds many search terms, so the Doc says "the search 'X'" only when the term is exposed and "a bed-bug search" otherwise. Report leads as people in the client's Doc (their own data). Phone-tap conversions are counted but cannot be joined to a person — say so. **Healthcare clients (`healthcare: true`):** the persistent `.json` and diff store only gclid, source keyword/ad group and count — never a lead's name, phone, email or address; full lead detail appears only in that week's Doc.

**Analysis**

5. **Pacing.** Google's limits: 2× the daily budget on any single day, 30.4× per month — **computed per campaign from the budget in force on each day** (a $51 day against a $35 budget that day is not a breach of a later $25 budget; Search and Display have separate ceilings). If the campaign has an ad schedule, compute the per-*active*-day target (`monthly_limit / active_days`). Project month-end and say when the campaign will go dark if the run-rate exceeds the limit.
6. **Budget-raise gate** — three conditions, all required, reported every week with the failing one named: (a) waste share on post-negative data under 25%; (b) budget-lost exceeds rank-lost on the majority of ≥5 settled serving days; (c) `campaign.primary_status` reads `BUDGET_CONSTRAINED`. Rank-lost ≫ budget-lost means a raise buys more of the same placement — recommend relevance work instead. Never diagnose the binding constraint from one day.
7. **Search-term buckets.** High-intent / marginal / searches-that-brought-nobody, with the cost of each, driven by `services` + `waste_terms`; waste above ~25% of spend names specific negatives. **Every proposed negative lists its plural/spacing variants** (`dermatologists` served past `dermatologist`) **and its level** — ad-group-only negatives leak across groups; default to campaign level. Zero-click ad groups are checked against `search_top_impression_share` before being called bad — ads rendered below the organic results have near-zero CTR by construction, and the fix for research-intent queries is negatives, not bids. Nothing in `never_negative` or `withdrawn_recommendations` is ever proposed. Waste share states its denominator (attributable spend vs total; withheld queries leave a gap). **Never invent search volume, benchmark CTR or industry CPC** — no Keyword Planner access.

**Records**

8. **Diff and verification.** Load last week's `.json` for deltas — but **"what changed" and "still unapplied" are verified against the live account** (`campaign_criterion`, `ad_group_criterion`, ad status), never inferred from a prior report's to-do list; two Serenite runs re-flagged negatives that were already live. IS values for the prior week are re-pulled (restated).
9. **Actions ledger** (`~/projects/<Client>/reports/actions-ledger.json`, per client, never merged). Fields: `id`, proposed date and report, entity id, exact change (term, match type, level, or budget/bid), justifying query and its cost, `status` ∈ proposed/approved/applied/verified/declined/withdrawn, verification-read result, running spend on the justifying queries since proposal, decided-by. **The report opens its internal summary with every item still `proposed`, its age, and what it has cost since** — ten Serenite actions sat unapplied for three weeks.
10. **LSA and separate-language campaigns** report in their own paragraph with their own cost per lead, never blended into Search.
11. **Outputs.** `~/projects/<Client>/reports/ads-weekly-<date>.md` and `.json`; the Google Doc in the client's folder (`create_file`, `text/markdown` → native Doc; body final in one call; `fileSize: 1` in the response is not a failure); `reports_sent += 1` written atomically with the config; a terminal summary; the ledger update.

### 4.4 The Doc — structure
Title: *<Client> — Google Ads, week of <Mon–Sun>*. No section over ~80 words except the appendix. Sections:

1. **This week in three lines** — always *leads → money → the one thing we are doing about it*, plus the verdict ("worth it?" with its caveat). Example: "Your ads brought in 3 leads this week — 2 bed-bug enquiries from Newark and 1 Spanish-language call. That cost $412, about $137 per lead. The one change worth making: block searches for 'bed bug spray', which spent $61 and produced nobody." An urgent finding (spend over the daily ceiling, an ad disapproved, a campaign dark) *replaces* the third line rather than adding a section.
2. **Your leads** — each as a person: search (when exposed), day, language, form or call. Phone taps that cannot be tied to a person are counted in one sentence.
3. **What people searched for** — three good, three bad, what we blocked. Spanish terms appear in Spanish with a bracketed gloss once: *"exterminador de chinches" (bed-bug exterminator)*; never translate ad copy back; never present the Spanish campaign as a separate report.
4. **What changed since last week** — prose, three sentences max, direction before number, only changes beyond the noise (one lead, ~15% spend); otherwise "About the same as last week." Derived from the ledger and the live verification, not from `change_event`. Week 1 is standalone.
5. **What we recommend, and why** — one sentence each; the budget-gate answer lives here in plain words, never as a term.
6. **What we need from you** — booking confirmations, service rulings, anything only the client can answer.
7. *First report only, as the closing line before the appendix:* "This first report is on us. From next week it comes as part of your monthly maintenance, so you will get one every Monday without asking."
8. **Appendix** — the numbers table (plain-text cells, real header row) and the glossary.

Glossary carried by the script: Impressions — times your ad was shown · Clicks — times someone tapped it · Cost per click — what one visit cost · Cost per lead — ad spend divided by leads; unreliable under ~10 leads · Search term — the exact words someone typed · Negative keyword — a word that stops your ad showing · Impression share — how often you showed when you could have · Lost to budget — missed because the daily budget ran out · Lost to rank — missed because Google ranked competitors' ads higher · Quality score — Google's 1–10 grade of how well the ad matches the search · Conversion — a form sent or a phone number tapped · Ad schedule — hours the ads are allowed to run.

### 4.5 Who runs it
The trigger is `launchd` (§4.1). **vera** is the agent responsible for every client's run and ledger — one client at a time, each as `subprocess.run([python, "08_weekly_report.py", <that client's launch.json>])`, a fresh interpreter per client; "across clients" means responsibility, never a merged file. **sloane** shapes the client Doc when the prose needs more than the template gives. No file read or written by one client's run is shared with another's.

## 5. Learnings carried in (each one is a rule above)

| # | What happened | Rule in this skill |
|---|---|---|
| 1 | `LAST_7_DAYS` excludes today; a campaign that started today read as dead | Explicit date ranges in the client timezone (§4.3.1) |
| 2 | 15 days of no reporting when ADC tokens expired every 7 days (consent screen in Testing); "This app is blocked" on gcloud's shared client | Studio OAuth app *In production*, own Desktop client; preflight checks ADC scopes every run |
| 3 | `get_client()` caches the client for the process; re-auth on disk does nothing until restart — "re-auth first, reconnect second" | Fresh process per run and per client (§3.3, §4.5) |
| 4 | Fresh impression share is restated by whole points for ~48 hours | IS window ends at today − 2; prior-week IS re-pulled (§4.3.1, 4.3.8) |
| 5 | Ad-schedule compression made normal spend look like overspend; a $51 day was judged against the wrong day's budget; Search and Display ceilings were conflated | Per-campaign, budget-by-day pacing with per-active-day target (§4.3.5) |
| 6 | Mike's standing question: *when* to raise the Search budget; "68% waste buys more waste" | Three-condition gate, reported weekly with the failing condition (§4.3.6) |
| 7 | Zero-click ad groups were rendering below organic; bidding up to win DIY queries is the most expensive mistake available; zero-click terms are the larger sample | Top-IS check before judging; negatives over bids; zero-click pass (§4.3.7) |
| 8 | Negatives did not catch plurals/spacing (`dermatologists`, `medi weightloss`); ad-group negatives leaked across groups | Variants and level on every proposed negative (§4.3.7) |
| 9 | Display CTR of 10–20% from lock-screen/quiz domains reporting as `WEBSITE`; app-category exclusions could not block them | Placement junk detection only when Display exists; never claim the app exclusion protects (§4.3.3) |
| 10 | Conversions credit back to click date; zero from 17 clicks is ~29% likely at 7% CVR | Probability under ~100 clicks, judgement above; lifetime beside window (§3.6) |
| 11 | `WEBPAGE_CODELESS` on a thank-you URL is fragile for AJAX forms; a `generate_lead` fired on page *load*; 16 "conversions" were 1 lead + 15 Business Profile taps | Biddable `conversions` vs `all_conversions`; GBP taps are never leads (§4.3.3) |
| 12 | Serenite captures gclid (since 08-04) but the join was manual, and Google withholds many search terms | Scripted join on every `client-launch` site; keyword-level is the guaranteed granularity; `click_view` corroboration (§4.3.4) |
| 13 | Conversion actions could not be mutated via API (`MUTATE_NOT_ALLOWED` on Google-created types) | Reads goal-level `biddable` and `include_in_conversions_metric`; changes flagged as UI work |
| 14 | Healthcare policy: many "safe-proxy" keywords rejected; "Eligible (limited)" does *not* stop delivery; certification was a wrong early reading | `policy_notes`; check actual impressions before calling an ad group suppressed; never recommend exemptions |
| 15 | Mike's rulings (`facial`/`hydrafacial` never negatived; Display stays at $5; "do not raise"; fillers offered-but-never-advertised) and withdrawn calls (`facelift` negative, Oxygen pause) were re-proposed by later sessions | `services`, `never_negative`, `decisions`, `withdrawn_recommendations` in config; engine refuses to re-propose (§4.2) |
| 16 | Ten recommended actions sat unapplied for three weeks; two agents re-flagged negatives already live | Ledger with ageing and cost-since-proposal; verify against the live account, not a prior report (§4.3.8–9) |
| 17 | Reports as `.md` on the laptop could not be shared; analyst-table prose did not read as human | Prose Google Doc, glossed terms, `.md` kept as the record (§3.4, §4.4) |
| 18 | Drive `update_file` is metadata-only; content cannot be patched; `fileSize: 1` is not a failure | One-shot body; idempotency guard; companion docs for follow-ups (§4.3.0, 4.3.11) |
| 19 | Duplicate campaigns from re-running `create_search_campaign`; the change log missed a campaign's creation but captured budget/status/criterion changes | Read-only; `change_event` bounded (30-day cap) and treated as incomplete for creation events |
| 20 | HIPAA: offline conversion upload and LSA "ask for review" both disclose "sought care" signals without a BAA; lead identities deliberately not persisted | `healthcare` flag: PHI-minimised history; never proposes offline uploads or review requests (§4.3.4) |
| 21 | Five reads were cheaper than spawning an agent for a 48-hour check-in | `--health` is a direct script, no agent |
| 22 | "Setup in progress" Ads accounts can hold a live LSA campaign; the API cannot cancel accounts | Isolation guard rejects anything not an enabled MCC leaf; never audits siblings (§4.3.0) |
| 23 | Explorer-tier token blocked account creation; brand verification failed on a homepage privacy URL | Now Basic; OAuth app's privacy/ToS links point at the real policy pages |
| 24 | `billing_setup APPROVED` + campaigns `ELIGIBLE` and still 0 impressions for 3 days — Google Payments' post-signup verification banner, UI-only | Serving guard with API corroboration and named UI-only causes (§4.3.2) |
| 25 | No Keyword Planner access on the account | Never invent volume, benchmark CTR or CPC (§4.3.7) |

## 6. Scaling — "any client, even Rojas"

**What a new client needs before the first report can run:**
1. `wp-mcp-onboard` — site on the studio WPMU DEV host, Elementor MCP connector.
2. `client-launch` 00–06 — SEO, Fluent Forms with the attribution hidden fields, thank-you pages firing the conversion, GA4 + GSC (studio-owned).
3. `client-launch` 07a — Ads account under the MCC (one API call at Basic), 07b — the client-approval Doc, **client approval + client payment method + Google's payment verification**, 07c — build, enable, accept Call & Messaging terms, link the client's *own* Business Profile.
4. `report` block in `launch.json` (all required lists filled for *this* client); a client folder in Mike's Drive; a `launchd` entry.
5. T+1 `--health`, T+3/4 negatives pass (search terms only — IS is not settled), T+7 first Doc.

**`--health` minimum:** campaign `primary_status` + reasons; impressions > 0 per campaign; ad `approval_status` and `APPROVED_LIMITED` topics; `RARELY_SERVED`/disapproved keywords; yesterday's spend vs 2× budget; conversion-action status and last fire; a form → thank-you test hit; ADC scope check; the UI-only checks listed by name.

For **Rojas** specifically today: the site is on staging with unratified prices and no Ads account; there is no `launch.json`. Steps 1–2 are the launch itself; step 3 needs an Ads budget decision and the client's card; the report is the last thing, not the next thing. Agent effort once the client says go, from the Eliminatis run: preflight + draft config ~30 min; 07a account creation ~5 min; 07b approval Doc ~1 h; 07c build + validate ~1 h; enable, Call & Messaging terms, own-GBP link ~30 min; `report` block + Drive folder + `launchd` entry ~30 min; T+1 health and T+7 first Doc ~30 min — **about 4–5 hours of agent work**, spread across the client's approval gates (draft → approval → payment → Google's verification), which are the long pole and took Eliminatis nine days.

**Capacity:** a report is ~15–20 read operations; at Basic access (15,000/day) that is several hundred clients per day before quota matters. Weekly is the default; `cadence` per client. One `launchd` entry per client, each a fresh process — no shared state between clients, by design.

**Drive layout:** one folder per client in Mike's Drive; the folder id and name live in config and are verified at run time. **Each client folder is shared only with Mike and that client's designated contact — never studio-wide, never a folder owned by a third party** (the shared "SERENITE MARKETING 2026" folder is not writable by this skill). Studio-level documents (this spec) live in **MTQ / Studio Specs**, never in a client folder.

**Offboarding (new):** when an engagement ends — remove the client's account from reporting scope (delete the `launchd` entry and the `report` block), unlink the account from the MCC if the client takes it over, trim or delete the client's Drive folder and local `reports/` against the privacy policy's engagement + 12-month ceiling, and record the end date in the client's own record, never in `LEARNINGS.md`. The shared OAuth token is not revoked (it serves other clients); what ends is this client being in scope.

**Skill self-improvement:** like `client-launch`, the skill reads and appends its own `LEARNINGS.md` on every run — under the §3.8 content rule — and is committed to `github.com/makethisquick/claude-config`.

## 7. Migration from `serenite-daily-ads-report`

1. Create `ads-weekly-report` with the engine above. **Before its SKILL.md text becomes the new skill's first `LEARNINGS.md`, correct two errors in it:** the claim that Serenite's form captured no gclid (retracted 08-26) and the stale Explorer-tier quota.
2. Serenite's constants move into a `report` block in `~/projects/Serenite/launch.json` (customer id, timezone, biddable conversion `7670763779`, `services`, `never_negative`, `decisions`, `withdrawn_recommendations`, `policy_notes` with `healthcare: true`, `display.enabled: true`, `lsa.enabled: true`, the ad schedule, cadence as Mike chooses).
3. Keep the old skill running until the new one has produced one Serenite report that Mike accepts.
4. **Rename the MCP servers only after step 5 (old skill retired) — not before.** Until then, add `studio-ads` / `studio-ads-write` as *second* entries in `~/.claude.json` pointing at the same launcher scripts, so both names resolve during the trial; the write server additionally gets a `customer_id` guard. Remove the `serenite-*` entries in the same edit that deletes the old skill, and update every reference (`client-launch` SKILL.md, memory `serenite-ads-api-auth`, any cron prompts) in that commit.
5. Retire `serenite-daily-ads-report`. Memory files and the account log keep their Serenite names — they are client records, not tooling.
6. Update memory: `report-format-google-doc`, `serenite-ads-api-auth`, `wp-mcp-onboarding-automation`.
7. **Deferred — GCP project ID.** `sereniteintelligence` is immutable. If Mike wants the last client name out of studio infrastructure: create project `quickintelligence` (or similar), new OAuth Desktop client, Branding + brand verification again (the policy pages now satisfy it), enable the Ads API and re-apply for Basic (the developer token belongs to the MCC, not the project, so it carries over), re-issue ADC with the five scopes, update the two launcher scripts' project argument. One evening of work with a hard cutover; recommended only after the new skill has run for a month.

## 8. Decisions for Mike

1. Doc folder per client — create "Eliminatis" in Drive now (none exists); confirm the folder-per-client convention and the Mike + client-contact-only sharing rule.
2. Client tone — plain-English body, numbers in an appendix (recommended, as specified in §4.4).
3. Week-over-week from week 2 in prose with noise thresholds (recommended); week 1 standalone.
4. Serenite cadence after migration — stay daily, or weekly like everyone else with a `--health` mid-week.
5. Confirm the `launchd`-on-Mac scheduling model (the only one that can reach Keychain + ADC) and that the Mac is normally awake at the chosen hour.
6. Confirm the deferred server rename (after the old skill retires, dual entries until then).
7. GCP project ID `sereniteintelligence` — accept as an invisible residual (recommended for now), or schedule the §7.7 migration.

## 9. Build plan

| Step | Effort | Depends on |
|---|---|---|
| Skill scaffold, config contract + validation, preflight (isolation guard, idempotency, ADC, dev token, required lists) | medium | — |
| Engine: dates + settle, serving guard, GAQL pulls, pacing, gate, buckets + variants, live verification, diff | medium | old skill text as source (corrected) |
| Lead join via Fluent Forms REST + `click_view` corroboration + healthcare minimisation | small–medium | `client-launch` 04 fields (done) |
| Doc writer (markdown → Drive), glossary, first-free counter, per-client ledger with ageing | medium | Drive folder ids |
| `launchd` wrapper + Keychain *Always Allow* + `--health` | small | Mike's decision 5 |
| First run on Eliminatis (`--health` at T+1 after payment verification, Doc at T+7) | — | Joan's verification |
| Serenite migration (config, corrected learnings, one accepted report) | small | decision 4 |
| Server rename with dual entries and reference sweep | small, separate | migration complete |

## 10. Review trail (v1 → v2)

- **Ads API engineer:** serving guard must query `customer.status`/`billing_setup`/`account_budget` and use exact `0.0` vs `0.0999` (§4.3.2); keyword health is on `ad_group_criterion`, not `keyword_view` (§4.3.3); concrete `customer_client` isolation query with three rejection conditions (§4.3.0); `click_view` one-day-per-query / 90-day corroboration (§4.3.4); `change_event` 30-day cap (§4.3.1); PMax fork (§4.3.3); the job must run through the Keychain wrapper (§4.1).
- **Paid-media analyst (vera):** removed the retracted "Serenite captured no gclid" claim (§5.12, §7.1); 48-hour IS settle (§4.3.1); verify-against-live-account, not prior reports (§4.3.8); ledger ageing and cost-since-proposal (§4.3.9); negative variants and level (§4.3.7); services-list lexicon and `withdrawn_recommendations`/`decisions` (§4.2); keyword-level granularity (§4.3.4); GBP taps are not leads (§4.3.3); zero-click term pass (§4.3.7); three-condition budget gate (§4.3.6); budget-by-day, per-campaign pacing (§4.3.5); conversion threshold (§3.6); LSA section (§4.3.10); no Keyword Planner rule (§4.3.7); verdict and "what we need from you" in the Doc (§4.4); descriptive-name and folder-name guards, no default lexicon (§3.2–3.3); `--health` minimum (§6).
- **Systems engineer:** rename only after retirement with dual entries and a reference sweep (§7.4); `launchd` as the scheduling mechanism with Keychain *Always Allow* (§4.1); fresh interpreter per client under vera (§4.5); idempotency guard and `--force` (§4.3.0); `reports_sent` counter (§4.2, §4.3.11); isolation guard as engine step 0 (§4.3.0); effort estimates raised, rename split out (§9).
- **Client communications (sloane):** six-section phone-first Doc with the leads → money → one-thing opener (§4.4); free-report line moved to the close (§4.4.7); glossary table (§4.4); never-in-a-client-Doc list (§3.7); Spanish-term gloss pattern and `campaign_languages` (§4.2, §4.4.3); week-over-week in prose with noise thresholds (§4.4.4).
- **Privacy/compliance:** `LEARNINGS.md` content rule (§3.8); per-client ledgers, never merged (§4.5); healthcare PHI minimisation in persistent files (§4.3.4); offboarding step and token scope (§6); Drive folder sharing rule (§6).
- **Independent verifier (second pass):** all owner requirements PASS except the project-ID residual, now stated and scheduled (§4.1, §7.7, §8.7); 54/54 reviewer findings confirmed present; §3.6/§3.7 reconciled (internal vs Doc language); the Rojas effort figure now shows its computation (§6); §4.3 grouped into Guards / Data / Analysis / Records. §5 kept deliberately as the traceability index Mike asked for.
