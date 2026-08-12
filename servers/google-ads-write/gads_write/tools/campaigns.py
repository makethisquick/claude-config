"""Campaign creation and lifecycle.

A Search campaign is six kinds of object (budget, campaign, ad group, ad,
keywords, targeting criteria). They are emitted as one atomic operation list
using temporary resource IDs, so either the whole campaign appears or none of it
does — no orphaned budgets from a half-failed build.
"""

from datetime import date
from typing import Any

from google.protobuf.field_mask_pb2 import FieldMask

from ..client import get_client, normalize_customer_id
from ..safety import TempIds, apply
from .extensions import (
    build_ad_schedule_ops,
    build_call_ops,
    build_callout_ops,
    build_sitelink_ops,
    build_structured_snippet_ops,
)

# Deliberate: a newly built campaign never starts spending on its own. Enabling
# is a separate, explicit call.
_DEFAULT_STATUS = "PAUSED"


def _budget_path(client, cid, temp_id):
    return client.get_service("CampaignBudgetService").campaign_budget_path(cid, temp_id)


def _campaign_path(client, cid, temp_id):
    return client.get_service("CampaignService").campaign_path(cid, temp_id)


def _ad_group_path(client, cid, temp_id):
    return client.get_service("AdGroupService").ad_group_path(cid, temp_id)


def _to_micros(amount: float) -> int:
    """Google Ads money is micros: $1.00 == 1_000_000."""
    return int(round(float(amount) * 1_000_000))


def _date_time(value: str | None, end_of_day: bool = False) -> str | None:
    """v25 takes `YYYY-MM-DD HH:MM:SS` in the account's timezone, not YYYYMMDD.

    Accepts a bare date and fills in the time.
    """
    if not value:
        return None
    value = value.strip()
    if len(value) == 10:  # bare YYYY-MM-DD
        return f"{value} {'23:59:59' if end_of_day else '00:00:00'}"
    return value


