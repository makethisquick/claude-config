---
name: google-ads-campaign
description: Build, validate, and launch Google Ads Search campaigns through the serenite-ads-write MCP server. Covers the dry-run/confirm safety gate, the pre-build checklist (landing page, geo target IDs, character limits), the atomic create_search_campaign call with extensions, post-apply verification queries, and the separate decision to enable spending. Use when asked to create/build/launch a Google Ads campaign, add keywords or negatives, attach sitelinks/callouts/call extensions/ad schedules, change budgets, bids or bidding strategy, or enable/pause a campaign.
---

# Google Ads campaign builds

Write operations go through the `serenite-ads-write` MCP server (35 tools, Google
Ads API v25). Reads can go through either it or the read-only `serenite-ads`
server. Source and full server notes: `servers/google-ads-write/` in the
`claude-config` repo (`~/projects/claude-config` on macOS,
`%USERPROFILE%\projects\claude-config` on Windows).

## The safety sequence — never skip a step

1. **Dry run.** Every mutating tool defaults to `confirm=false`, which sends the
   real request to Google with `validate_only=true`. Nothing is written; Google
   validates policy, budgets, and referential integrity for real. This is not a
   local simulation — it catches genuine policy violations.
2. **Show the user** the returned `intended` block and `operation_count`. Wait for
   agreement.
3. **Apply** by re-running the identical call with `confirm=true`.
4. **Verify** with GAQL queries against the live account (below).
5. **Enabling is a separate decision.** New campaigns are created `PAUSED`.
   `set_campaign_status(status="ENABLED")` is the moment money starts moving —
   it needs its own dry run and its own explicit approval, never bundled into
   the build.

Never pass `confirm=true` on the first call for a change. Never pass it to save
a round trip. If the dry run's numbers differ from what you predicted, stop and
report the discrepancy instead of applying.

## Before building

- **Confirm the account.** `query` for existing campaigns first. Check the
  channel type of anything already there so you don't confuse a DISPLAY campaign
  with a Search one, and confirm the campaign you're about to create doesn't
  already exist (a re-run after a crash is the common case).
- **Validate the landing page.** Fetch the final URL and confirm HTTP 200 with no
  redirects, and that the on-page wording matches the ad copy. A redirect or a
  claim mismatch is a policy risk.
- **Resolve geo targets** with `find_geo_targets` — never guess an ID. Prefer a
  few counties over a long list of cities when the counties cover them.
- **Set `location_presence_only=true`** unless there's a reason not to. Google's
  default (`PRESENCE_OR_INTEREST`) serves to people merely *interested in* the
  area, which wastes local budget.
- **`search_partners=false`** for a first build. Add partners later with data.
- **Add UTMs** to the final URL and to every sitelink, with distinct
  `utm_content` per link so clicks are attributable.

## Field limits — validate before sending

| Field | Limit |
|---|---|
| Headline | 30 chars (need 3–15; supply 15) |
| Description | 90 chars (need 2–4; supply 4) |
| `path1` / `path2` | 15 chars each |
| Callout | 25 chars (≥2 required to serve; supply 4–6) |
| Sitelink link text | 25 chars |
| Sitelink description lines | 35 chars each |
| Structured snippet value | 25 chars (3–10 values) |

Count them yourself before the dry run. Google rejects the whole atomic mutate
on one overlong string.

## The build

Use **one** `create_search_campaign` call. Budget, campaign, ad group, RSA,
keywords, negatives, geo/language, callouts, sitelinks, structured snippet, call
extension, ad schedule, and display paths all fold into a single atomic mutate —
they all land or none do, so there are no orphaned budgets from a half-failed
build. A full build is ~78 operations.

Only use the standalone extension tools (`add_callout_extensions`,
`add_sitelink_extensions`, `add_structured_snippet`, `add_call_extension`,
`add_ad_schedule`, `set_location_targeting`) to equip a campaign that *already*
exists.

Reference payload from a real applied build:
`reference/serenite-lifestyle-wellness.json`.

## Changing the bidding strategy

`set_campaign_bidding_strategy` (added 2026-10-02) switches a live campaign
between `MANUAL_CPC`, `MAXIMIZE_CLICKS`, `MAXIMIZE_CONVERSIONS`,
`MAXIMIZE_CONVERSION_VALUE` and `TARGET_IMPRESSION_SHARE`. Treat it like
enabling a campaign: its own dry run, its own approval. It changes how every
auction is bid, and the effect shows up as CPC within a day.

**Why it exists.** On 2026-09-24 a Google recommendation accepted in the Ads
mobile app moved two live Serenite campaigns from Manual CPC to Maximize
conversions. There was no API tool to undo it, so the revert needed a browser
session — on a page where screenshots are blocked and Material components ignore
synthetic clicks. Measured damage over the seven days it ran: average CPC
$2.73 → $4.67 (+71%), waste 16.4% → 29.1% of spend, 0.00 conversions attributed
to the strategy. Never leave this to the UI again.

