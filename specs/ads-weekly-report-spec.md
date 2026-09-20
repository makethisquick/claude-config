# Google Ads weekly client report — studio skill spec

*MakeThisQuick · draft v1 · 2026-09-20 · author: Claude, for Mike's review*

## 1. The problem this fixes

The studio's Google Ads reporting knowledge lives in a skill called `serenite-daily-ads-report`, backed by MCP servers called `serenite-ads` and `serenite-ads-write`. None of that is Serenite-specific. The servers take the studio GCP project as their only argument and reach every account under the MakeThisQuick manager account (MCC `101-894-5450`) with one credential; the skill's logic — pacing maths, impression-share diagnosis, search-term bucketing, junk-placement detection, the "don't judge conversion rate on a short window" rules — applies to any account. Only the constants (customer id, timezone, the one biddable conversion, the policy quirks) are Serenite's.

The naming has already caused real confusion: the Eliminatis weekly report was described as running on "Serenite's engine", and the cross-client isolation rule (never let one client's tooling touch another's data) is harder to keep when the tooling carries a client's name. This spec defines the replacement: one studio skill, **`ads-weekly-report`**, that runs against any client the studio has onboarded, and a rename of the two MCP servers to **`studio-ads`** / **`studio-ads-write`**.

## 2. Where it sits in the pipeline

```
wp-mcp-onboard  →  client-launch (00–07)  →  ads-weekly-report (this)
  site + MCP         SEO, forms, attribution,    T+1 health check
  connector          GA4/GSC, Ads account,       weekly client Google Doc
                     draft → approval → build    internal actions ledger
```

The report never runs before `client-launch` phase 7c has enabled campaigns — there is nothing to report on and the first-report-is-free clock has not started. Everything the report needs to know about a client is already in that client's `launch.json`; this skill adds one `report` block to that file and reads nothing else.

## 3. Principles (non-negotiable)

