---
name: serenite-daily-ads-report
description: Produce the daily Google Ads performance report for Serenite Medical & Spa — traffic quality, wasted spend, impression-share diagnosis, placement-junk detection, and budget pacing against Google's 2x/30.4x limits. Use when asked for a Serenite ads report, a daily/weekly ads check, "how are the ads doing", wasted spend review, search-terms review, or when running on a schedule.
---

# Serenite daily Google Ads report

Read-only analysis. **This skill never mutates the account.** Never pass
`confirm=true` to any tool. Recommend changes; do not apply them.

Account: customer `2169272958`, timezone **America/New_York**, USD.
Tool: `mcp__serenite-ads-write__query` (GAQL, read-only) or `mcp__serenite-ads__search_search`.

## Step 0 — get the date right, or the whole report is wrong

**`LAST_7_DAYS`, `LAST_30_DAYS` and `LAST_14_DAYS` all EXCLUDE today.** A campaign
that started serving today returns zero rows and reads as dead. Always resolve
today's date in `America/New_York` first (`TZ=America/New_York date +%F`) and use
explicit ranges:

```sql
WHERE segments.date BETWEEN '<start>' AND '<today>'
```

`change_event` additionally requires an explicit `LIMIT <= 10000` or it errors.

Also note: `campaign.start_date` is not selectable, and filtering by
`campaign.id` requires `campaign.id` in the SELECT.

## Step 1 — pull the data

Run these. Metrics and certain segments cannot be mixed — `segments.conversion_action_name`
cannot be selected alongside `metrics.clicks` / `cost_micros` / `impressions`, so
keep that in its own query.

1. **Campaign totals by day** — `campaign.id/name/status`,
   `campaign_budget.amount_micros`, `metrics.cost_micros/clicks/impressions/ctr/average_cpc/conversions`
2. **Ad group breakdown** for the reporting window — same metrics, plus
   `ad_group.cpc_bid_micros` and `ad_group.status`
3. **Search terms** — `search_term_view`: `search_term_view.search_term`,
   `segments.keyword.info.text`, `metrics.clicks/cost_micros/impressions`
4. **Impression share** — `metrics.search_impression_share`,
   `search_top_impression_share`, `search_absolute_top_impression_share`,
   `search_rank_lost_impression_share`, `search_budget_lost_impression_share`
5. **Keyword status** — `ad_group_criterion.system_serving_status`,
   `ad_group_criterion.approval_status`, plus metrics; find keywords with zero
   impressions and any `RARELY_SERVED`
6. **Ad policy** — `ad_group_ad.policy_summary.approval_status` /
   `review_status`, and per-asset `policy_summary_info` when an ad reads
   `APPROVED_LIMITED`
7. **Display only** — `detail_placement_view` (`placement`, `placement_type`,
   `display_name`) and `segments.device`. This is where junk hides.

## Step 2 — the analysis that matters

### Budget pacing — the part people get wrong
Google's two hard limits (cite these; verify at
support.google.com/google-ads/answer/10486637 and /1704443):
- **Daily**: up to **2x** the average daily budget on any single day
- **Monthly**: **30.4x** the daily budget; Google covers any overage

So a $25/day budget = **$50 single-day ceiling**, **$760/month**.

**The compression trap:** if the campaign runs an ad schedule, Google still
paces to the full monthly limit across *fewer active days*. Serenite's Search
campaign runs Mon–Fri 8am–7pm, Sat 9am–4pm, **closed Sunday**. A 31-day month
with 5 Sundays = 26 active days, so the real per-active-day target is
`monthly_limit / active_days`, not the nominal daily budget. Always compute and
report this — an "overspend" is usually this, not a fault.

Project month-end: if `run_rate x active_days_remaining` exceeds the monthly
limit, say **when the campaign will go dark**.

### Is budget the constraint?
Compare `search_rank_lost_impression_share` vs `search_budget_lost_impression_share`.
**Rank-lost >> budget-lost means more money buys more of the same mediocre
placement.** Recommend relevance work, not budget increases.

