"""Display campaigns and responsive display ads.

A Display campaign is the same shape as a Search campaign — budget, campaign,
ad group, ad, targeting criteria — emitted as one atomic operation list with
temporary resource IDs, so either the whole thing appears or none of it does.

The difference is the creative. A responsive display ad carries no image bytes:
it references `Asset` resources by resource name. Upload the images first with
`upload_image_asset` (or find existing ones with `list_assets`) and pass the
asset IDs here.

Image slots, and how they map onto the v25 `ResponsiveDisplayAdInfo` proto:

| Parameter                          | Proto field             | Ratio |
|------------------------------------|-------------------------|-------|
| `marketing_image_asset_ids`        | `marketing_images`      | 1.91:1 |
| `square_marketing_image_asset_ids` | `square_marketing_images` | 1:1  |
| `logo_asset_ids`                   | `square_logo_images`    | 1:1   |
| `landscape_logo_asset_ids`         | `logo_images`           | 4:1   |

Note the proto's naming: the *unqualified* `logo_images` is the 4:1 landscape
logo, and the 1:1 logo lives in `square_logo_images`. The parameter names here
follow the Google Ads UI ("Logo" is the square one) rather than the proto.
"""

from datetime import date
from typing import Any

from ..client import get_client, normalize_customer_id
from ..safety import TempIds, apply

# Same rail as Search: a newly built campaign never starts spending on its own.
_DEFAULT_STATUS = "PAUSED"

# Google's own limits. Enforced client-side so the failure names the offending
# string instead of arriving as a generic STRING_TOO_LONG on operation 4 — and
# because one overlong string rejects the entire atomic mutate.
_HEADLINE_MAX = 30
_LONG_HEADLINE_MAX = 90
_DESCRIPTION_MAX = 90
_BUSINESS_NAME_MAX = 25

_HEADLINES_MAX = 5
_DESCRIPTIONS_MAX = 5
_IMAGES_MAX = 15
_LOGOS_MAX = 5


def _budget_path(client, cid, temp_id):
    return client.get_service("CampaignBudgetService").campaign_budget_path(cid, temp_id)


def _campaign_path(client, cid, campaign_id):
    return client.get_service("CampaignService").campaign_path(cid, campaign_id)


def _ad_group_path(client, cid, ad_group_id):
    return client.get_service("AdGroupService").ad_group_path(cid, ad_group_id)


def _asset_path(client, cid, asset_id):
    """Accepts a bare asset ID or an already-qualified resource name."""
    asset_id = str(asset_id).strip()
    if asset_id.startswith("customers/"):
        return asset_id
    return client.get_service("AssetService").asset_path(cid, asset_id)


def _to_micros(amount: float) -> int:
    """Google Ads money is micros: $1.00 == 1_000_000."""
    return int(round(float(amount) * 1_000_000))


def _date_time(value: str | None, end_of_day: bool = False) -> str | None:
    """v25 takes `YYYY-MM-DD HH:MM:SS` in the account's timezone, not YYYYMMDD."""
    if not value:
        return None
    value = value.strip()
    if len(value) == 10:  # bare YYYY-MM-DD
        return f"{value} {'23:59:59' if end_of_day else '00:00:00'}"
    return value


# --------------------------------------------------------------------------
# responsive display ad — shared by both tools
# --------------------------------------------------------------------------


