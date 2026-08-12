"""Google Ads write MCP server.

Companion to Google's official read-only server. Everything that changes an
account lives here, behind a confirm gate.
"""

import logging

from fastmcp import FastMCP

from .tools import (
    assets,
    campaigns,
    conversions,
    display,
    extensions,
    lookup,
    structure,
    targeting,
)

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

INSTRUCTIONS = """
Write access to Google Ads. These tools change live advertising accounts that
spend real money.

Every mutating tool takes `confirm` and defaults it to false. With confirm=false
the request is sent to Google with validate_only — fully checked, nothing
written — and the response says what *would* change. Show that to the user and
get their agreement before re-running with confirm=true.

Never pass confirm=true on the first call for a given change. Never pass it to
"save a step" when the user has not seen the dry run.

New campaigns are created PAUSED. Enabling one starts spending money, so treat
set_campaign_status(status="ENABLED") as its own decision that needs its own
confirmation.
""".strip()

mcp = FastMCP(name="Google Ads Write", instructions=INSTRUCTIONS)


# --------------------------------------------------------------------------
# lookup (read-only)
# --------------------------------------------------------------------------

mcp.tool(
    lookup.query,
    name="query",
    description=(
        "Run a GAQL query (read-only). Use this to find campaign, ad group, ad, "
        "and criterion IDs before mutating anything."
    ),
)

mcp.tool(
    lookup.find_geo_targets,
    name="find_geo_targets",
    description=(
        "Look up geo target constant IDs by place name, for campaign location "
        "targeting. Returns IDs to pass as geo_target_ids."
    ),
)

mcp.tool(
    lookup.find_targeting_criteria,
    name="find_targeting_criteria",
    description=(
        "Look up Display targeting IDs by name. kind is one of user_interest "
        "(affinity and in-market), topic, mobile_app_category, user_list "
        "(remarketing), custom_audience, life_event. Returns the numeric IDs the "
        "add_*_targeting and exclude_mobile_app_placements tools require — they "
        "cannot be guessed. Read-only."
    ),
)


# --------------------------------------------------------------------------
# campaigns
# --------------------------------------------------------------------------

mcp.tool(
    campaigns.create_search_campaign,
    name="create_search_campaign",
    description=(
        "Build a complete Search campaign atomically: budget, campaign, ad group, "
        "responsive search ad, keywords, negatives, and geo/language targeting. "
        "Created PAUSED by default. DRY RUN unless confirm=true — always dry-run "
        "first and show the result to the user."
    ),
)

mcp.tool(
    campaigns.set_campaign_status,
    name="set_campaign_status",
    description=(
        "Pause, enable, or remove a campaign (ENABLED | PAUSED | REMOVED). "
        "Enabling starts real spending. DRY RUN unless confirm=true."
    ),
)

mcp.tool(
    campaigns.update_campaign_budget,
    name="update_campaign_budget",
    description=(
        "Change a campaign budget's daily amount. This directly changes how much "
        "the account can spend per day. DRY RUN unless confirm=true."
    ),
)


# --------------------------------------------------------------------------
# structure
# --------------------------------------------------------------------------

for func, name, description in [
    (
        structure.create_ad_group,
        "create_ad_group",
        "Add an ad group to an existing campaign. DRY RUN unless confirm=true.",
    ),
    (
        structure.set_ad_group_status,
        "set_ad_group_status",
        "ENABLED | PAUSED | REMOVED for an ad group. DRY RUN unless confirm=true.",
    ),
    (
        structure.set_ad_group_bid,
        "set_ad_group_bid",
        "Change an ad group's default max CPC. DRY RUN unless confirm=true.",
    ),
    (
        structure.add_keywords,
        "add_keywords",
        "Add positive keywords to an ad group. DRY RUN unless confirm=true.",
    ),
    (
        structure.add_negative_keywords,
        "add_negative_keywords",
        "Add negative keywords at ad group or campaign level. DRY RUN unless confirm=true.",
    ),
    (
        structure.remove_keywords,
        "remove_keywords",
        "Remove keywords by criterion ID. DRY RUN unless confirm=true.",
    ),
    (
        structure.create_responsive_search_ad,
        "create_responsive_search_ad",
        "Add a responsive search ad to an existing ad group. DRY RUN unless confirm=true.",
    ),
    (
        structure.set_ad_status,
        "set_ad_status",
        "ENABLED | PAUSED | REMOVED for a single ad. DRY RUN unless confirm=true.",
    ),
]:
    mcp.tool(func, name=name, description=description)