def create_search_campaign(
    customer_id: str,
    campaign_name: str,
    daily_budget: float,
    final_url: str,
    headlines: list[str],
    descriptions: list[str],
    keywords: list[str],
    ad_group_name: str = "Ad group 1",
    match_type: str = "PHRASE",
    negative_keywords: list[str] | None = None,
    geo_target_ids: list[str] | None = None,
    language_ids: list[str] | None = None,
    bidding_strategy: str = "MANUAL_CPC",
    cpc_bid: float | None = None,
    target_cpa: float | None = None,
    search_partners: bool = False,
    callouts: list[str] | None = None,
    sitelinks: list[dict] | None = None,
    structured_snippet_header: str | None = None,
    structured_snippet_values: list[str] | None = None,
    call_phone_number: str | None = None,
    call_country_code: str = "US",
    ad_schedule: list[dict] | None = None,
    location_presence_only: bool = True,
    path1: str | None = None,
    path2: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    status: str = _DEFAULT_STATUS,
    eu_political_advertising: str = "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
    request_policy_exemptions: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Builds a complete Search campaign in one atomic mutate.

    Defaults to a dry run and to PAUSED. Returns what would be created unless
    confirm=True.
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)
    temp = TempIds()

    # --- validate what the API would reject anyway, but with clearer messages
    problems = []
    if not 3 <= len(headlines) <= 15:
        problems.append(f"responsive search ads need 3-15 headlines, got {len(headlines)}")
    if not 2 <= len(descriptions) <= 4:
        problems.append(f"responsive search ads need 2-4 descriptions, got {len(descriptions)}")
    for h in headlines:
        if len(h) > 30:
            problems.append(f"headline over 30 chars ({len(h)}): {h!r}")
    for d in descriptions:
        if len(d) > 90:
            problems.append(f"description over 90 chars ({len(d)}): {d!r}")
    if not keywords:
        problems.append("at least one keyword is required")
    if bidding_strategy == "TARGET_CPA" and target_cpa is None:
        problems.append("bidding_strategy=TARGET_CPA requires target_cpa")
    for label, value in (("path1", path1), ("path2", path2)):
        if value and len(value) > 15:
            problems.append(f"{label} over 15 chars ({len(value)}): {value!r}")
    if path2 and not path1:
        problems.append("path2 requires path1")
    if bool(structured_snippet_header) != bool(structured_snippet_values):
        problems.append(
            "structured_snippet_header and structured_snippet_values must be given together"
        )
    if problems:
        return {"status": "rejected", "applied": False, "errors": problems}

    operations = []

    # --- budget
    budget_id = temp.take()
    budget_rn = _budget_path(client, cid, budget_id)
    op = client.get_type("MutateOperation")
    budget = op.campaign_budget_operation.create
    budget.resource_name = budget_rn
    budget.name = f"{campaign_name} budget"
    budget.amount_micros = _to_micros(daily_budget)
    budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    budget.explicitly_shared = False
    operations.append(op)

    # --- campaign
    campaign_id = temp.take()
    campaign_rn = _campaign_path(client, cid, campaign_id)
    op = client.get_type("MutateOperation")
    campaign = op.campaign_operation.create
    campaign.resource_name = campaign_rn
    campaign.name = campaign_name
    campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH
    campaign.status = getattr(client.enums.CampaignStatusEnum, status)
    campaign.campaign_budget = budget_rn
    campaign.network_settings.target_google_search = True
    campaign.network_settings.target_search_network = search_partners
    campaign.network_settings.target_content_network = False
    # Required since v25. Exposed as a parameter rather than hardcoded because
    # declaring this wrongly is a policy violation, not a technicality.
    campaign.contains_eu_political_advertising = getattr(
        client.enums.EuPoliticalAdvertisingStatusEnum, eu_political_advertising
    )
    # Google defaults to PRESENCE_OR_INTEREST, which serves to people merely
    # researching the area. For a local business that is wasted budget.
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
    else:
        return {
            "status": "rejected",
            "applied": False,
            "errors": [f"unknown bidding_strategy {bidding_strategy!r}"],
        }

    campaign.start_date_time = _date_time(start_date) or date.today().strftime(
        "%Y-%m-%d 00:00:00"
    )
    if end_date:
        campaign.end_date_time = _date_time(end_date, end_of_day=True)
    operations.append(op)

    # --- ad group
    ad_group_id = temp.take()
    ad_group_rn = _ad_group_path(client, cid, ad_group_id)
    op = client.get_type("MutateOperation")
    ad_group = op.ad_group_operation.create
    ad_group.resource_name = ad_group_rn
    ad_group.name = ad_group_name
    ad_group.campaign = campaign_rn
    ad_group.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
    ad_group.status = client.enums.AdGroupStatusEnum.ENABLED
    if cpc_bid is not None:
        ad_group.cpc_bid_micros = _to_micros(cpc_bid)
    operations.append(op)

    # --- responsive search ad
    op = client.get_type("MutateOperation")
    ad_group_ad = op.ad_group_ad_operation.create
    ad_group_ad.ad_group = ad_group_rn
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.ENABLED
    ad_group_ad.ad.final_urls.append(final_url)
    for text in headlines:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        ad_group_ad.ad.responsive_search_ad.headlines.append(asset)
    for text in descriptions:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        ad_group_ad.ad.responsive_search_ad.descriptions.append(asset)
    # Display paths are cosmetic: they shape the green URL shown in the ad and
    # need not match the real path.
    if path1:
        ad_group_ad.ad.responsive_search_ad.path1 = path1
    if path2:
        ad_group_ad.ad.responsive_search_ad.path2 = path2
    operations.append(op)

    # --- keywords
    match = getattr(client.enums.KeywordMatchTypeEnum, match_type)
    for text in keywords:
        op = client.get_type("MutateOperation")
        criterion = op.ad_group_criterion_operation.create
        criterion.ad_group = ad_group_rn
        criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        criterion.keyword.text = text
        criterion.keyword.match_type = match
        operations.append(op)

    for text in negative_keywords or []:
        op = client.get_type("MutateOperation")
        criterion = op.ad_group_criterion_operation.create
        criterion.ad_group = ad_group_rn
        criterion.negative = True
        criterion.keyword.text = text
        criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.BROAD
        operations.append(op)

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

    # --- extensions and schedule, folded into the same atomic batch so a
    #     campaign is never created half-equipped
    extension_problems = []
    if callouts:
        ops, errs = build_callout_ops(client, cid, campaign_rn, callouts, temp)
        operations += ops
        extension_problems += errs
    if sitelinks:
        ops, errs = build_sitelink_ops(client, cid, campaign_rn, sitelinks, temp)
        operations += ops
        extension_problems += errs
    if structured_snippet_header:
        ops, errs = build_structured_snippet_ops(
            client, cid, campaign_rn, structured_snippet_header,
            structured_snippet_values or [], temp,
        )
        operations += ops
        extension_problems += errs
    if call_phone_number:
        ops, errs = build_call_ops(
            client, cid, campaign_rn, call_phone_number, call_country_code, temp
        )
        operations += ops
        extension_problems += errs
    if ad_schedule:
        ops, errs = build_ad_schedule_ops(client, campaign_rn, ad_schedule)
        operations += ops
        extension_problems += errs
    if extension_problems:
        return {"status": "rejected", "applied": False, "errors": extension_problems}

    summary = {
        "action": "create_search_campaign",
        "campaign": campaign_name,
        "status": status,
        "daily_budget": f"${daily_budget:,.2f}",
        "bidding": bidding_strategy,
        "ad_group": ad_group_name,
        "keywords": len(keywords),
        "negative_keywords": len(negative_keywords or []),
        "headlines": len(headlines),
        "descriptions": len(descriptions),
        "geo_targets": geo_target_ids or [],
        "languages": language_ids or [],
        "final_url": final_url,
        "search_partners": search_partners,
        "display_path": "/".join(p for p in (path1, path2) if p) or None,
        "callouts": len(callouts or []),
        "sitelinks": len(sitelinks or []),
        "structured_snippet": structured_snippet_header or None,
        "call_extension": call_phone_number or None,
        "ad_schedule_blocks": len(ad_schedule or []),
        "location_presence_only": location_presence_only,
    }
    return apply(cid, operations, confirm, summary, request_policy_exemptions)


