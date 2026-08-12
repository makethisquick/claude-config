"""Ad groups, ads, and keywords on campaigns that already exist.

Everything here goes through the same confirm gate as campaign creation.
"""

from typing import Any

from google.protobuf.field_mask_pb2 import FieldMask

from ..client import get_client, normalize_customer_id
from ..safety import apply


def _ad_group_path(client, cid, ad_group_id):
    return client.get_service("AdGroupService").ad_group_path(cid, ad_group_id)


def _campaign_path(client, cid, campaign_id):
    return client.get_service("CampaignService").campaign_path(cid, campaign_id)


def _to_micros(amount: float) -> int:
    return int(round(float(amount) * 1_000_000))


def add_keywords(
    customer_id: str,
    ad_group_id: str,
    keywords: list[str],
    match_type: str = "PHRASE",
    cpc_bid: float | None = None,
    request_policy_exemptions: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Adds positive keywords to an existing ad group."""
    client = get_client()
    cid = normalize_customer_id(customer_id)
    ad_group_rn = _ad_group_path(client, cid, ad_group_id)
    match = getattr(client.enums.KeywordMatchTypeEnum, match_type)

    operations = []
    for text in keywords:
        op = client.get_type("MutateOperation")
        criterion = op.ad_group_criterion_operation.create
        criterion.ad_group = ad_group_rn
        criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        criterion.keyword.text = text
        criterion.keyword.match_type = match
        if cpc_bid is not None:
            criterion.cpc_bid_micros = _to_micros(cpc_bid)
        operations.append(op)

    return apply(
        cid,
        operations,
        confirm,
        {
            "action": "add_keywords",
            "ad_group_id": ad_group_id,
            "match_type": match_type,
            "keywords": keywords,
        },
        request_policy_exemptions,
    )


def add_negative_keywords(
    customer_id: str,
    keywords: list[str],
    ad_group_id: str | None = None,
    campaign_id: str | None = None,
    match_type: str = "BROAD",
    confirm: bool = False,
) -> dict[str, Any]:
    """Adds negative keywords at ad group or campaign level.

    Exactly one of ad_group_id or campaign_id must be given.
    """
    if bool(ad_group_id) == bool(campaign_id):
        return {
            "status": "rejected",
            "applied": False,
            "errors": ["provide exactly one of ad_group_id or campaign_id"],
        }

    client = get_client()
    cid = normalize_customer_id(customer_id)
    match = getattr(client.enums.KeywordMatchTypeEnum, match_type)

    operations = []
    for text in keywords:
        op = client.get_type("MutateOperation")
        if ad_group_id:
            criterion = op.ad_group_criterion_operation.create
            criterion.ad_group = _ad_group_path(client, cid, ad_group_id)
        else:
            criterion = op.campaign_criterion_operation.create
            criterion.campaign = _campaign_path(client, cid, campaign_id)
        criterion.negative = True
        criterion.keyword.text = text
        criterion.keyword.match_type = match
        operations.append(op)

    return apply(
        cid,
        operations,
        confirm,
        {
            "action": "add_negative_keywords",
            "level": "ad_group" if ad_group_id else "campaign",
            "target_id": ad_group_id or campaign_id,
            "keywords": keywords,
        },
    )


def remove_keywords(
    customer_id: str,
    ad_group_id: str,
    criterion_ids: list[str],
    confirm: bool = False,
) -> dict[str, Any]:
    """Removes keywords by criterion ID. Find IDs with a GAQL query on ad_group_criterion."""
    client = get_client()
    cid = normalize_customer_id(customer_id)
    service = client.get_service("AdGroupCriterionService")

    operations = []
    for criterion_id in criterion_ids:
        op = client.get_type("MutateOperation")
        op.ad_group_criterion_operation.remove = service.ad_group_criterion_path(
            cid, ad_group_id, criterion_id
        )
        operations.append(op)

    return apply(
        cid,
        operations,
        confirm,
        {
            "action": "remove_keywords",
            "ad_group_id": ad_group_id,
            "criterion_ids": criterion_ids,
        },
    )


def create_ad_group(
    customer_id: str,
    campaign_id: str,
    name: str,
    cpc_bid: float | None = None,
    status: str = "ENABLED",
    confirm: bool = False,
) -> dict[str, Any]:
    """Adds an ad group to an existing campaign."""
    client = get_client()
    cid = normalize_customer_id(customer_id)

    op = client.get_type("MutateOperation")
    ad_group = op.ad_group_operation.create
    ad_group.name = name
    ad_group.campaign = _campaign_path(client, cid, campaign_id)
    ad_group.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
    ad_group.status = getattr(client.enums.AdGroupStatusEnum, status)
    if cpc_bid is not None:
        ad_group.cpc_bid_micros = _to_micros(cpc_bid)

    return apply(
        cid,
        [op],
        confirm,
        {
            "action": "create_ad_group",
            "campaign_id": campaign_id,
            "name": name,
            "status": status,
        },
    )


def set_ad_group_status(
    customer_id: str,
    ad_group_id: str,
    status: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """ENABLED | PAUSED | REMOVED."""
    client = get_client()
    cid = normalize_customer_id(customer_id)

    op = client.get_type("MutateOperation")
    ad_group = op.ad_group_operation.update
    ad_group.resource_name = _ad_group_path(client, cid, ad_group_id)
    ad_group.status = getattr(client.enums.AdGroupStatusEnum, status)
    client.copy_from(
        op.ad_group_operation.update_mask,
        FieldMask(paths=["status"]),
    )

    return apply(
        cid,
        [op],
        confirm,
        {"action": "set_ad_group_status", "ad_group_id": ad_group_id, "status": status},
    )


def set_ad_group_bid(
    customer_id: str,
    ad_group_id: str,
    cpc_bid: float,
    confirm: bool = False,
) -> dict[str, Any]:
    """Changes an ad group's default max CPC."""
    client = get_client()
    cid = normalize_customer_id(customer_id)

    op = client.get_type("MutateOperation")
    ad_group = op.ad_group_operation.update
    ad_group.resource_name = _ad_group_path(client, cid, ad_group_id)
    ad_group.cpc_bid_micros = _to_micros(cpc_bid)
    client.copy_from(
        op.ad_group_operation.update_mask,
        FieldMask(paths=["cpc_bid_micros"]),
    )

    return apply(
        cid,
        [op],
        confirm,
        {
            "action": "set_ad_group_bid",
            "ad_group_id": ad_group_id,
            "cpc_bid": f"${cpc_bid:,.2f}",
        },
    )


def create_responsive_search_ad(
    customer_id: str,
    ad_group_id: str,
    final_url: str,
    headlines: list[str],
    descriptions: list[str],
    path1: str | None = None,
    path2: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Adds a responsive search ad to an existing ad group."""
    problems = []
    if not 3 <= len(headlines) <= 15:
        problems.append(f"need 3-15 headlines, got {len(headlines)}")
    if not 2 <= len(descriptions) <= 4:
        problems.append(f"need 2-4 descriptions, got {len(descriptions)}")
    for h in headlines:
        if len(h) > 30:
            problems.append(f"headline over 30 chars ({len(h)}): {h!r}")
    for d in descriptions:
        if len(d) > 90:
            problems.append(f"description over 90 chars ({len(d)}): {d!r}")
    if problems:
        return {"status": "rejected", "applied": False, "errors": problems}

    client = get_client()
    cid = normalize_customer_id(customer_id)

    op = client.get_type("MutateOperation")
    ad_group_ad = op.ad_group_ad_operation.create
    ad_group_ad.ad_group = _ad_group_path(client, cid, ad_group_id)
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
    if path1:
        ad_group_ad.ad.responsive_search_ad.path1 = path1
    if path2:
        ad_group_ad.ad.responsive_search_ad.path2 = path2

    return apply(
        cid,
        [op],
        confirm,
        {
            "action": "create_responsive_search_ad",
            "ad_group_id": ad_group_id,
            "final_url": final_url,
            "headlines": len(headlines),
            "descriptions": len(descriptions),
        },
    )


def set_ad_status(
    customer_id: str,
    ad_group_id: str,
    ad_id: str,
    status: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """ENABLED | PAUSED | REMOVED for a single ad."""
    client = get_client()
    cid = normalize_customer_id(customer_id)
    service = client.get_service("AdGroupAdService")

    op = client.get_type("MutateOperation")
    ad_group_ad = op.ad_group_ad_operation.update
    ad_group_ad.resource_name = service.ad_group_ad_path(cid, ad_group_id, ad_id)
    ad_group_ad.status = getattr(client.enums.AdGroupAdStatusEnum, status)
    client.copy_from(
        op.ad_group_ad_operation.update_mask,
        FieldMask(paths=["status"]),
    )

    return apply(
        cid,
        [op],
        confirm,
        {"action": "set_ad_status", "ad_id": ad_id, "status": status},
    )
