# Handoff (updated 2026-08-02)

## State — both remaining items are done

Server code done and verified live, **22 tools**. The Lifestyle Wellness campaign
is **applied and PAUSED**. The `google-ads-campaign` skill is written.

**Added since (2026-08-02, later): Display — now 24 tools.**
`gads_write/tools/display.py` adds `create_display_campaign` and
`create_responsive_display_ad`. Written and checked **offline only** — the
package imports, both tools register, and the mutate requests build (7
operations for a full Display build with 2 geos + 1 language). **No dry run has
been sent to Google.** See "Display is code-complete but never validated live"
in the README for what to watch on the first `confirm=false` call.

**Added 2026-08-02 (later still): Display targeting — now 30 tools.**
`gads_write/tools/targeting.py` adds `exclude_mobile_app_placements`,
`add_audience_targeting`, `add_topic_targeting`, `add_placement_targeting`,
`add_demographic_targeting`; `tools/lookup.py` adds `find_targeting_criteria`.

Why: `create_display_campaign` applied geo + language only, which on Display is
effectively untargeted, and the account's **1.38% Display CTR** (3-10x normal)
is the signature of mobile-app inventory and accidental clicks. Existing DISPLAY
campaign `23723515346` is the obvious first target.

Offline-only again. Harness:
`scratchpad/offline_check_targeting.py` — 30 tools enumerate, every tool builds
a `validate_only=True` request with the expected operation count and criterion
fields, bad input is rejected by name, and one request round-trips through
protobuf serialization. **Nothing has been sent to Google, not even a dry run.**

What v25 actually required, vs. what was assumed going in:

- **No `NegativeCampaignCriterion` resource.** A negative is `CampaignCriterion`
  / `AdGroupCriterion` with `negative = true`. Same as `add_negative_keywords`.
- **Criterion `type_` is never set** — inferred from whichever oneof is
  populated. Confirmed on the wire: a mobile-app-category exclusion serializes
  as exactly `{campaign, negative, mobile_app_category}`.
- **Negatives must not carry a `status`.** `CampaignCriterionError
  .CANNOT_SET_STATUS_FOR_EXCLUDED_CRITERIA` exists in v25. Positives are ENABLED,
  negatives have no status field on the wire.
- **`UserInterest`, `TopicConstant`, `MobileAppCategoryConstant`, `LifeEvent`
  have no service in v25** — `client.get_service(...)` raises. Resource names
  are string-built. `UserList` and `CustomAudience` do have services.
- Topic and mobile-app-category constants are **global** (`topicConstants/{id}`),
  user interests and life events are **customer-scoped**
  (`customers/{cid}/userInterests/{id}`).
- No update mask anywhere in this module — every operation is a create.

Ranked by how likely it is to break on the first real dry run, see the numbered
list in the README's "Display is code-complete" section. Short version:
`find_targeting_criteria`'s GAQL selects first, then the `69500` app-category ID,
then `adsenseformobileapps.com`.

Loose ends deliberately left:

- `create_display_campaign` was **not** extended to fold targeting into its
  atomic build. Targeting is applied as separate calls after the campaign
  exists. Doing it inline needs temp-ID chaining through the criterion ops.
- No read-before-write. Re-running any of these adds duplicate criteria, or
  trips `CANNOT_TARGET_AND_EXCLUDE` against an opposite-signed existing one.
- No removal tools — nothing here undoes a criterion. Use `query` to find
  criterion IDs, then remove them in the UI.
- No `combined_audience`, `custom_intent`, `content_label`, `youtube_video` /
  `youtube_channel`, `device`, or shared placement-exclusion-list support.
- No `bid_modifier` on any criterion.
- `find_targeting_criteria` scans up to 20,000 rows and filters in Python; it
  has never been run against a real taxonomy, so the row counts are guesses.
Resolved 2026-08-02 — `client.py` used to declare a dead `API_VERSION = "v24"`
that was never passed to `GoogleAdsClient`. The constant is now `"v25"` and is
passed as `version=API_VERSION`, so the API version is pinned rather than
inherited from whatever `google-ads` currently defaults to. Bumping the API
version is now a one-line, deliberate edit in `client.py`.