def validate_rda(
    headlines: list[str],
    long_headline: str,
    descriptions: list[str],
    business_name: str,
    marketing_image_asset_ids: list[str] | None,
    square_marketing_image_asset_ids: list[str] | None,
    logo_asset_ids: list[str] | None,
    landscape_logo_asset_ids: list[str] | None,
) -> list[str]:
    """Client-side length and cardinality checks. Returns a list of problems.

    Google rejects the whole mutate for a single overlong string, and the error
    it returns does not say which string. These messages name it.
    """
    problems: list[str] = []

    marketing = marketing_image_asset_ids or []
    square = square_marketing_image_asset_ids or []
    logos = logo_asset_ids or []
    landscape = landscape_logo_asset_ids or []

    if not 1 <= len(headlines) <= _HEADLINES_MAX:
        problems.append(
            f"responsive display ads need 1-{_HEADLINES_MAX} headlines, got {len(headlines)}"
        )
    for h in headlines:
        if len(h) > _HEADLINE_MAX:
            problems.append(f"headline over {_HEADLINE_MAX} chars ({len(h)}): {h!r}")

    if not long_headline:
        problems.append("long_headline is required")
    elif len(long_headline) > _LONG_HEADLINE_MAX:
        problems.append(
            f"long_headline over {_LONG_HEADLINE_MAX} chars "
            f"({len(long_headline)}): {long_headline!r}"
        )

    if not 1 <= len(descriptions) <= _DESCRIPTIONS_MAX:
        problems.append(
            f"responsive display ads need 1-{_DESCRIPTIONS_MAX} descriptions, "
            f"got {len(descriptions)}"
        )
    for d in descriptions:
        if len(d) > _DESCRIPTION_MAX:
            problems.append(f"description over {_DESCRIPTION_MAX} chars ({len(d)}): {d!r}")

    if not business_name:
        problems.append("business_name is required")
    elif len(business_name) > _BUSINESS_NAME_MAX:
        problems.append(
            f"business_name over {_BUSINESS_NAME_MAX} chars "
            f"({len(business_name)}): {business_name!r}"
        )

    # At least one landscape marketing image is mandatory; the square one is
    # what serves in most native slots, so an ad without it is badly crippled.
    if not marketing:
        problems.append("at least one marketing_image_asset_ids entry (1.91:1) is required")
    if not square:
        problems.append(
            "at least one square_marketing_image_asset_ids entry (1:1) is required"
        )
    if not logos and not landscape:
        problems.append(
            "at least one logo is required — logo_asset_ids (1:1) or "
            "landscape_logo_asset_ids (4:1)"
        )

    for label, values, limit in (
        ("marketing_image_asset_ids", marketing, _IMAGES_MAX),
        ("square_marketing_image_asset_ids", square, _IMAGES_MAX),
        ("logo_asset_ids", logos, _LOGOS_MAX),
        ("landscape_logo_asset_ids", landscape, _LOGOS_MAX),
    ):
        if len(values) > limit:
            problems.append(f"{label} takes at most {limit} assets, got {len(values)}")

    return problems


def build_responsive_display_ad_op(
    client,
    cid: str,
    ad_group_rn: str,
    final_url: str,
    headlines: list[str],
    long_headline: str,
    descriptions: list[str],
    business_name: str,
    marketing_image_asset_ids: list[str] | None = None,
    square_marketing_image_asset_ids: list[str] | None = None,
    logo_asset_ids: list[str] | None = None,
    landscape_logo_asset_ids: list[str] | None = None,
    call_to_action_text: str | None = None,
):
    """Builds the single AdGroupAd operation carrying the RDA.

    Returns (operations, problems), matching the extensions.py builder shape so
    it can be folded into a larger atomic batch.
    """
    problems = validate_rda(
        headlines,
        long_headline,
        descriptions,
        business_name,
        marketing_image_asset_ids,
        square_marketing_image_asset_ids,
        logo_asset_ids,
        landscape_logo_asset_ids,
    )
    if problems:
        return [], problems

    op = client.get_type("MutateOperation")
    ad_group_ad = op.ad_group_ad_operation.create
    ad_group_ad.ad_group = ad_group_rn
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.ENABLED
    ad_group_ad.ad.final_urls.append(final_url)

    rda = ad_group_ad.ad.responsive_display_ad

    # Images are referenced by asset resource name — bytes were uploaded
    # earlier by upload_image_asset. See the module docstring for the mapping
    # between these parameter names and the proto's fields.
    for target, asset_ids in (
        (rda.marketing_images, marketing_image_asset_ids or []),
        (rda.square_marketing_images, square_marketing_image_asset_ids or []),
        (rda.square_logo_images, logo_asset_ids or []),
        (rda.logo_images, landscape_logo_asset_ids or []),
    ):
        for asset_id in asset_ids:
            image = client.get_type("AdImageAsset")
            image.asset = _asset_path(client, cid, asset_id)
            target.append(image)

    for text in headlines:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        rda.headlines.append(asset)
    for text in descriptions:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        rda.descriptions.append(asset)
    rda.long_headline.text = long_headline
    rda.business_name = business_name
    if call_to_action_text:
        rda.call_to_action_text = call_to_action_text

    return [op], []


# --------------------------------------------------------------------------
# tools
# --------------------------------------------------------------------------