1. **Read-only.** The report never mutates an account. Recommendations go into an actions ledger and are applied only after Mike says go, through the write server's dry-run → confirm flow, in a separate step.
2. **One client per run, addressed by config.** The customer id, timezone, currency, campaigns, forms and Drive folder all come from `launch.json`. No client identifiers in code, skill text, server names or script names.
3. **Zero cross-client contact.** A run for client A opens client A's config and client A's account. It does not list other accounts, does not write to another client's folder, and refuses to start if the config's `customer_id` is not a child of the MCC.
4. **Client-facing output is a Google Doc in prose** (Mike's report-format rule). Every Ads term is glossed in plain language the first time it appears. Numbers live in an appendix table. A local `.md` + `.json` is always written first — it is the durable record and the diff source for "what changed since last week".
5. **First report free, then maintenance.** The first Doc carries a one-line cover note; from the second on it is part of paid monthly maintenance. This is a commercial rule, so it is enforced by the script (it counts prior reports for the client).
6. **Say what the sample supports.** One week supports conclusions about traffic composition and auction position; it does not support cost-per-lead rankings between ad groups. The report marks those provisional rather than implying certainty.

## 4. Architecture

### 4.1 Credentials and reach
- Identity: the studio's Application Default Credentials (OAuth app **MakeThisQuick-AdsAutomation**, GCP project `sereniteintelligence` — display name QuickIntelligence — consent screen *In production* so tokens do not expire every 7 days).
- Authority: the studio developer token (macOS Keychain `google-ads-dev-token`), now at **Basic** access (15,000 operations/day on production accounts).
- Scope: `login-customer-id` = the MCC. Every client account created through `client-launch` 07a is a child of the MCC; Serenite (`216-927-2958`) is already a child. One credential, every client.
- The two MCP servers stay for interactive work; the scheduled report calls the `google-ads` Python library directly through `gads_write.client.get_client()` (same auth), because a scheduled job should not depend on an MCP session being connected — the 09-16 "reconnect before the report" ritual is exactly the failure this removes.

### 4.2 Config contract — additions to `launch.json`
```json
"report": {
  "cadence": "weekly",
  "weekday": "mon",
  "window_days": 7,
  "drive_folder_id": "<client folder in Mike's Drive>",
  "client_first_name": "Joan",
  "language": "en",
  "first_report_free": true,
  "lead_join": { "forms": [3, 4], "gclid_field": "gclid", "utm_fields": ["utm_campaign","utm_adgroup","utm_term","lang"] },
  "biddable_conversions": ["<conversion_action_id>"],
  "search_term_lexicon": { "high_intent": ["exterminator","near me","emergency", "…"], "waste": ["diy","jobs","how to","…"] },
  "never_negative": ["facial","hydrafacial"],
  "policy_notes": "uncertified healthcare — safe-proxy wording; never request exemptions",
  "budget_raise_gate": true
}
```
`ads.customer_id`, `ads.mcc_customer_id`, `ads.time_zone`, `ads.campaigns[]`, `thank_you`, `forms`, and `brand` are already there from `client-launch`.

### 4.3 The engine — `08_weekly_report.py`
One Python script in the skill, flags `--health` (T+1, terminal only), `--md` (local files only), `--doc` (also publish the Google Doc). Steps:

1. **Dates.** Resolve *today* in the client's timezone; use explicit `BETWEEN` ranges. `LAST_7_DAYS` excludes today and hides a campaign that started today — the Serenite skill's first lesson.
2. **Serving guard.** If every campaign has zero impressions for the window: do not write a performance report. Write the *not serving* note instead, listing the account-level checks (payment verification banner, policy suspension, billing) — the Eliminatis 09-18→20 lesson, where every API status was green and the account had never entered an auction.
3. **Pulls (read-only GAQL, ~15 operations):** campaign × day; ad group; search terms with keyword; impression share incl. rank-lost and budget-lost; keyword health (`RARELY_SERVED`, quality score, zero-impression); ad policy (`approval_status`, `review_status`, per-asset `policy_summary_info` on `APPROVED_LIMITED`); conversions by action in its own query (segments cannot mix with cost metrics); change history with an explicit bounded date range and `LIMIT`; Display placements + device only if a Display campaign exists.
4. **Lead join.** Pull Fluent Forms entries for the window (`fluentform/v1`, forms from config), read the hidden attribution fields written by `client-launch` 04 (gclid, UTM set, landing page, language), match to ad group / search term. Report leads as people, not as a metric: *"3 form leads: 2 from 'bed bug exterminator nj', 1 from the Spanish general group."* Phone-tap conversions are counted but cannot be joined to a person — the report says so. (Serenite could never do this because its form captured no gclid; every `client-launch` site captures it from day one.)
5. **Pacing.** Google's limits: 2× daily budget on any day, 30.4× per month. If the campaign has an ad schedule, compute the per-*active*-day target (`monthly_limit / active_days`) — the compression trap that makes normal spend look like overspend. Project month-end and say when the campaign will go dark if the run-rate exceeds the limit.
6. **Budget-raise gate.** Rank-lost vs budget-lost impression share, 48-hour-settled. Budget-lost > rank-lost means money is the constraint and a raise is justified; rank-lost ≫ budget-lost means a raise buys more of the same mediocre placement — recommend relevance work instead. Reported explicitly every week (Mike's standing Serenite goal), never buried.
7. **Search-term buckets.** High-intent / marginal / waste with the cost of each, using the client lexicon; waste above ~25% of spend names specific negatives. Zero-click ad groups are checked against `search_top_impression_share` before being called bad — ads rendered below the organic results have near-zero CTR by construction, and the fix for research-intent queries is negatives, not bids. Terms in `never_negative` are never proposed.
8. **Diff.** Load last week's `.json`, compute deltas and the "what changed" section (changes applied, budget moves, new negatives, ads approved/disapproved).
9. **Outputs.** `~/projects/<Client>/reports/ads-weekly-<date>.md` and `.json`; a Google Doc in the client's Drive folder from config (`create_file`, `text/markdown` → native Doc; content cannot be patched afterwards, so the body is final in one call); a terminal summary; and an **actions ledger** entry (`reports/actions-ledger.md`) listing recommended changes with expected effect, status *proposed* until applied.

### 4.4 The Doc — structure
1. Cover line (first report: "this one is on us; from next week it is part of your monthly maintenance").
2. What ran and what it cost (spend, clicks, average cost per click — glossed).
3. What people searched for, and what we blocked.
4. Leads, and where each came from.
5. What we changed this week.
6. What we recommend (budget gate answer, negatives, copy) — with the one-sentence reason for each.
7. Next week.
8. Appendix: the numbers table.

Urgent findings — spend above the daily ceiling, a newly disapproved ad, a campaign gone dark, waste above 40% — lead the Doc rather than sit in a section.

### 4.5 Who runs it
**vera** (paid-media analyst agent) owns the recurring run and the actions ledger across clients; **sloane** shapes the client Doc when the prose needs more than the template gives. Both are studio agents, not client agents — a run is parameterised by which `launch.json` it is handed.

## 5. Learnings carried in from Serenite (each one is a rule above)

| # | What happened on Serenite | Rule in this skill |
|---|---|---|
| 1 | `LAST_7_DAYS` excludes today; a campaign that started today read as dead | Explicit date ranges resolved in the client timezone (§4.3.1) |
| 2 | 15 days of no reporting when ADC tokens expired every 7 days (consent screen in Testing); "This app is blocked" on gcloud's shared client | Studio OAuth app *In production*, own Desktop client; preflight checks ADC scopes every run |
| 3 | `get_client()` caches the client; re-auth on disk does nothing until the MCP server restarts — "re-auth first, reconnect second" | Scheduled report runs in a fresh process, not through an MCP session |
| 4 | Ad-schedule compression made normal spend look like overspend | Per-active-day pacing target (§4.3.5) |
| 5 | Mike's standing question: *when* to raise the Search budget | Rank-lost vs budget-lost gate reported every week (§4.3.6) |
| 6 | Zero-click ad groups were rendering below organic; bidding up to win DIY queries is the most expensive mistake available | Top-IS check before judging; negatives over bids (§4.3.7) |
| 7 | Display CTR of 10–20% from lock-screen/quiz domains reporting as `WEBSITE`; app-category exclusions could not block them | Placement junk detection only when Display exists; never claim the app exclusion protects (§4.3.3) |
| 8 | Conversions credit back to click date; zero conversions on 17 clicks is ~29% likely at a 7% CVR | Never judge conversion rate on a short window; state the probability (§3.6) |
| 9 | `WEBPAGE_CODELESS` on a thank-you URL is fragile for AJAX forms; a `generate_lead` fired on page *load*; enhanced conversions collected nothing | `client-launch` 05 fires the conversion from the form success redirect and captures gclid; the report distinguishes `conversions` (biddable) from `all_conversions` |
| 10 | Lead-level attribution did not exist — no gclid in the form | Lead join is a first-class section, on every `client-launch` site (§4.3.4) |
| 11 | Conversion actions could not be mutated via API (`MUTATE_NOT_ALLOWED` on Google-created types) | Report reads goal-level `biddable` and `include_in_conversions_metric`; never infers from `primary_for_goal`; changes are flagged as UI work |
| 12 | Healthcare policy: many "safe-proxy" keywords rejected; "Eligible (limited)" does *not* stop delivery; certification was a wrong early reading | `policy_notes` in config; check actual impressions before calling an ad group suppressed; never recommend exemptions |
| 13 | Mike's rulings: `facial`/`hydrafacial` never negatived, Display stays at $5 as brand awareness, "do not raise Search budget", fillers offered-but-never-advertised | `never_negative` and decision notes in config so a new session cannot re-propose a settled call |
| 14 | Reports as `.md` on the laptop could not be shared; analyst-table prose did not read as human | Google Doc in prose, glossed terms, `.md` kept as the record (§3.4) |
| 15 | Drive `update_file` is metadata-only; content cannot be patched; `fileSize: 1` is not a failure | One-shot body; companion docs for follow-ups; never recreate (§4.3.9) |
| 16 | Duplicate campaigns from re-running `create_search_campaign`; a campaign flipped to ENABLED with no change-log entry | The report is read-only; change history is bounded and treated as unreliable for audit |
| 17 | HIPAA: offline conversion upload and LSA "ask for review" both disclose "sought care" signals without a BAA | `policy_notes` carries compliance posture; the report never proposes offline uploads or review requests for healthcare clients |
| 18 | Five reads were cheaper than spawning an agent for a 48-hour check-in | `--health` mode is a direct script, no agent |
| 19 | "Setup in progress" Ads accounts can hold a live LSA campaign; the API cannot cancel accounts | Preflight refuses any `customer_id` that is not an MCC child; never audits or touches sibling accounts |
| 20 | Explorer-tier token blocked account creation; brand verification failed on a homepage privacy URL | Now Basic; the OAuth app's privacy/ToS links point at the real policy pages (rewritten 2026-09-18) |

## 6. Scaling — "any client, even Rojas"

**What a new client needs before the first report can run:**
1. `wp-mcp-onboard` — site on the studio WPMU DEV host, Elementor MCP connector.
2. `client-launch` 00–06 — SEO, Fluent Forms with the 13 attribution hidden fields, thank-you pages firing the conversion, GA4 + GSC (studio-owned).
3. `client-launch` 07a — Ads account under the MCC (now one API call), 07b — the client-approval Doc, **client approval + client payment method + Google's payment verification**, 07c — build, enable, accept Call & Messaging terms, link the client's *own* Business Profile.
4. `report` block in `launch.json`; a client folder in Mike's Drive.
5. T+1 `--health`, T+3/4 negatives pass, T+7 first Doc.

For **Rojas** specifically today: the site is on staging with unratified prices and no Ads account; there is no `launch.json`. Steps 1–2 are the launch itself; step 3 needs an Ads budget decision and the client's card; the report is the last thing, not the next thing. Agent effort once the client says go: roughly half a day of scripted work spread across the client's approval gates (draft → approval → payment → verification), which are the long pole.

**Capacity:** a report is ~15–20 read operations; at Basic access (15,000/day) that is several hundred clients per day before quota matters. Serenite's daily cadence is the exception; weekly is the default tier, with `cadence` per client in config. One scheduler entry per client, each a fresh process — no shared state between clients, by design.

**Drive layout:** one folder per client in Mike's Drive (Serenite Stuff, Alerte, … already exist); the folder id lives in config. Studio-level documents (this spec) live in **MTQ / Studio Specs**, never in a client folder.

**Skill self-improvement:** like `client-launch`, the skill reads and appends its own `LEARNINGS.md` on every run, and is committed to `github.com/makethisquick/claude-config`.

## 7. Migration from `serenite-daily-ads-report`

1. Create `ads-weekly-report` with the engine above; keep the Serenite skill in place until the new one has produced one Serenite report that Mike accepts.
2. Serenite's constants move into a `report` block in a new `~/projects/Serenite/launch.json` (customer id, timezone, biddable conversion `7670763779`, `never_negative`, `policy_notes`, the Display campaign, the ad schedule, cadence daily/weekly as Mike chooses).
3. Rename MCP servers `serenite-ads` → `studio-ads`, `serenite-ads-write` → `studio-ads-write` in `~/.claude.json` (same launcher, same project argument). Memory files and the account log keep their Serenite names — they are client records, not tooling.
4. Retire `serenite-daily-ads-report`; its SKILL.md text becomes the first `LEARNINGS.md` of the new skill.
5. Update memory: `report-format-google-doc`, `serenite-ads-api-auth` (already marked studio-wide), `wp-mcp-onboarding-automation`.

## 8. Decisions for Mike

1. Doc folder per client — create "Eliminatis" in Drive now (none exists); confirm the folder-per-client convention.
2. Client tone — plain-English body, numbers in an appendix (recommended), or numbers up top.
3. Week-over-week deltas from week 2 (recommended; needs the local history) or standalone reports.
4. Serenite cadence after migration — stay daily, or move to weekly like everyone else with a `--health` mid-week.
5. Server rename now (one edit in `~/.claude.json`, reconnect once) or at migration time.
6. Who runs the weekly job — vera on a cron per client (recommended), or Mike triggers manually.

## 9. Build plan

| Step | Effort | Depends on |
|---|---|---|
| Skill scaffold, config contract, preflight (MCC-child check, ADC, dev token, config) | small | — |
| Engine: dates, serving guard, GAQL pulls, pacing, gate, buckets, diff | medium | Serenite skill text as the source |
| Lead join via Fluent Forms REST | small | `client-launch` 04 fields (done) |
| Doc writer (markdown → Drive) + first-free logic + actions ledger | small | Drive folder ids |
| First run on Eliminatis (`--health` at T+1 after payment verification, Doc at T+7) | — | Joan's verification |
| Serenite migration + server rename | small | Mike's decisions 4–5 |