# --------------------------------------------------------------------------
# extensions — assets linked to a campaign, plus campaign-level targeting
# --------------------------------------------------------------------------

for func, name, description in [
    (
        extensions.add_callout_extensions,
        "add_callout_extensions",
        "Attach callout extensions (short trust phrases, max 25 chars each) to a "
        "campaign. DRY RUN unless confirm=true.",
    ),
    (
        extensions.add_sitelink_extensions,
        "add_sitelink_extensions",
        "Attach sitelinks to a campaign. Each is a dict: {\"text\" (max 25), "
        "\"url\", optional \"description1\"/\"description2\" (max 35, both or "
        "neither)}. DRY RUN unless confirm=true.",
    ),
    (
        extensions.add_structured_snippet,
        "add_structured_snippet",
        "Attach a structured snippet, e.g. header=\"Services\" with 3-10 values "
        "(max 25 chars each). DRY RUN unless confirm=true.",
    ),
    (
        extensions.add_call_extension,
        "add_call_extension",
        "Attach a call extension so the ad can be dialled straight from search. "
        "For a business whose conversion is a phone call this is the highest-value "
        "extension. DRY RUN unless confirm=true.",
    ),
    (
        extensions.add_ad_schedule,
        "add_ad_schedule",
        "Restrict a campaign to given hours, in the account timezone. schedule is "
        "a list of {\"days\": [\"MONDAY\", ...], \"start_hour\": 8, \"end_hour\": 19}. "
        "Without one a campaign runs 24/7. DRY RUN unless confirm=true.",
    ),
    (
        extensions.set_location_targeting,
        "set_location_targeting",
        "Set whether geo targeting means PRESENCE (people in the area) or "
        "PRESENCE_OR_INTEREST (Google's broader default). DRY RUN unless confirm=true.",
    ),
]:
    mcp.tool(func, name=name, description=description)


# --------------------------------------------------------------------------
# assets — the prerequisite for Display / Performance Max / Demand Gen
# --------------------------------------------------------------------------

mcp.tool(
    assets.upload_image_asset,
    name="upload_image_asset",
    description=(
        "Upload an image as a reusable Asset from a local file path or an http(s) "
        "URL. Required before Display or Performance Max campaigns can use "
        "creative. For a Google Drive file, download it with the Drive tools "
        "first and pass the local path. DRY RUN unless confirm=true."
    ),
)

mcp.tool(
    assets.create_text_asset,
    name="create_text_asset",
    description="Create a reusable text asset for Performance Max asset groups. DRY RUN unless confirm=true.",
)

mcp.tool(
    assets.list_assets,
    name="list_assets",
    description="List existing assets in the account (read-only), so creative can be reused.",
)


# --------------------------------------------------------------------------
# display — campaigns and responsive display ads, built on uploaded assets
# --------------------------------------------------------------------------

mcp.tool(
    display.create_display_campaign,
    name="create_display_campaign",
    description=(
        "Build a complete Display campaign atomically: budget, DISPLAY campaign, "
        "ad group, responsive display ad, and geo/language targeting. Images are "
        "referenced by existing asset ID — upload them first with "
        "upload_image_asset and find existing ones with list_assets. Needs "
        "1.91:1 marketing images, 1:1 square marketing images, and a logo. "
        "Created PAUSED by default. DRY RUN unless confirm=true — always dry-run "
        "first and show the result to the user."
    ),
)

mcp.tool(
    display.create_responsive_display_ad,
    name="create_responsive_display_ad",
    description=(
        "Add a responsive display ad to an existing Display ad group. Same "
        "creative parameters as create_display_campaign; images referenced by "
        "asset ID. DRY RUN unless confirm=true."
    ),
)