def create_display_campaign(
    customer_id: str,
    campaign_name: str,
    daily_budget: float,
    final_url: str,
    headlines: list[str],
    long_headline: str,
    descriptions: list[str],
    business_name: str,
    marketing_image_asset_ids: list[str] | None = None,
    square_marketing_image_asset_ids: list[str] | None = None,
    logo_asset_ids: list[str] | None = None,
    landscape_logo_asset_ids: list[str] | None = None,
    ad_group_name: str = "Ad group 1",
    geo_target_ids: list[str] | None = None,
    language_ids: list[str] | None = None,
    bidding_strategy: str = "MANUAL_CPC",
    cpc_bid: float | None = None,
    target_cpa: float | None = None,
    location_presence_only: bool = True,
    call_to_action_text: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    status: str = _DEFAULT_STATUS,
    eu_political_advertising: str = "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
    request_policy_exemptions: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Builds a complete Display campaign in one atomic mutate.

    Creates a budget, a DISPLAY campaign, an ad group, one responsive display
    ad, and geo/language targeting criteria. Images are referenced by asset ID —
    upload them first with upload_image_asset.

    Defaults to a dry run and to PAUSED.
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)
    temp = TempIds()

    # --- validate what the API would reject anyway, but with clearer messages
    problems = validate_rda(
        headlines,
        long_headline,
        descriptions,
        business_name,
        marketing_image_asset_ids,
        square_marketing_image_asset_ids,
        logo_asset_ids,
        landscape_logo_asset_ids,
    )
    if bidding_strategy == "TARGET_CPA" and target_cpa is None:
        problems.append("bidding_strategy=TARGET_CPA requires target_cpa")
    if bidding_strategy not in (
        "MANUAL_CPC",
        "MAXIMIZE_CONVERSIONS",
        "TARGET_CPA",
        "MAXIMIZE_CLICKS",
    ):
        problems.append(f"unknown bidding_strategy {bidding_strategy!r}")
    if problems:
        return {"status": "rejected", "applied": False, "errors": problems}

    operations = []

    # --- budget
    budget_rn = _budget_path(client, cid, temp.take())
    op = client.get_type("MutateOperation")
    budget = op.campaign_budget_operation.create
    budget.resource_name = budget_rn
    budget.name = f"{campaign_name} budget"
    budget.amount_micros = _to_micros(daily_budget)
    budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    budget.explicitly_shared = False
    operations.append(op)

    # --- campaign
    campaign_rn = _campaign_path(client, cid, temp.take())
    op = client.get_type("MutateOperation")
    campaign = op.campaign_operation.create
    campaign.resource_name = campaign_rn
    campaign.name = campaign_name
    campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.DISPLAY
    campaign.status = getattr(client.enums.CampaignStatusEnum, status)
    campaign.campaign_budget = budget_rn
    # A Display campaign serves on the content network only. Left explicit
    # rather than relying on the API's defaults.
    campaign.network_settings.target_google_search = False
    campaign.network_settings.target_search_network = False
    campaign.network_settings.target_content_network = True
    # Required since v25. Exposed as a parameter rather than hardcoded because
    # declaring this wrongly is a policy violation, not a technicality.
    campaign.contains_eu_political_advertising = getattr(
        client.enums.EuPoliticalAdvertisingStatusEnum, eu_political_advertising
    )
    if location_presence_only:
        campaign.geo_target_type_setting.positive_geo_target_type = (
            client.enums.PositiveGeoTargetTypeEnum.PRESENCE
        )
        campaign.geo_target_type_setting.negative_geo_target_type = (
            client.enums.NegativeGeoTargetTypeEnum.PRESENCE
        )

    if bidding_strategy == "MANUAL_CPC":
        campaign.manual_cpc.enhanced_cpc_enabled = False
    elif bidding_strategy == "MAXIMIZE_CONVERSIONS":
        campaign.maximize_conversions.target_cpa_micros = (
            _to_micros(target_cpa) if target_cpa else 0
        )
    elif bidding_strategy == "TARGET_CPA":
        campaign.target_cpa.target_cpa_micros = _to_micros(target_cpa)
    elif bidding_strategy == "MAXIMIZE_CLICKS":
        campaign.target_spend = client.get_type("TargetSpend")

    campaign.start_date_time = _date_time(start_date) or date.today().strftime(
        "%Y-%m-%d 00:00:00"
    )
    if end_date:
        campaign.end_date_time = _date_time(end_date, end_of_day=True)
    operations.append(op)

    # --- ad group
    ad_group_rn = _ad_group_path(client, cid, temp.take())
    op = client.get_type("MutateOperation")
    ad_group = op.ad_group_operation.create
    ad_group.resource_name = ad_group_rn
    ad_group.name = ad_group_name
    ad_group.campaign = campaign_rn
    ad_group.type_ = client.enums.AdGroupTypeEnum.DISPLAY_STANDARD
    ad_group.status = client.enums.AdGroupStatusEnum.ENABLED
    if cpc_bid is not None:
        ad_group.cpc_bid_micros = _to_micros(cpc_bid)
    operations.append(op)

    # --- responsive display ad
    ad_ops, ad_problems = build_responsive_display_ad_op(
        client,
        cid,
        ad_group_rn,
        final_url,
        headlines,
        long_headline,
        descriptions,
        business_name,
        marketing_image_asset_ids,
        square_marketing_image_asset_ids,
        logo_asset_ids,
        landscape_logo_asset_ids,
        call_to_action_text,
    )
    if ad_problems:
        return {"status": "rejected", "applied": False, "errors": ad_problems}
    operations += ad_ops

    # --- targeting
    for geo_id in geo_target_ids or []:
        op = client.get_type("MutateOperation")
        criterion = op.campaign_criterion_operation.create
        criterion.campaign = campaign_rn
        criterion.location.geo_target_constant = f"geoTargetConstants/{geo_id}"
        operations.append(op)

    for language_id in language_ids or []:
        op = client.get_type("MutateOperation")
        criterion = op.campaign_criterion_operation.create
        criterion.campaign = campaign_rn
        criterion.language.language_constant = f"languageConstants/{language_id}"
        operations.append(op)

    summary = {
        "action": "create_display_campaign",
        "campaign": campaign_name,
        "channel": "DISPLAY",
        "status": status,
        "daily_budget": f"${daily_budget:,.2f}",
        "bidding": bidding_strategy,
        "cpc_bid": f"${cpc_bid:,.2f}" if cpc_bid is not None else None,
        "ad_group": ad_group_name,
        "final_url": final_url,
        "business_name": business_name,
        "headlines": len(headlines),
        "long_headline": long_headline,
        "descriptions": len(descriptions),
        "marketing_images": len(marketing_image_asset_ids or []),
        "square_marketing_images": len(square_marketing_image_asset_ids or []),
        "logos": len(logo_asset_ids or []),
        "landscape_logos": len(landscape_logo_asset_ids or []),
        "call_to_action_text": call_to_action_text,
        "geo_targets": geo_target_ids or [],
        "languages": language_ids or [],
        "location_presence_only": location_presence_only,
    }
    return apply(cid, operations, confirm, summary, request_policy_exemptions)