**When an automated strategy is the wrong answer.** Maximize conversions needs
conversion volume to learn from — Google's own guidance is ~30/month, and this
account produces a handful per quarter. Below that it is bidding on noise, and it
will spend the whole budget proving it. Default to `MANUAL_CPC` on low-volume
accounts and say so when a recommendation argues otherwise.

**Things the API will not forgive** (all established by dry run, so don't
rediscover them):

- `campaign.bidding_strategy_type` is **output-only**. The strategy is declared
  by which oneof field is set, never by naming the type.
- Update masks must name **leaf** fields. Masking `manual_cpc` fails with
  `FIELD_HAS_SUBFIELDS`.
- Standalone `TARGET_CPA` / `TARGET_ROAS` no longer exist at campaign level;
  Google folded them into `MAXIMIZE_CONVERSIONS(target_cpa)` and
  `MAXIMIZE_CONVERSION_VALUE(target_roas)`. The tool accepts the old names as
  aliases and routes them, because the Ads UI still shows them.
- Bid ceilings are accepted on `MAXIMIZE_CLICKS` and `TARGET_IMPRESSION_SHARE`
  (required on both — a zero ceiling returns "Too low.") and **refused** on the
  Maximize\* strategies, where they are portfolio-only.
- Enhanced CPC cannot be turned back on — Google returns "The operation is not
  allowed for the given context." `MANUAL_CPC` therefore always sets it off, and
  that is a one-way door.

Currency parameters are in dollars, not micros. `target_roas` (e.g. `4.0`) and
`impression_share_target` (e.g. `0.65`) are ratios.

**Verify after switching to MANUAL_CPC.** The per-ad-group `cpc_bid_micros`
survive a spell under an automated strategy and govern auctions again
immediately, but confirm rather than assume:

```
SELECT ad_group.name, ad_group.cpc_bid_micros, ad_group.effective_cpc_bid_micros
FROM ad_group WHERE campaign.id = <id> AND ad_group.status = 'ENABLED'
```

`effective_cpc_bid_micros` should equal `cpc_bid_micros` on every row. If it
doesn't, the switch didn't take.

## Verify after applying

The apply response lists created resource names, but query the account to
confirm what actually landed:

```
SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type,
       campaign.bidding_strategy_type, campaign_budget.amount_micros,
       campaign.network_settings.target_google_search,
       campaign.network_settings.target_search_network,
       campaign.geo_target_type_setting.positive_geo_target_type
FROM campaign WHERE campaign.id = <id>
```

```
SELECT ad_group_criterion.type, ad_group_criterion.negative,
       ad_group_criterion.keyword.match_type
FROM ad_group_criterion WHERE campaign.id = <id>
```

```
SELECT campaign.id, campaign_asset.field_type, campaign_asset.status
FROM campaign_asset WHERE campaign.id = <id>
```

Check: status `PAUSED`, `target_google_search: true` (this is Google Search;
`target_search_network` is the *partner* network and should be false),
`positive_geo_target_type: PRESENCE`, positive keywords at the intended match
type, negatives all `negative: true`, and one campaign_asset row per extension.

GAQL gotchas: every query needs `campaign.id` in the SELECT when filtering by
it, and `campaign.start_date` is not selectable in v25.

A freshly created ad returns `approval_status: UNKNOWN` and
`ad_strength: PENDING`. That's normal — review takes time. Re-query later rather
than treating it as a failure.

## Constraints to respect

- **No Keyword Planner access.** These tools expose no search-volume data. Do not
  invent volume, CTR, or cost-per-click estimates. Say the data isn't available.
- **Operations quota**: Explorer tier, 2,880 ops/day. A full build is ~78, and
  dry runs count.
- **Healthcare policy.** Some med-spa terms are blocked but *exemptible* —
  `botox`, `botox near me`, `dermal fillers`, `weight loss injections`,
  `hormone therapy` (Health in personalized advertising) and `semaglutide`
  (restricted drug terms). Brand names like `juvederm`, `dysport`, `kybella`,
  `sculptra` pass where the generic word does not.
  `request_policy_exemptions=true` retries with the violation declared. That is
  a declaration to Google that the advertiser qualifies, not a bypass — only use
  it when they genuinely do, and tell the user you're doing it.
- **Ad Strength is not an auction ranking factor.** A single-service ad group
  with tight message match will often read *Good*, not *Excellent*, because
  headlines share a content word. That's an acceptable trade; don't dilute copy
  chasing the label.
- **Uncertified accounts** (no LegitScript / Healthcare Provider certification)
  must keep safe-proxy wording — describe sessions and services, not treatment
  outcomes or cures.
