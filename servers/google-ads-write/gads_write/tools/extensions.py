"""Ad extensions and campaign-level targeting settings.

Extensions are the single biggest lever on search CTR that is *not* the ad copy
itself, and a campaign built without them is only half built. In the modern API
there is no "extension" object: each one is an `Asset`, linked to a campaign by
a `CampaignAsset` row carrying a `field_type`. Both halves are emitted in one
atomic mutate with a temporary asset ID, so an asset is never created without
its link.

The builders here return operation lists rather than calling `apply()` so that
`create_search_campaign` can fold extensions into the same all-or-nothing batch
that creates the campaign.
"""

from typing import Any

from google.protobuf.field_mask_pb2 import FieldMask

from ..client import get_client, normalize_customer_id
from ..safety import TempIds, apply

# Google's own limits. Enforced here so the failure names the offending string
# instead of arriving as a generic STRING_TOO_LONG on operation 7.
_CALLOUT_MAX = 25
_SITELINK_TEXT_MAX = 25
_SITELINK_DESC_MAX = 35
_SNIPPET_VALUE_MAX = 25

# Callouts and snippet values below these counts are accepted by the API but
# will never serve, which is a worse outcome than a clear rejection.
_CALLOUT_MIN = 2
_SNIPPET_VALUES_MIN = 3
_SNIPPET_VALUES_MAX = 10


def _asset_path(client, cid, temp_id):
    return client.get_service("AssetService").asset_path(cid, temp_id)


def _campaign_path(client, cid, campaign_id):
    return client.get_service("CampaignService").campaign_path(cid, campaign_id)


def _link_asset(client, campaign_rn: str, asset_rn: str, field_type: str):
    """The CampaignAsset row that actually attaches an asset to a campaign."""
    op = client.get_type("MutateOperation")
    link = op.campaign_asset_operation.create
    link.campaign = campaign_rn
    link.asset = asset_rn
    link.field_type = getattr(client.enums.AssetFieldTypeEnum, field_type)
    return op


# --------------------------------------------------------------------------
# builders — return (operations, problems)
# --------------------------------------------------------------------------


def build_callout_ops(client, cid, campaign_rn, callouts: list[str], temp: TempIds):
    problems = []
    if len(callouts) < _CALLOUT_MIN:
        problems.append(
            f"need at least {_CALLOUT_MIN} callouts for them to serve, got {len(callouts)}"
        )
    for text in callouts:
        if len(text) > _CALLOUT_MAX:
            problems.append(f"callout over {_CALLOUT_MAX} chars ({len(text)}): {text!r}")
    if problems:
        return [], problems

    operations = []
    for text in callouts:
        asset_rn = _asset_path(client, cid, temp.take())
        op = client.get_type("MutateOperation")
        asset = op.asset_operation.create
        asset.resource_name = asset_rn
        asset.callout_asset.callout_text = text
        operations.append(op)
        operations.append(_link_asset(client, campaign_rn, asset_rn, "CALLOUT"))
    return operations, []


def build_sitelink_ops(client, cid, campaign_rn, sitelinks: list[dict], temp: TempIds):
    """sitelinks: [{"text","url","description1"?,"description2"?}, ...]"""
    problems = []
    for i, link in enumerate(sitelinks):
        text = link.get("text")
        url = link.get("url")
        if not text or not url:
            problems.append(f"sitelink {i}: both 'text' and 'url' are required")
            continue
        if len(text) > _SITELINK_TEXT_MAX:
            problems.append(
                f"sitelink text over {_SITELINK_TEXT_MAX} chars ({len(text)}): {text!r}"
            )
        d1, d2 = link.get("description1"), link.get("description2")
        # Google rejects a lone description line.
        if bool(d1) != bool(d2):
            problems.append(
                f"sitelink {text!r}: provide both description1 and description2, or neither"
            )
        for d in (d1, d2):
            if d and len(d) > _SITELINK_DESC_MAX:
                problems.append(
                    f"sitelink description over {_SITELINK_DESC_MAX} chars ({len(d)}): {d!r}"
                )
    if problems:
        return [], problems

    operations = []
    for link in sitelinks:
        asset_rn = _asset_path(client, cid, temp.take())
        op = client.get_type("MutateOperation")
        asset = op.asset_operation.create
        asset.resource_name = asset_rn
        asset.final_urls.append(link["url"])
        asset.sitelink_asset.link_text = link["text"]
        if link.get("description1"):
            asset.sitelink_asset.description1 = link["description1"]
            asset.sitelink_asset.description2 = link["description2"]
        operations.append(op)
        operations.append(_link_asset(client, campaign_rn, asset_rn, "SITELINK"))
    return operations, []