# --------------------------------------------------------------------------
# display targeting — what keeps a Display campaign from spraying
# --------------------------------------------------------------------------

for func, name, description in [
    (
        targeting.exclude_mobile_app_placements,
        "exclude_mobile_app_placements",
        "Exclude mobile-app inventory from a Display campaign: a negative "
        "MOBILE_APP_CATEGORY criterion on 'All Apps' (69500) plus a negative "
        "placement on adsenseformobileapps.com. This is the usual cause of an "
        "abnormally high Display CTR — in-app accidental clicks. Does NOT cover "
        "mobile web, in-app webviews, YouTube, or other campaigns. "
        "DRY RUN unless confirm=true.",
    ),
    (
        targeting.add_audience_targeting,
        "add_audience_targeting",
        "Target or exclude audiences on a campaign or ad group: user_interest_ids "
        "(affinity / in-market), user_list_ids (remarketing), custom_audience_ids. "
        "Get IDs from find_targeting_criteria. Exactly one of campaign_id or "
        "ad_group_id. DRY RUN unless confirm=true.",
    ),
    (
        targeting.add_topic_targeting,
        "add_topic_targeting",
        "Target or exclude Display topics (content categories) on an ad group. "
        "IDs from find_targeting_criteria(kind=\"topic\"). negative=true excludes. "
        "DRY RUN unless confirm=true.",
    ),
    (
        targeting.add_placement_targeting,
        "add_placement_targeting",
        "Managed placements on an ad group. negative=false restricts the ad group "
        "to those sites only; negative=true excludes them and leaves the rest of "
        "the network. DRY RUN unless confirm=true.",
    ),
    (
        targeting.add_demographic_targeting,
        "add_demographic_targeting",
        "Age / gender / parental status / income criteria on an ad group. Takes "
        "human-readable values (\"25-34\", \"female\", \"not-a-parent\", \"90+\") and "
        "maps them to v25 enums; unknown values are rejected by name. "
        "exclude=true makes them negative. DRY RUN unless confirm=true.",
    ),
]:
    mcp.tool(func, name=name, description=description)


# --------------------------------------------------------------------------
# conversions — what counts as a result, and what bidding optimises towards
# --------------------------------------------------------------------------

for func, name, description in [
    (
        conversions.set_conversion_action_primary,
        "set_conversion_action_primary",
        "Set primary_for_goal on a conversion action. true = counted in the "
        "main Conversions column and eligible for bidding; false = demoted to "
        "secondary (still recorded under All conversions). This is the "
        "action-level flag — the goal-level one is set_customer_conversion_goal. "
        "GOOGLE_HOSTED (Google Business Profile) actions may refuse the "
        "mutation. DRY RUN unless confirm=true.",
    ),
    (
        conversions.set_conversion_action_status,
        "set_conversion_action_status",
        "ENABLED | REMOVED | HIDDEN for a conversion action. There is no "
        "PAUSED: HIDDEN stops recording but keeps history, REMOVED deletes. "
        "To only stop counting an action in the Conversions column, prefer "
        "set_conversion_action_primary(primary=false). DRY RUN unless confirm=true.",
    ),
    (
        conversions.set_customer_conversion_goal,
        "set_customer_conversion_goal",
        "Set biddable on an account-level (category, origin) conversion goal, "
        "e.g. category=\"GET_DIRECTIONS\", origin=\"GOOGLE_HOSTED\". biddable "
        "controls whether Smart Bidding optimises towards that bucket. Goals "
        "cannot be created or deleted — only biddable is writable. Accepts UI "
        "wording (\"directions\", \"phone calls\", \"Google Business Profile\") "
        "and rejects unknown values by name. DRY RUN unless confirm=true.",
    ),
    (
        conversions.set_campaign_conversion_goal,
        "set_campaign_conversion_goal",
        "Same as set_customer_conversion_goal but for one campaign, overriding "
        "the account default. Does not change whether the campaign is on "
        "account-default or custom goals. DRY RUN unless confirm=true.",
    ),
]:
    mcp.tool(func, name=name, description=description)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
