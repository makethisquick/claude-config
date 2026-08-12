"""Read helpers the write tools depend on.

Every mutation needs IDs — campaign, ad group, criterion, geo target. Google's
read-only server can find most of them, but bundling these here means the write
server works standalone and the two never disagree about API version.
"""

from typing import Any

from google.ads.googleads.errors import GoogleAdsException

from ..client import get_client, normalize_customer_id


def find_geo_targets(
    query: str,
    country_code: str = "US",
    locale: str = "en",
    limit: int = 15,
) -> dict[str, Any]:
    """Looks up geo target constant IDs by place name, for campaign targeting.

    e.g. find_geo_targets("Brooklyn") -> the ID you pass as geo_target_ids.
    """
    client = get_client()
    service = client.get_service("GeoTargetConstantService")

    request = client.get_type("SuggestGeoTargetConstantsRequest")
    request.locale = locale
    request.country_code = country_code
    request.location_names.names.append(query)

    try:
        response = service.suggest_geo_target_constants(request=request)
    except GoogleAdsException as exc:
        return {
            "status": "error",
            "errors": [e.message for e in exc.failure.errors],
        }

    results = []
    for suggestion in response.geo_target_constant_suggestions[:limit]:
        constant = suggestion.geo_target_constant
        results.append(
            {
                "id": str(constant.id),
                "name": constant.name,
                "canonical_name": constant.canonical_name,
                "target_type": constant.target_type,
                "country_code": constant.country_code,
                "reach": suggestion.reach,
            }
        )
    return {"status": "ok", "query": query, "results": results}


# --------------------------------------------------------------------------
# targeting taxonomies
# --------------------------------------------------------------------------
#
# Display targeting criteria are referenced by numeric ID, and none of them are
# guessable. Unlike geo targets there is no Suggest* RPC for any of these — the
# only way in is a GAQL query against the backing resource, so that is what this
# does, then filters client-side.
#
# Client-side rather than a GAQL WHERE on purpose: `topic_constant.path` is a
# repeated field (no LIKE), GAQL string matching is case-sensitive, and the
# whole taxonomy is a couple of thousand rows in one page. Correctness beats
# cleverness here.
#
# Each entry: (resource, primary select, fallback select, row -> record).

_MAX_SCAN = 20000


def _user_interest_record(row):
    node = row.user_interest
    return {
        "id": str(node.user_interest_id),
        "name": node.name,
        "resource_name": node.resource_name,
        "taxonomy_type": node.taxonomy_type.name,
        "launched_to_all": node.launched_to_all,
    }


def _topic_record(row):
    node = row.topic_constant
    return {
        "id": str(node.id),
        "name": "/".join(node.path),
        "resource_name": node.resource_name,
        "path": list(node.path),
    }


def _mobile_app_category_record(row):
    node = row.mobile_app_category_constant
    return {"id": str(node.id), "name": node.name, "resource_name": node.resource_name}


def _user_list_record(row):
    node = row.user_list
    return {
        "id": str(node.id),
        "name": node.name,
        "resource_name": node.resource_name,
        "type": node.type_.name,
        "eligible_for_display": node.eligible_for_display,
        "size_for_display": node.size_for_display,
    }


def _custom_audience_record(row):
    node = row.custom_audience
    return {
        "id": str(node.id),
        "name": node.name,
        "resource_name": node.resource_name,
        "type": node.type_.name,
        "status": node.status.name,
        "description": node.description,
    }


def _life_event_record(row):
    node = row.life_event
    return {"id": str(node.id), "name": node.name, "resource_name": node.resource_name}


_TAXONOMIES: dict[str, tuple[str, str, str | None, Any]] = {
    "user_interest": (
        "user_interest",
        "SELECT user_interest.user_interest_id, user_interest.name, "
        "user_interest.taxonomy_type, user_interest.launched_to_all FROM user_interest",
        None,
        _user_interest_record,
    ),
    "topic": (
        "topic_constant",
        "SELECT topic_constant.id, topic_constant.path FROM topic_constant",
        "SELECT topic_constant.id FROM topic_constant",
        _topic_record,
    ),
    "mobile_app_category": (
        "mobile_app_category_constant",
        "SELECT mobile_app_category_constant.id, mobile_app_category_constant.name "
        "FROM mobile_app_category_constant",
        None,
        _mobile_app_category_record,
    ),
    "user_list": (
        "user_list",
        "SELECT user_list.id, user_list.name, user_list.type, "
        "user_list.eligible_for_display, user_list.size_for_display FROM user_list",
        "SELECT user_list.id, user_list.name, user_list.type FROM user_list",
        _user_list_record,
    ),
    "custom_audience": (
        "custom_audience",
        "SELECT custom_audience.id, custom_audience.name, custom_audience.type, "
        "custom_audience.status, custom_audience.description FROM custom_audience",
        None,
        _custom_audience_record,
    ),
    "life_event": (
        "life_event",
        "SELECT life_event.id, life_event.name FROM life_event",
        None,
        _life_event_record,
    ),
}