def build_structured_snippet_ops(
    client, cid, campaign_rn, header: str, values: list[str], temp: TempIds
):
    problems = []
    if not _SNIPPET_VALUES_MIN <= len(values) <= _SNIPPET_VALUES_MAX:
        problems.append(
            f"structured snippets need {_SNIPPET_VALUES_MIN}-{_SNIPPET_VALUES_MAX} "
            f"values, got {len(values)}"
        )
    for v in values:
        if len(v) > _SNIPPET_VALUE_MAX:
            problems.append(
                f"snippet value over {_SNIPPET_VALUE_MAX} chars ({len(v)}): {v!r}"
            )
    if problems:
        return [], problems

    asset_rn = _asset_path(client, cid, temp.take())
    op = client.get_type("MutateOperation")
    asset = op.asset_operation.create
    asset.resource_name = asset_rn
    # Header must be one of Google's predefined set ("Services", "Brands", ...).
    # Left to the API to validate: the list is localised and changes.
    asset.structured_snippet_asset.header = header
    asset.structured_snippet_asset.values.extend(values)
    return [op, _link_asset(client, campaign_rn, asset_rn, "STRUCTURED_SNIPPET")], []


def build_call_ops(
    client, cid, campaign_rn, phone_number: str, country_code: str, temp: TempIds
):
    asset_rn = _asset_path(client, cid, temp.take())
    op = client.get_type("MutateOperation")
    asset = op.asset_operation.create
    asset.resource_name = asset_rn
    asset.call_asset.country_code = country_code
    asset.call_asset.phone_number = phone_number
    return [op, _link_asset(client, campaign_rn, asset_rn, "CALL")], []


def build_ad_schedule_ops(client, campaign_rn, schedule: list[dict]):
    """schedule: [{"days":[...], "start_hour":8, "end_hour":19, ...}, ...]

    Absent an ad schedule a campaign runs 24/7, which for an office with staffed
    hours spends budget on clicks nobody can answer.
    """
    operations, problems = [], []
    for i, block in enumerate(schedule):
        days = block.get("days") or ([block["day"]] if block.get("day") else [])
        if not days:
            problems.append(f"schedule block {i}: 'days' is required")
            continue
        start_hour = block.get("start_hour")
        end_hour = block.get("end_hour")
        if start_hour is None or end_hour is None:
            problems.append(f"schedule block {i}: start_hour and end_hour are required")
            continue
        if not 0 <= start_hour <= 23:
            problems.append(f"start_hour must be 0-23, got {start_hour}")
        if not 0 <= end_hour <= 24:
            problems.append(f"end_hour must be 0-24, got {end_hour}")
        if end_hour <= start_hour:
            problems.append(
                f"schedule block {i}: end_hour ({end_hour}) must be after "
                f"start_hour ({start_hour})"
            )
        start_minute = block.get("start_minute", "ZERO")
        end_minute = block.get("end_minute", "ZERO")
        # Google treats hour 24 as end-of-day and rejects a non-zero minute with it.
        if end_hour == 24 and end_minute != "ZERO":
            problems.append("end_minute must be ZERO when end_hour is 24")

        for day in days:
            op = client.get_type("MutateOperation")
            criterion = op.campaign_criterion_operation.create
            criterion.campaign = campaign_rn
            try:
                criterion.ad_schedule.day_of_week = getattr(
                    client.enums.DayOfWeekEnum, day
                )
                criterion.ad_schedule.start_minute = getattr(
                    client.enums.MinuteOfHourEnum, start_minute
                )
                criterion.ad_schedule.end_minute = getattr(
                    client.enums.MinuteOfHourEnum, end_minute
                )
            except AttributeError as exc:
                problems.append(f"schedule block {i}: {exc}")
                continue
            criterion.ad_schedule.start_hour = start_hour
            criterion.ad_schedule.end_hour = end_hour
            operations.append(op)

    return (([], problems) if problems else (operations, []))


# --------------------------------------------------------------------------
# tools
# --------------------------------------------------------------------------


def _run(cid, operations, problems, confirm, summary):
    if problems:
        return {"status": "rejected", "applied": False, "errors": problems}
    return apply(cid, operations, confirm, summary)


def add_callout_extensions(
    customer_id: str,
    campaign_id: str,
    callouts: list[str],
    confirm: bool = False,
) -> dict[str, Any]:
    """Attaches callout extensions (short trust phrases) to a campaign."""
    client = get_client()
    cid = normalize_customer_id(customer_id)
    ops, problems = build_callout_ops(
        client, cid, _campaign_path(client, cid, campaign_id), callouts, TempIds()
    )
    return _run(
        cid,
        ops,
        problems,
        confirm,
        {
            "action": "add_callout_extensions",
            "campaign_id": campaign_id,
            "callouts": callouts,
        },
    )