def set_campaign_status(
    customer_id: str,
    campaign_id: str,
    status: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Pauses, enables, or removes a campaign. status: ENABLED | PAUSED | REMOVED."""
    client = get_client()
    cid = normalize_customer_id(customer_id)

    op = client.get_type("MutateOperation")
    campaign = op.campaign_operation.update
    campaign.resource_name = _campaign_path(client, cid, campaign_id)
    campaign.status = getattr(client.enums.CampaignStatusEnum, status)
    client.copy_from(
        op.campaign_operation.update_mask,
        FieldMask(paths=["status"]),
    )

    return apply(
        cid,
        [op],
        confirm,
        {"action": "set_campaign_status", "campaign_id": campaign_id, "status": status},
    )


def update_campaign_budget(
    customer_id: str,
    budget_id: str,
    daily_budget: float,
    confirm: bool = False,
) -> dict[str, Any]:
    """Changes a campaign budget's daily amount."""
    client = get_client()
    cid = normalize_customer_id(customer_id)

    op = client.get_type("MutateOperation")
    budget = op.campaign_budget_operation.update
    budget.resource_name = _budget_path(client, cid, budget_id)
    budget.amount_micros = _to_micros(daily_budget)
    client.copy_from(
        op.campaign_budget_operation.update_mask,
        FieldMask(paths=["amount_micros"]),
    )

    return apply(
        cid,
        [op],
        confirm,
        {
            "action": "update_campaign_budget",
            "budget_id": budget_id,
            "new_daily_budget": f"${daily_budget:,.2f}",
        },
    )
