# Google Ads Write MCP Server

Write access to the Google Ads API for Claude Code, with a dry-run confirm gate.
Companion to the official read-only server (`serenite-ads`) — reads live there,
writes live here.

_Built 2026-08-01. Verified against Serenite Medical & Spa (`2169272958`)._

## Why this exists

Google's official MCP server is deliberately read-only. This one wraps the same
`google-ads` Python library (31.2.0) and the same credentials — ADC for identity,
developer token from the Keychain — and exposes mutate operations. The API
version is pinned to **v25** by `API_VERSION` in `gads_write/client.py`, which is
passed to `GoogleAdsClient`; upgrading the library does not move it on its own.

## The safety model

Every mutating tool takes `confirm`, defaulting to **false**:

| `confirm` | What happens |
|---|---|
| `false` (default) | Sent to Google with `validate_only=true`. Fully validated — policy, budgets, referential integrity — **nothing written**. Returns what *would* change. |
| `true` | Actually writes. |

Two further rails:

- **New campaigns are created `PAUSED`.** Enabling is a separate, explicit call,
  because that is the moment money starts moving.
- **Everything for one logical change is a single atomic mutate.** A campaign
  build is ~12 operations chained with temporary resource IDs; they all land or
  none do. No orphaned budgets from a half-failed build.

The dry run is not a local simulation — it is Google validating the real request.
On the first test build it caught two genuine policy violations that a local
check would have missed.

## Tools

30 tools — 22 verified live, plus the 2 Display tools and the 6 Display
targeting tools added 2026-08-02, so far only verified offline.

**Lookup (read-only)**

| Tool | Does |
|---|---|
| `query` | GAQL query — find campaign/ad group/criterion IDs before mutating |
| `find_geo_targets` | Place name → geo target constant ID for location targeting |
| `find_targeting_criteria` | Name → ID for the Display taxonomies: user interests, topics, app categories, user lists, custom audiences, life events |

**Campaigns**

| Tool | Does |
|---|---|
| `create_search_campaign` | Full build: budget, campaign, ad group, RSA, keywords, negatives, geo/language, **extensions, ad schedule, display paths** |
| `set_campaign_status` | ENABLED / PAUSED / REMOVED |
| `update_campaign_budget` | Change daily budget |

**Extensions & targeting settings**

| Tool | Does |
|---|---|
| `add_callout_extensions` | Short trust phrases (max 25 chars, need ≥2 to serve) |
| `add_sitelink_extensions` | Extra links; `{"text","url","description1"?,"description2"?}` |
| `add_structured_snippet` | Header + 3–10 values, e.g. `Services: …` |
| `add_call_extension` | Phone number — dial straight from the ad |
| `add_ad_schedule` | Restrict to staffed hours (account timezone) |
| `set_location_targeting` | `PRESENCE` vs Google's broader `PRESENCE_OR_INTEREST` default |

All of these are also parameters on `create_search_campaign`, folded into the
same atomic mutate — so a campaign is never created half-equipped. Use the
standalone tools to add extensions to a campaign that already exists.

There is no "extension" object in the modern API: each is an `Asset` plus a
`CampaignAsset` link row carrying a `field_type`. Both halves are emitted
together with a temporary asset ID.

**Structure**

| Tool | Does |
|---|---|
| `create_ad_group`, `set_ad_group_status`, `set_ad_group_bid` | Ad group lifecycle |
| `add_keywords`, `add_negative_keywords`, `remove_keywords` | Keyword management |
| `create_responsive_search_ad`, `set_ad_status` | Ad management |

**Assets** — the prerequisite for Display / PMax / Demand Gen

| Tool | Does |
|---|---|
| `upload_image_asset` | Upload an image from a local path or http(s) URL |
| `create_text_asset` | Reusable text asset for PMax asset groups |
| `list_assets` | List existing assets so creative can be reused |

**Display**

| Tool | Does |
|---|---|
| `create_display_campaign` | Full build: budget, DISPLAY campaign, ad group, responsive display ad, geo/language |
| `create_responsive_display_ad` | Add an RDA to a Display ad group that already exists |

A responsive display ad carries no image bytes — it references `Asset`
resources by resource name. Upload with `upload_image_asset` first (or find
existing ones with `list_assets`) and pass the asset IDs. Slot mapping, because
the proto's names do not match the UI's:

| Parameter | Proto field | Ratio |
|---|---|---|
| `marketing_image_asset_ids` | `marketing_images` | 1.91:1 |
| `square_marketing_image_asset_ids` | `square_marketing_images` | 1:1 |
| `logo_asset_ids` | `square_logo_images` | 1:1 |
| `landscape_logo_asset_ids` | `logo_images` | 4:1 |

The unqualified `logo_images` is the **4:1 landscape** logo; the square one is
`square_logo_images`. Text limits — headline 30, long headline 90, description
90, business name 25 — are checked client-side before the request is built,
because one overlong string rejects the whole atomic mutate and the API error
does not say which string.

Images must be uploaded as **bytes** — a campaign cannot reference an image URL.
PNG/JPEG/GIF, 5MB max, both checked before the request is sent.

**Google Drive**: ADC here holds only the `adwords` and `cloud-platform` scopes,
so this server cannot read Drive directly. Pull the file with the Drive MCP
first, save it locally, then pass that path. Adding `drive.readonly` to ADC would
also work but means re-authenticating.

**Video**: referenced by YouTube video ID, never uploaded through this API. Any
video creative must be on YouTube first.

**Display targeting**

`create_display_campaign` applies geo and language only. On the Display Network
that is effectively untargeted — geo narrows *where* the impression lands,
nothing narrows *what page or app*. These six add the rest.

| Tool | Does |
|---|---|
| `exclude_mobile_app_placements` | Campaign-level negative on the app-category tree + `adsenseformobileapps.com` |
| `add_audience_targeting` | Affinity / in-market (`user_interest_ids`), remarketing (`user_list_ids`), `custom_audience_ids` — campaign or ad group |
| `add_topic_targeting` | Content categories on an ad group; `negative=true` excludes |
| `add_placement_targeting` | Managed placements on an ad group; `negative=true` excludes |
| `add_demographic_targeting` | Age / gender / parental status / income; `exclude=true` makes them negative |
| `find_targeting_criteria` | The lookup all of the above depend on |

There is **no `NegativeCampaignCriterion` resource in v25**. A negative is the
same `CampaignCriterion` / `AdGroupCriterion` message with `negative = true`,
and the criterion type is inferred from whichever oneof field is set — `type_`
is never written by these tools. A negative criterion must **not** carry a
`status`; setting one returns
`CampaignCriterionError.CANNOT_SET_STATUS_FOR_EXCLUDED_CRITERIA`. Positives here
are created ENABLED, negatives with no status at all.

Three of the six taxonomies have **no service and no path helper** in v25 —
`UserInterest`, `TopicConstant`, `MobileAppCategoryConstant` (and `LifeEvent`)
are read-only resources reachable only by GAQL. Their resource names are built
by hand:

| Resource | Pattern |
|---|---|
| `UserInterest` | `customers/{cid}/userInterests/{id}` |
| `LifeEvent` | `customers/{cid}/lifeEvents/{id}` |
| `TopicConstant` | `topicConstants/{id}` — global, not customer-scoped |
| `MobileAppCategoryConstant` | `mobileAppCategoryConstants/{id}` — global |

`UserList` and `CustomAudience` do have services, and use their path helpers.

**What `exclude_mobile_app_placements` covers.** Two campaign-level negatives:
`mobileAppCategoryConstants/69500` ("App categories > All Apps" — the UI and
Editor spell this `mobileappcategory::69500`) and the placement
`adsenseformobileapps.com`. It does **not** touch mobile web, in-app webviews
that report as a website domain, apps outside the category tree, YouTube
video/channel inventory, content labels, individual named apps, or anything
outside that one campaign. Performance Max placement exclusions are
account-level only and cannot be set here at all.

`add_demographic_targeting` accepts human-readable values — `25-34`, `65+`,
`female`, `not a parent`, `90+`, `undetermined` — and maps them to v25 enums,
rejecting anything else by name with the valid set. Raw enum names
(`AGE_RANGE_25_34`) also pass through. Note that excluding four of seven age
bands *is* targeting the other three; there is no separate include list. Income
ranges only serve in US/AU/JP/NZ.

`find_targeting_criteria` pulls the whole taxonomy in one GAQL call and filters
client-side, deliberately: `topic_constant.path` is a repeated field so `LIKE`
does not apply to it, and GAQL string matching is case-sensitive.

## Usage

Dry run first — always:

> Build a Search campaign for Serenite, $40/day, targeting Manhattan, keywords
> "med spa new york" and "medical spa manhattan".

Returns `status: validated` with the intended change. Then:

> Looks right, apply it.

Which re-runs with `confirm=true` and returns `status: applied` with resource names.

## Known constraints

**Healthcare keyword policy — mapped 2026-08-01.** Probed 27 med-spa terms
against the live account. 21 passed; 6 were blocked, and **all 6 are
`exemptible`**:

| Blocked | Policy |
|---|---|
| `botox`, `botox near me`, `dermal fillers`, `weight loss injections`, `hormone therapy` | Health in personalized advertising |
| `semaglutide` | Restricted drug terms |

Passing terms include `juvederm`, `dysport`, `kybella`, `sculptra`, `lip filler`,
`coolsculpting`, `morpheus8`, `microneedling`, `hydrafacial`, `chemical peel`,
`prp facial`, `laser hair removal`, `body contouring`, and the generic med-spa
and location terms. Note the quirk: the brand names pass where the generic word
*botox* does not.

Exemptible means no LegitScript certification is needed — the remedy is to
declare the violation knowingly. `create_search_campaign` and `add_keywords`
take `request_policy_exemptions=true`, which retries with
`exempt_policy_violation_keys` attached and reports how many were submitted.

⚠️ Only use it where the advertiser genuinely qualifies to make the claim. It is
a declaration to Google, not a bypass.

**`FieldMask` — fixed 2026-08-02.** Every update tool was dead on arrival with
`Specified type 'FieldMask' does not exist in Google Ads API v25`. Cause:
`client.get_type("FieldMask")`. `FieldMask` is a *protobuf well-known type*, not
a Google Ads type, so it is not in the v25 type registry. The fix is to import it
directly:

```python
from google.protobuf.field_mask_pb2 import FieldMask
client.copy_from(op.campaign_operation.update_mask, FieldMask(paths=["status"]))
```

Creates were unaffected throughout — they carry no update mask — which is why the
account looked healthy while every update failed.

**Operations quota.** The developer token is Explorer tier: 2,880 operations/day
against production. A campaign build is ~12, or ~60 with full extensions. Basic access (15,000/day) is a
5-day review in the API Center if that becomes tight.

**Display is code-complete but never validated live.** The Display tools —
campaign/ad build *and* all six targeting tools — were written offline against
the v25 protos and proved out by building the mutate request objects locally
and round-tripping them through protobuf serialization. **No dry run has been
sent to Google.** The first real call should be a `confirm=false` dry run.
What to watch, most likely to fail first:

1. **`find_targeting_criteria`** — the GAQL selects are unverified. If a field
   is not selectable the error names it; `topic` and `user_list` have a narrower
   fallback select, the other four do not. Also unverified: whether
   `topic_constant` / `user_interest` / `mobile_app_category_constant` can be
   queried with no `WHERE` clause at all.
2. **`mobileAppCategoryConstants/69500`.** The ID comes from the UI/Editor
   spelling `mobileappcategory::69500`, not from a live query. A wrong ID
   surfaces as `CriterionError.INVALID_MOBILE_APP_CATEGORY`. Confirm it first
   with `find_targeting_criteria(kind="mobile_app_category", query="all apps")`.
3. **`adsenseformobileapps.com`.** Google has deprecated this placement more
   than once. If it is rejected
   (`CriterionError.PLACEMENT_IS_NOT_AVAILABLE_FOR_TARGETING_OR_EXCLUSION`),
   re-run with `exclude_adsense_for_mobile_apps=false` — the category exclusion
   is the load-bearing half.
4. **Campaign `network_settings`** (search off, content on) and missing-asset
   policy errors on the RDA, from the original Display build.
5. **`CANNOT_TARGET_AND_EXCLUDE`** if a criterion is added that already exists
   with the opposite sign. These tools only ever create; they never read the
   existing criteria first.

## Not yet built

Performance Max and Demand Gen. Both depend on the same asset pipeline Display
uses, plus more:

1. Performance Max (asset groups, listing groups, audience signals) — the largest
2. Demand Gen (needs video assets on YouTube)

## Rebuilding

```bash
cd /Users/mike/projects/mcp/google-ads-write
python3 -m venv .venv && ./.venv/bin/pip install -e .
```

Registered as `serenite-ads-write` at user scope, launched by
`../google-ads-write.sh sereniteintelligence`.