def find_targeting_criteria(
    customer_id: str,
    kind: str,
    query: str = "",
    limit: int = 25,
) -> dict[str, Any]:
    """Resolves a Display targeting taxonomy name to the numeric ID tools need.

    The `add_*_targeting` tools take IDs, and IDs are not guessable. This is the
    way in. Read-only.

    | `kind` | Backing resource | Feeds |
    |---|---|---|
    | `user_interest` | `user_interest` | `add_audience_targeting(user_interest_ids=…)` — affinity **and** in-market both live here; check `taxonomy_type` |
    | `topic` | `topic_constant` | `add_topic_targeting(topic_ids=…)` |
    | `mobile_app_category` | `mobile_app_category_constant` | `exclude_mobile_app_placements(app_category_ids=…)` |
    | `user_list` | `user_list` | `add_audience_targeting(user_list_ids=…)` — remarketing |
    | `custom_audience` | `custom_audience` | `add_audience_targeting(custom_audience_ids=…)` |
    | `life_event` | `life_event` | reference only — no tool takes these yet |

    `query` is matched case-insensitively; every whitespace-separated token must
    appear somewhere in the name (for topics, in the full slash-joined path).
    An empty query lists the first `limit` rows, which is how you enumerate a
    small taxonomy such as the account's own user lists.
    """
    if kind not in _TAXONOMIES:
        return {
            "status": "error",
            "errors": [
                f"unknown kind {kind!r} — valid kinds are: "
                f"{', '.join(sorted(_TAXONOMIES))}"
            ],
        }

    client = get_client()
    cid = normalize_customer_id(customer_id)
    service = client.get_service("GoogleAdsService")
    resource, gaql, fallback_gaql, to_record = _TAXONOMIES[kind]

    def _search(statement):
        request = client.get_type("SearchGoogleAdsRequest")
        request.customer_id = cid
        request.query = statement
        return service.search(request=request)

    try:
        response = _search(gaql)
        rows = list(_take(response))
    except GoogleAdsException as exc:
        # A selectable-field mismatch is the likely cause; retry with the
        # narrower select before giving up.
        if not fallback_gaql:
            return {
                "status": "error",
                "kind": kind,
                "resource": resource,
                "errors": [e.message for e in exc.failure.errors],
            }
        try:
            rows = list(_take(_search(fallback_gaql)))
        except GoogleAdsException as retry_exc:
            return {
                "status": "error",
                "kind": kind,
                "resource": resource,
                "errors": [e.message for e in retry_exc.failure.errors],
            }

    tokens = [t for t in str(query or "").lower().split() if t]
    results = []
    for row in rows:
        record = to_record(row)
        haystack = f"{record.get('name', '')} {record.get('description', '')}".lower()
        if tokens and not all(t in haystack for t in tokens):
            continue
        results.append(record)
        if len(results) >= limit:
            break

    return {
        "status": "ok",
        "kind": kind,
        "resource": resource,
        "query": query,
        "scanned": len(rows),
        "result_count": len(results),
        "results": results,
    }


def _take(response):
    """Bounded iteration over a search response — these taxonomies auto-page."""
    for i, row in enumerate(response):
        if i >= _MAX_SCAN:
            break
        yield row


def query(customer_id: str, gaql: str, limit: int = 200) -> dict[str, Any]:
    """Runs a GAQL query. Read-only — use it to find IDs before mutating.

    e.g. SELECT campaign.id, campaign.name, campaign.status FROM campaign
    """
    client = get_client()
    cid = normalize_customer_id(customer_id)
    service = client.get_service("GoogleAdsService")

    request = client.get_type("SearchGoogleAdsRequest")
    request.customer_id = cid
    request.query = gaql

    try:
        response = service.search(request=request)
    except GoogleAdsException as exc:
        return {
            "status": "error",
            "errors": [
                {"message": e.message, "code": str(e.error_code).strip()}
                for e in exc.failure.errors
            ],
        }

    from google.protobuf.json_format import MessageToDict

    rows = []
    for i, row in enumerate(response):
        if i >= limit:
            break
        rows.append(MessageToDict(row._pb, preserving_proto_field_name=True))

    return {"status": "ok", "customer_id": cid, "row_count": len(rows), "rows": rows}