def create_responsive_display_ad(
    customer_id: str,
    ad_group_id: str,
    final_url: str,
    headlines: list[str],
    long_headline: str,
    descriptions: list[str],
    business_name: str,
    marketing_image_asset_ids: list[str] | None = None,
    square_marketing_image_asset_ids: list[str] | None = None,
    logo_asset_ids: list[str] | None = None,
    landscape_logo_asset_ids: list[str] | None = None,
    call_to_action_text: str | None = None,
    request_policy_exemptions: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Adds a responsive display ad to an ad group that already exists.

    The ad group must belong to a Display campaign and be DISPLAY_STANDARD.
    Images are referenced by asset ID — upload them first with upload_image_asset.
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)

    operations, problems = build_responsive_display_ad_op(
        client,
        cid,
        _ad_group_path(client, cid, ad_group_id),
        final_url,
        headlines,
        long_headline,
        descriptions,
        business_name,
        marketing_image_asset_ids,
        square_marketing_image_asset_ids,
        logo_asset_ids,
        landscape_logo_asset_ids,
        call_to_action_text,
    )
    if problems:
        return {"status": "rejected", "applied": False, "errors": problems}

    return apply(
        cid,
        operations,
        confirm,
        {
            "action": "create_responsive_display_ad",
            "ad_group_id": ad_group_id,
            "final_url": final_url,
            "business_name": business_name,
            "headlines": len(headlines),
            "long_headline": long_headline,
            "descriptions": len(descriptions),
            "marketing_images": len(marketing_image_asset_ids or []),
            "square_marketing_images": len(square_marketing_image_asset_ids or []),
            "logos": len(logo_asset_ids or []),
            "landscape_logos": len(landscape_logo_asset_ids or []),
            "call_to_action_text": call_to_action_text,
        },
        request_policy_exemptions,
    )