### Traffic quality
Bucket every clicked search term into **high-intent / marginal / waste** with the
cost of each bucket. Report waste as a share of spend. Above ~25% needs action;
name the specific negative keywords.

### Zero-click ad groups
Before concluding "bad ad group", check `search_top_impression_share`. A low
top-IS means impressions rendered *below* the organic results, where CTR is
near-zero by construction. **The fix for research-intent queries is negatives,
not higher bids** — bidding up to win DIY queries is the most expensive mistake
available.

### Display junk detection
High Display CTR is a red flag, not a win. Signals of made-for-advertising
inventory:
- All clicks from one device (typically mobile) while other devices get zero
- Legitimate publishers at 0% CTR while unknown domains show 10-20% CTR
- Domains containing `quiz`, `game`, `play`, `kids`, `/lp/`, lock-screen ad
  platforms (`glance.com`, `mobileposse.com`)

**Critical:** these usually report `placement_type: WEBSITE`, meaning they arrive
via **mobile web, not apps**. A negative `MOBILE_APP_CATEGORY` exclusion cannot
block them, and neither can `adsenseformobileapps.com`. Only placement
exclusions or pausing work. Do not claim the app exclusion protects against this.

## Step 3 — interpretation constraints (do not violate)

- **The only biddable conversion is `7670763779`** (contact form → `/thank-you/`),
  **90-day click-through lookback**, data-driven attribution. Conversions credit
  back to *click date*, so recent days keep rising for weeks. **Never judge
  conversion rate on a short window.**
- **Zero conversions on small click counts is not evidence.** State the
  probability rather than implying failure — at a 7% CVR, zero from 17 clicks has
  ~29% probability.
- **Lead-level attribution does not exist yet.** The Fluent Forms entry captures
  no `gclid`. Until that is fixed, no report can say which lead came from which
  keyword. Say so rather than implying otherwise.
- **No Keyword Planner access.** Never invent search volume, benchmark CTR, or
  industry-average CPC. If you lack the data, say so.
- **"Eligible (limited)" does not stop delivery** — it restricts audience reach.
  Check actual impressions before calling an ad group policy-suppressed.
- The account is **not Healthcare-Provider certified**; see the memory note on
  which keywords Google rejects. Never recommend requesting policy exemptions.
- Distinguish `metrics.conversions` (biddable only) from `metrics.all_conversions`.

## Step 4 — output

Write the report to `~/reports/serenite/YYYY-MM-DD.md` (create dirs as needed)
and print a short summary. Structure:

1. **Headline** — spend, clicks, CTR, avg CPC, conversions, vs. prior period
2. **Verdict** — is this worth the spend? Answer directly, with caveats
3. **Budget pacing** — spent vs. limits, per-active-day target, month-end projection
4. **Ad group table** — impressions, clicks, cost, CTR, IS, top-IS, rank-lost
5. **Search terms** — high-intent / marginal / waste with costs; negatives to add
6. **Display** — placement quality, junk domains found
7. **Anomalies** — zero-click groups, disapproved or limited ads, `RARELY_SERVED`
   keywords, policy changes
8. **Ranked actions** — most valuable first, each with expected effect
9. **What changed since yesterday** — diff against the previous report file if present

Be explicit about what the sample size supports. One day supports conclusions
about **traffic composition and auction position**; it does not support
conclusions about conversion rate, cost per lead, or which ad group is best.
Mark short-window rankings provisional.

## Running on a schedule

The report is read-only, so it is safe to automate. Requirements for any host:
- Google Ads API credentials the `serenite-ads-write` MCP server can use (it
  reads ADC / the same credentials as the local server whose source lives in
  `servers/google-ads-write/` in the `claude-config` repo)
- Network access to `googleads.googleapis.com`
- Somewhere durable to write `~/reports/serenite/`

Quota: the account is Explorer tier, **~2,880 operations/day**. A full report is
roughly 10-20 read operations — negligible. Do not add dry runs; this skill
never mutates.

If a scheduled run finds something urgent — spend above the daily ceiling, an ad
newly DISAPPROVED, a campaign gone dark, or waste above 40% of spend — lead the
report with it rather than burying it in section 7.
