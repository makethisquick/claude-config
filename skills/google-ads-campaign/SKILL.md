---
name: google-ads-campaign
description: Build, validate, and launch Google Ads Search campaigns through the serenite-ads-write MCP server. Covers the dry-run/confirm safety gate, the pre-build checklist (landing page, geo target IDs, character limits), the atomic create_search_campaign call with extensions, post-apply verification queries, and the separate decision to enable spending. Use when asked to create/build/launch a Google Ads campaign, add keywords or negatives, attach sitelinks/callouts/call extensions/ad schedules, change budgets or bids, or enable/pause a campaign.
---

# Google Ads campaign builds

Write operations go through the `serenite-ads-write` MCP server (22 tools, Google
Ads API v25). Reads can go through either it or the read-only `serenite-ads`
server. Source and full server notes: `/Users/mike/projects/mcp/google-ads-write/`.

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