def add_sitelink_extensions(
    customer_id: str,
    campaign_id: str,
    sitelinks: list[dict],
    confirm: bool = False,
) -> dict[str, Any]:
    """Attaches sitelinks. Each: {"text", "url", "description1"?, "description2"?}."""
    client = get_client()
    cid = normalize_customer_id(customer_id)
    ops, problems = build_sitelink_ops(
        client, cid, _campaign_path(client, cid, campaign_id), sitelinks, TempIds()
    )
    return _run(
        cid,
        ops,
        problems,
        confirm,
        {
            "action": "add_sitelink_extensions",
            "campaign_id": campaign_id,
            "sitelinks": [s.get("text") for s in sitelinks],
        },
    )


def add_structured_snippet(
    customer_id: str,
    campaign_id: str,
    header: str,
    values: list[str],
    confirm: bool = False,
) -> dict[str, Any]:
    """Attaches a structured snippet, e.g. header="Services", values=[...]."""
    client = get_client()
    cid = normalize_customer_id(customer_id)
    ops, problems = build_structured_snippet_ops(
        client, cid, _campaign_path(client, cid, campaign_id), header, values, TempIds()
    )
    return _run(
        cid,
        ops,
        problems,
        confirm,
        {
            "action": "add_structured_snippet",
            "campaign_id": campaign_id,
            "header": header,
            "values": values,
        },
    )


def add_call_extension(
    customer_id: str,
    campaign_id: str,
    phone_number: str,
    country_code: str = "US",
    confirm: bool = False,
) -> dict[str, Any]:
    """Attaches a call extension so the ad can be dialled straight from search."""
    client = get_client()
    cid = normalize_customer_id(customer_id)
    ops, problems = build_call_ops(
        client,
        cid,
        _campaign_path(client, cid, campaign_id),
        phone_number,
        country_code,
        TempIds(),
    )
    return _run(
        cid,
        ops,
        problems,
        confirm,
        {
            "action": "add_call_extension",
            "campaign_id": campaign_id,
            "phone_number": phone_number,
            "country_code": country_code,
        },
    )


def add_ad_schedule(
    customer_id: str,
    campaign_id: str,
    schedule: list[dict],
    confirm: bool = False,
) -> dict[str, Any]:
    """Restricts a campaign to given hours.

    schedule: [{"days": ["MONDAY", ...], "start_hour": 8, "end_hour": 19}, ...]
    Minutes are "ZERO" | "FIFTEEN" | "THIRTY" | "FORTY_FIVE" and default to ZERO.
    Hours are in the account's timezone.
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)
    ops, problems = build_ad_schedule_ops(
        client, _campaign_path(client, cid, campaign_id), schedule
    )
    return _run(
        cid,
        ops,
        problems,
        confirm,
        {
            "action": "add_ad_schedule",
            "campaign_id": campaign_id,
            "blocks": len(schedule),
            "criteria": len(ops),
        },
    )


def set_location_targeting(
    customer_id: str,
    campaign_id: str,
    positive_geo_target_type: str = "PRESENCE",
    negative_geo_target_type: str = "PRESENCE",
    confirm: bool = False,
) -> dict[str, Any]:
    """Controls whether targeting means presence or merely interest.

    Google defaults to PRESENCE_OR_INTEREST, which also serves to people who are
    only *searching about* the area. PRESENCE restricts to people actually in it
    — usually what a local business wants, and materially cheaper.
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)

    op = client.get_type("MutateOperation")
    campaign = op.campaign_operation.update
    campaign.resource_name = _campaign_path(client, cid, campaign_id)
    campaign.geo_target_type_setting.positive_geo_target_type = getattr(
        client.enums.PositiveGeoTargetTypeEnum, positive_geo_target_type
    )
    campaign.geo_target_type_setting.negative_geo_target_type = getattr(
        client.enums.NegativeGeoTargetTypeEnum, negative_geo_target_type
    )
    client.copy_from(
        op.campaign_operation.update_mask,
        FieldMask(
            paths=[
                "geo_target_type_setting.positive_geo_target_type",
                "geo_target_type_setting.negative_geo_target_type",
            ]
        ),
    )

    return apply(
        cid,
        [op],
        confirm,
        {
            "action": "set_location_targeting",
            "campaign_id": campaign_id,
            "positive": positive_geo_target_type,
            "negative": negative_geo_target_type,
        },
    )