### Applied 2026-08-02 — account `2169272958`

| Resource | ID |
|---|---|
| Campaign | `24090635268` (PAUSED) |
| Campaign budget | `15759663590` |
| Ad group | `199091955059` |
| Ad | `819612274949` |

Dry run and apply both reported **78 operations, 0 policy exemptions**.

Verified live after apply: SEARCH channel, PAUSED, MANUAL_CPC, $15.00/day,
ad group cpc bid $3.50, `target_google_search: true`, search partners **false**,
`positive_geo_target_type: PRESENCE`, 40 ad group criteria (10 PHRASE positive +
30 BROAD negatives), 12 campaign assets (6 CALLOUT, 4 SITELINK, 1
STRUCTURED_SNIPPET, 1 CALL) all ENABLED.

The ad reads `approval_status: UNKNOWN` / `ad_strength: PENDING` — normal for a
just-created ad awaiting review. Re-query later.

Pre-existing campaign `23723515346` is DISPLAY, untouched.

## The one open decision

**The campaign has never been enabled.** `set_campaign_status(campaign_id=
"24090635268", status="ENABLED")` is the moment money starts moving — it needs
its own dry run and its own explicit approval. Do not bundle it into other work.

Also still open: no conversion tracking on the search side, which is why bidding
is MANUAL_CPC rather than Maximize Conversions. Revisit once there's click data.

**Do not re-run `create_search_campaign` for Lifestyle Wellness** — it does not
detect duplicates and would build a second identical campaign.

## The skill

`~/.claude/skills/google-ads-campaign/`

- `SKILL.md` — dry-run/confirm sequence, pre-build checklist, field limits,
  post-apply verification GAQL (incl. the v25 gotchas: `campaign.start_date` is
  not selectable; filtering by `campaign.id` requires it in the SELECT), quota
  and healthcare-policy constraints.
- `reference/serenite-lifestyle-wellness.json` — the exact applied payload plus
  the applied resource IDs and the reasoning behind each non-obvious choice.
  This is the durable copy; the original was only ever in a session scratchpad.

## Decisions already made — do not re-litigate

- **Manual CPC $3.50**, not the PDF's Maximize Conversions. No search-side
  conversion history; a hard ceiling while we learn real CPCs.
- **3 geo targets** (`1027258` Prince William County, `9059781` Stafford County,
  `1027194` Lorton), not the PDF's 15 cities. Covers nearly all of them.
- **Strategy doc beats the PDF** on wording: "Sessions" not "Therapy", drop
  "healing therapy", drop Medical Weight Loss (off-topic for this page).
- PDF keyword list had `medical spa nj` / `staten island` / `brooklyn` —
  wrong account, dropped. PDF's single description is 117 chars (limit 90).
- Landing page already compliant: title says "Sessions", has disclaimer,
  no Botox/Bong.

## Known limits

- No Keyword Planner access via these tools — **no search-volume data**. Do not
  invent volume or CTR estimates.
- Ad Strength will likely read *Good*, not *Excellent* (19 headline pairs share
  a content word). Deliberate: single-service ad group, message match matters
  more. Ad Strength is not an auction ranking factor.
- Explorer tier: 2,880 ops/day. A full build is ~78, and dry runs count.
- Account is **not** Healthcare-Provider certified yet — safe-proxy framing
  stays until it is.

## Earlier work (2026-08-01/02), for context

- **Fixed `FieldMask` bug.** `client.get_type("FieldMask")` → `from
  google.protobuf.field_mask_pb2 import FieldMask`. 5 sites in
  `tools/campaigns.py` + `tools/structure.py`. All update tools were dead before
  this; creates were unaffected (no update mask).
- **Added `tools/extensions.py`** — 6 tools: `add_callout_extensions`,
  `add_sitelink_extensions`, `add_structured_snippet`, `add_call_extension`,
  `add_ad_schedule`, `set_location_targeting`.
- **Extended `create_search_campaign`** with `callouts`, `sitelinks`,
  `structured_snippet_header/values`, `call_phone_number`, `ad_schedule`,
  `location_presence_only`, `path1`, `path2` — all folded into one atomic mutate.
